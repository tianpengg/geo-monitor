"""Bounded Sitemap downloads for an explicit host allowlist. Pages are never fetched."""

import gzip
import http.client
import io
import ipaddress
import socket
import ssl
import time
from urllib.parse import quote, urlsplit, urlunsplit
from xml.etree import ElementTree

from internal.server.services.inventory import MAX_FILE_BYTES, MAX_PAGES, normalize_page

MAX_FILES = 20
MAX_TOTAL_BYTES = 10 * MAX_FILE_BYTES
TASK_SECONDS = 60


class SitemapError(ValueError):
    """Only fixed, safe messages from this module may be shown or persisted."""


def sitemap_url(value, host, aliases=()):
    try:
        value = value.strip()
        parsed = urlsplit(value)
        hostname = (parsed.hostname or "").encode("idna").decode().lower().rstrip(".")
        if (
            not value or len(value) > 2048 or "\\" in value
            or any(ord(char) < 33 for char in value)
            or parsed.scheme not in {"http", "https"} or hostname not in {host, *aliases}
            or parsed.username is not None or parsed.password is not None or parsed.fragment
            or parsed.port not in {None, 443 if parsed.scheme == "https" else 80}
        ):
            raise ValueError
        return urlunsplit((parsed.scheme, hostname, parsed.path or "/", parsed.query, ""))
    except (ValueError, UnicodeError):
        raise SitemapError("请填写官网主域名或已登记别名的标准 HTTP/HTTPS Sitemap 地址；别名请在官网配置保存") from None


def remaining(deadline):
    seconds = deadline - time.monotonic()
    if seconds <= 0:
        raise SitemapError("Sitemap 同步超过 60 秒，请缩小索引或稍后重试")
    return min(5, seconds)


def download(url, host, deadline):
    parsed = urlsplit(sitemap_url(url, host))
    port = 443 if parsed.scheme == "https" else 80
    remaining(deadline)
    addresses = {entry[4][0] for entry in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    if not addresses or any(
        not ipaddress.ip_address(address).is_global or ipaddress.ip_address(address).is_multicast
        for address in addresses
    ):
        raise SitemapError("Sitemap 地址解析至非公网网络，已拒绝获取")
    target = sorted(addresses, key=lambda address: (":" in address, address))[0]
    connection = http.client.HTTPConnection(host, port, timeout=remaining(deadline))
    response = None
    stream = None
    try:
        # A connected socket prevents HTTPConnection from resolving the hostname a second time.
        raw = socket.create_connection((target, port), timeout=remaining(deadline))
        connection.sock = raw
        if parsed.scheme == "https":
            connection.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
        stream = connection.sock
        path = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
        if parsed.query:
            path += "?" + quote(parsed.query, safe="%/:@!$&'()*+,;=?-._~")
        connection.request("GET", path, headers={
            "Accept-Encoding": "identity", "User-Agent": "geo-monitor-sitemap/0.1",
        })
        response = connection.getresponse()
        if response.status != 200:
            raise SitemapError("Sitemap 返回非 200 状态或重定向，请填写可直接访问的最终地址")
        parts, length = [], 0
        while response.length != 0:
            stream.settimeout(remaining(deadline))
            part = response.read1(min(65536, MAX_FILE_BYTES + 1 - length))
            if not part:
                if isinstance(response.length, int) and response.length > 0:
                    raise SitemapError("Sitemap 下载不完整，请稍后重试")
                break
            parts.append(part)
            length += len(part)
            if length > MAX_FILE_BYTES:
                raise SitemapError("单个 Sitemap 下载超过 1 MiB")
        return b"".join(parts)
    finally:
        if response:
            response.close()
        connection.close()
        if stream:
            stream.close()


def xml_document(payload):
    if len(payload) > MAX_FILE_BYTES:
        raise SitemapError("单个 Sitemap 下载超过 1 MiB")
    try:
        if payload.startswith(b"\x1f\x8b"):
            with gzip.GzipFile(fileobj=io.BytesIO(payload)) as compressed:
                payload = compressed.read(MAX_FILE_BYTES + 1)
        if len(payload) > MAX_FILE_BYTES:
            raise SitemapError("Sitemap 解压后超过 1 MiB")
        text = payload.decode("utf-8-sig")
        if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise SitemapError("Sitemap 不支持 XML DTD 或实体")
        root = ElementTree.fromstring(text)
        kind = root.tag.split("}")[-1]
        if kind not in {"urlset", "sitemapindex"}:
            raise SitemapError("地址没有返回 urlset 或 sitemapindex XML")
        locations = []
        for child in root:
            if child.tag.split("}")[-1] != ("url" if kind == "urlset" else "sitemap"):
                raise SitemapError("Sitemap XML 结构无效")
            entries = [node.text for node in child if node.tag.split("}")[-1] == "loc"]
            if len(entries) != 1 or not entries[0] or not entries[0].strip():
                raise SitemapError("Sitemap 每项必须包含一个 loc 地址")
            locations.append(entries[0].strip())
        if not locations:
            raise SitemapError("Sitemap 清单为空，原目录已保留")
        return kind, locations, len(payload)
    except (OSError, EOFError, UnicodeError, ElementTree.ParseError):
        raise SitemapError("Sitemap 不是有效的 UTF-8 XML 或 gzip 文件") from None


def collect_pages(url, host, fetch=None, *, aliases=()):
    fetch = fetch or download
    deadline = time.monotonic() + TASK_SECONDS
    pages, seen = {}, set()
    total_bytes = total_entries = 0

    def read(address):
        nonlocal total_bytes
        address = sitemap_url(address, host, aliases)
        if address in seen:
            raise SitemapError("Sitemap 索引存在重复或循环引用")
        if len(seen) >= MAX_FILES:
            raise SitemapError("Sitemap 文件总数超过 20 个（包含索引）")
        seen.add(address)
        remaining(deadline)
        result = xml_document(fetch(address, urlsplit(address).hostname, deadline))
        remaining(deadline)
        total_bytes += result[2]
        if total_bytes > MAX_TOTAL_BYTES:
            raise SitemapError("Sitemap 累计解压内容超过 10 MiB")
        return result

    def add(locations):
        nonlocal total_entries
        total_entries += len(locations)
        if total_entries > MAX_PAGES:
            raise SitemapError("Sitemap 输入页面超过 10000 条")
        for location in locations:
            try:
                pages[normalize_page(location, host, aliases)] = ""
            except ValueError:
                raise SitemapError("Sitemap 含无效、非本站或不支持的页面地址；同站 www 等域名请先在官网配置登记别名") from None

    kind, locations, _ = read(url)
    if kind == "urlset":
        add(locations)
    else:
        if len(locations) + 1 > MAX_FILES:
            raise SitemapError("Sitemap 文件总数超过 20 个（包含索引）")
        # Validate every child before any child is requested.
        children = [sitemap_url(location, host, aliases) for location in locations]
        for address in children:
            child_kind, child_locations, _ = read(address)
            if child_kind != "urlset":
                raise SitemapError("只支持单层 Sitemap 索引，不支持嵌套索引")
            add(child_locations)
    remaining(deadline)
    return pages, len(seen)
