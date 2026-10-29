"""Fetch configured HTTPS evidence without proxy, redirects or private targets."""

import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit

MAX_EVIDENCE_BYTES = 1024 * 1024


def evidence_url(value: str) -> str:
    value = value.strip()
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or parsed.fragment
        or any(ord(char) < 33 for char in value)
    ):
        raise ValueError("证据与资料地址必须为无凭据的 HTTPS 公网地址（默认端口）")
    host = parsed.hostname.encode("idna").decode()
    if "." not in host or host.lower().endswith((".localhost", ".local", ".internal")):
        raise ValueError("核验来源必须是公网主机")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise ValueError("核验来源不能指向非公网地址")
    return value


def fetch_evidence(url: str) -> bytes:
    parsed = urlsplit(evidence_url(url))
    host = parsed.hostname.encode("idna").decode()
    addresses = {entry[4][0] for entry in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("证据地址解析至非公网网络")
    target = sorted(addresses, key=lambda address: (":" in address, address))[0]
    context = ssl.create_default_context()
    connection = http.client.HTTPSConnection(host, timeout=5, context=context)
    try:
        with socket.create_connection((target, 443), timeout=5) as raw:
            with context.wrap_socket(raw, server_hostname=host) as tls:
                connection.sock = tls
                path = parsed.path or "/"
                if parsed.query:
                    path += "?" + parsed.query
                connection.request("GET", path, headers={"Accept-Encoding": "identity"})
                response = connection.getresponse()
                if response.status != 200:
                    raise ValueError("证据来源拒绝请求或返回重定向")
                payload = response.read(MAX_EVIDENCE_BYTES + 1)
                if len(payload) > MAX_EVIDENCE_BYTES:
                    raise ValueError("证据响应超过 1 MiB")
                return payload
    finally:
        connection.close()
