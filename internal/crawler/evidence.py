import hashlib
import ipaddress
import json
import time
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from http.client import HTTPException

import httpx

from internal.crawler.catalog import RuleStore
from internal.crawler.fetch import fetch_evidence
from internal.crawler.rules import Rule
from internal.storage.database import Database


def parse_networks(payload: object) -> list[str]:
    if isinstance(payload, dict):
        if "prefixes" in payload:
            prefixes = payload["prefixes"]
            if not isinstance(prefixes, list):
                raise ValueError("invalid prefixes")
            values = []
            for item in prefixes:
                if not isinstance(item, dict):
                    raise ValueError("invalid prefix")
                value = item.get("ipv4Prefix") or item.get("ipv6Prefix") or item.get("ip_prefix")
                if not isinstance(value, str):
                    raise ValueError("invalid prefix")
                values.append(value)
        else:
            values = next(
                (
                    payload[key]
                    for key in ("ips", "ip", "ip_addresses", "addresses", "ipRanges")
                    if key in payload
                ),
                None,
            )
    else:
        values = payload
    if not isinstance(values, list) or not values or len(values) > 10000:
        raise ValueError("unsupported evidence format")
    return sorted({str(ipaddress.ip_network(value, strict=False)) for value in values})


class OfficialCode(HTMLParser):
    """Read JSON code blocks from an explicitly selected HTTPS evidence page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active = False
        self.parts = []
        self.blocks = []

    def handle_starttag(self, tag, attrs):
        if tag == "code":
            self.active = True
            self.parts = []

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "code" and self.active:
            self.blocks.append("".join(self.parts))
            self.active = False


def decode_evidence(payload: bytes, rule: Rule):
    if rule.evidence_format != "amazon-code":
        return json.loads(payload)
    parser = OfficialCode()
    parser.feed(payload.decode("utf-8"))
    candidates = []
    for block in parser.blocks:
        try:
            decoded = json.loads(block)
        except ValueError:
            continue
        if isinstance(decoded, dict) and "prefixes" in decoded:
            candidates.append(decoded)
    if len(candidates) != 1:
        raise ValueError("official evidence code block missing or ambiguous")
    return candidates[0]


class EvidenceStore:
    def __init__(self, database: Database, ttl: int = 86400):
        self.database = database
        self.ttl = ttl
        self.rules = RuleStore(database)

    @staticmethod
    def current(conn, rule):
        row = conn.execute("SELECT * FROM crawler_rules WHERE token=?", (rule.token,)).fetchone()
        return (
            row
            and row["enabled"]
            and row["version"] == rule.version
            and row["evidence_url"] == rule.evidence_url
            and row["evidence_format"] == rule.evidence_format
        )

    def save(self, rule: Rule, payload: object, now: float | None = None) -> None:
        now = time.time() if now is None else now
        networks = json.dumps(parse_networks(payload), separators=(",", ":"))
        version = hashlib.sha256(networks.encode()).hexdigest()
        self.rules.seed()
        with self.database.transaction() as conn:
            if not self.current(conn, rule):
                return
            conn.execute(
                """INSERT INTO evidence VALUES(?,?,?,?,?,?,1)
                ON CONFLICT(crawler) DO UPDATE SET source=excluded.source,version=excluded.version,
                fetched_at=excluded.fetched_at,expires_at=excluded.expires_at,
                networks_json=excluded.networks_json,available=1""",
                (rule.token, rule.evidence_url, version, now, now + self.ttl, networks),
            )

    def snapshot(self) -> dict[str, dict]:
        with self.database.read() as conn:
            return {row["crawler"]: dict(row) for row in conn.execute("SELECT * FROM evidence")}

    def refresh(self, client: httpx.Client | None = None, *, token: str | None = None) -> None:
        groups: dict[tuple[str, str], list[Rule]] = {}
        for rule in self.rules.snapshot():
            if rule.enabled and rule.evidence_url and (token is None or rule.token == token):
                groups.setdefault((rule.evidence_url, rule.evidence_format), []).append(rule)

        def refresh_url(key: tuple[str, str]) -> None:
            url, _format = key
            try:
                if client is None:
                    payload = fetch_evidence(url)
                else:
                    with client.stream("GET", url) as response:
                        response.raise_for_status()
                        payload = bytearray()
                        for chunk in response.iter_bytes():
                            payload.extend(chunk)
                            if len(payload) > 1024 * 1024:
                                raise ValueError("evidence too large")
                decoded = decode_evidence(bytes(payload), groups[key][0])
                for rule in groups[key]:
                    self.save(rule, decoded)
            except (httpx.HTTPError, ValueError, TypeError, OSError, HTTPException):
                with self.database.transaction() as conn:
                    for rule in groups[key]:
                        if self.current(conn, rule):
                            conn.execute(
                                "UPDATE evidence SET available=0 WHERE crawler=?", (rule.token,)
                            )

        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="official-evidence") as pool:
            list(pool.map(refresh_url, groups))


def verify(rule: Rule, address: str, mode: str, snapshots: dict, now: float) -> dict:
    result = {
        "verification": "ua_only",
        "evidence_source": rule.evidence_url,
        "evidence_version": None,
        "evidence_fetched_at": None,
        "evidence_expires_at": None,
    }
    snapshot = snapshots.get(rule.token)
    if snapshot and snapshot["source"] != rule.evidence_url:
        snapshot = None
    if snapshot:
        result.update(
            evidence_version=snapshot["version"],
            evidence_fetched_at=snapshot["fetched_at"],
            evidence_expires_at=snapshot["expires_at"],
        )
    if mode != "trusted":
        result["verification"] = "client_ip_unknown"
    elif rule.evidence_url:
        if not snapshot or not snapshot["available"] or snapshot["expires_at"] <= now:
            result["verification"] = "evidence_unavailable"
        else:
            ip = ipaddress.ip_address(address)
            matches = any(
                ip in ipaddress.ip_network(network)
                for network in json.loads(snapshot["networks_json"])
            )
            result["verification"] = "verified" if matches else "ip_mismatch"
    return result
