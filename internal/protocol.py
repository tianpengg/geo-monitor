"""Version 1 bounded collection protocol. Raw IPs exist only in transit/memory."""

import hashlib
from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress, field_validator, model_validator

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")]
MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_LINE_BYTES = 64 * 1024


def batch_identity(source: str, generation: str, start: int, end: int) -> str:
    return hashlib.sha256(f"{source}:{generation}:{start}:{end}".encode()).hexdigest()


def event_identity(source: str, generation: str, offset: int) -> str:
    return hashlib.sha256(f"{source}:{generation}:{offset}".encode()).hexdigest()


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceMessage(Message):
    version: Literal[1] = 1
    site_id: Identifier
    source_id: Identifier


class Event(Message):
    offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    occurred_at: datetime
    client_ip: IPvAnyAddress = Field(repr=False)
    method: str = Field(pattern=r"^[A-Z]{1,20}$")
    path: str = Field(min_length=1, max_length=4096)
    status: int = Field(ge=100, le=599)
    user_agent: str = Field(max_length=1024, repr=False)

    @field_validator("occurred_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timezone is required")
        return value

    @field_validator("path")
    @classmethod
    def normalize_path(cls, value: str) -> str:
        if value == "*":
            return value
        parsed = urlsplit(value)
        if not parsed.path.startswith("/") or parsed.netloc or parsed.scheme:
            raise ValueError("request target must be an origin path")
        if any(ord(char) < 32 for char in parsed.path):
            raise ValueError("control characters are not allowed")
        return parsed.path

    @model_validator(mode="after")
    def valid_interval(self) -> "Event":
        if self.end_offset <= self.offset:
            raise ValueError("invalid event interval")
        return self


class Issue(Message):
    offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    reason: Literal["invalid_line", "line_too_long", "initial_partial_line"]


class Batch(SourceMessage):
    generation: Identifier
    batch_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    events: list[Event] = Field(max_length=1000)
    issues: list[Issue] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def validate_intervals(self) -> "Batch":
        if self.end_offset <= self.start_offset:
            raise ValueError("empty batch interval")
        if self.batch_id != batch_identity(
            self.source_id, self.generation, self.start_offset, self.end_offset
        ):
            raise ValueError("invalid batch identity")
        cursor = self.start_offset
        for item in sorted([*self.events, *self.issues], key=lambda item: item.offset):
            if item.offset != cursor or item.end_offset <= item.offset:
                raise ValueError("batch intervals must be complete, ordered and non-overlapping")
            cursor = item.end_offset
        if cursor != self.end_offset:
            raise ValueError("batch interval is not covered")
        return self


class Gap(Message):
    id: Identifier
    reason: Literal["file_missing", "truncated", "copytruncate_uncertain", "state_reset"]
    detected_at: datetime
    generation: Identifier | None = None
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=0)

    @field_validator("detected_at")
    @classmethod
    def aware_detection_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timezone is required")
        return value


class Heartbeat(SourceMessage):
    instance_id: Identifier
    sequence: int = Field(ge=0)
    baseline_at: datetime
    state: Literal["ok", "backlog", "read_error", "retrying", "auth_error", "protocol_error"]
    read_offset: int = Field(ge=0)
    acknowledged_offset: int = Field(ge=0)
    pending_bytes: int | None = Field(default=None, ge=0)
    parse_errors: int = Field(default=0, ge=0)
    error_code: Literal["unreadable", "missing", "network", "authentication", "protocol"] | None = (
        None
    )
    last_read_at: datetime | None = None
    gaps: list[Gap] = Field(default_factory=list, max_length=100)

    @field_validator("baseline_at", "last_read_at")
    @classmethod
    def aware_times(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timezone is required")
        return value
