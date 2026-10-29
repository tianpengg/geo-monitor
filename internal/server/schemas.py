import re
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, field_validator

from internal.crawler.fetch import evidence_url


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(max_length=100)
    password: SecretStr = Field(max_length=1024)


class InventoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["xml", "csv", "json"]
    text: str = Field(max_length=1024 * 1024)


class SitemapInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=1, max_length=2048)
    enabled: StrictBool = True


class SiteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain: str = Field(max_length=253)
    timezone: str = "Asia/Shanghai"
    client_ip_mode: Literal["unknown", "trusted"] = "unknown"

    @field_validator("domain")
    @classmethod
    def domain_name(cls, value: str) -> str:
        try:
            normalized = value.strip().rstrip(".").encode("idna").decode().lower()
        except UnicodeError:
            raise ValueError("域名无效") from None
        if "." not in normalized or not all(
            re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
            for label in normalized.split(".")
        ):
            raise ValueError("请填写不含协议、端口或路径的官网域名")
        return normalized

    @field_validator("timezone")
    @classmethod
    def timezone_name(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError):
            raise ValueError("统计时区无效") from None
        return value


class CrawlerRuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    token: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{1,99}$")
    match_token: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{1,99}$")
    name: str = Field(min_length=1, max_length=100)
    operator: str = Field(min_length=1, max_length=100)
    product_attribution: str = Field(min_length=1, max_length=200)
    evidence_url: str | None = Field(default=None, max_length=1024)
    documentation_url: str | None = Field(default=None, max_length=1024)
    evidence_format: Literal["json", "amazon-code"] = "json"
    enabled: StrictBool = True
    revision: int | None = Field(default=None, ge=1)

    @field_validator("evidence_url", "documentation_url", mode="before")
    @classmethod
    def source_url(cls, value):
        if value is not None and not isinstance(value, str):
            raise ValueError("来源地址必须为文本")
        return evidence_url(value) if value else None

    @field_validator("name", "operator", "product_attribution")
    @classmethod
    def readable_text(cls, value):
        if any(ord(char) < 32 for char in value):
            raise ValueError("文本不能包含控制字符")
        return value
