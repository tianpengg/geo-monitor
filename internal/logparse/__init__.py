"""Combined / OpenResty main parser operating on complete binary lines."""

import re
from datetime import UTC, datetime

from internal.protocol import Event

_QUOTED = r'((?:[^"\\]|\\.)*)'
COMBINED = re.compile(
    r'^([^ ]+) [^ ]+ [^ ]+ \[([^\]]+)\] "'
    + _QUOTED
    + r'" ([0-9]{3}) (?:[0-9]+|-) "'
    + _QUOTED
    + r'" "'
    + _QUOTED
    + r'"(?: "(?:[^"\\]|\\.)*")?\s*$'
)
MONTHS = {
    name: index
    for index, name in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)
}


class ParseError(ValueError):
    """Safe error type: never includes the original log line."""


def unescape(value: str) -> str:
    def replace(match):
        part = match.group(1)
        if part.startswith("x"):
            return chr(int(part[1:], 16))
        return {"\\": "\\", '"': '"'}.get(part, "?")

    return re.sub(r"\\(x[0-9a-fA-F]{2}|.)", replace, value)


def parse_line(raw: bytes, offset: int) -> Event:
    try:
        if not raw.endswith(b"\n"):
            raise ParseError("incomplete line")
        match = COMBINED.fullmatch(raw.decode("utf-8", errors="replace"))
        if not match:
            raise ParseError("unsupported Combined line")
        address, timestamp, request, status, _referrer, ua = match.groups()
        day, month, rest = timestamp.split("/", 2)
        year, clock = rest.split(":", 1)
        parsed = datetime.strptime(
            f"{year}-{MONTHS[month]:02}-{day} {clock}", "%Y-%m-%d %H:%M:%S %z"
        )
        method, target, version = unescape(request).split(" ", 2)
        if not version.startswith("HTTP/"):
            raise ParseError("unsupported request")
        return Event(
            offset=offset,
            end_offset=offset + len(raw),
            occurred_at=parsed.astimezone(UTC),
            client_ip=address,
            method=method,
            path=target,
            status=int(status),
            user_agent=unescape(ua)[:1024],
        )
    except (ValueError, KeyError, TypeError):
        raise ParseError("invalid Combined line") from None
