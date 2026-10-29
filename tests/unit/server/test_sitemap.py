import gzip
import http.server
import socket
import ssl
import threading
import time
from unittest.mock import MagicMock

import pytest

from internal.server.services import sitemap


def urlset(*urls):
    return ("<urlset>" + "".join(f"<url><loc>{url}</loc></url>" for url in urls) + "</urlset>").encode()


def index(*urls):
    return ("<sitemapindex>" + "".join(f"<sitemap><loc>{url}</loc></sitemap>" for url in urls)
            + "</sitemapindex>").encode()


def test_index_gzip_deduplicates_paths_and_fetches_only_sitemap_files():
    files = {
        "https://example.com/map.xml": index("https://example.com/a.xml", "http://example.com/b.gz"),
        "https://example.com/a.xml": urlset("https://example.com/page?q=1", "/other"),
        "http://example.com/b.gz": gzip.compress(urlset("https://example.com/page#section")),
    }
    fetch = MagicMock(side_effect=lambda url, host, deadline: files[url])
    pages, count = sitemap.collect_pages("https://example.com/map.xml", "example.com", fetch)
    assert pages == {"/page": "", "/other": ""} and count == 3
    assert [call.args[0] for call in fetch.call_args_list] == list(files)


def test_explicit_aliases_cover_sources_children_and_pages_with_actual_fetch_hosts():
    files = {
        "https://www.example.com/map.xml": index("https://example.com/a.xml", "https://www.example.com/b.xml"),
        "https://example.com/a.xml": urlset("https://example.com/page"),
        "https://www.example.com/b.xml": urlset("https://www.example.com/page?q=1", "https://www.example.com/other"),
    }
    fetch = MagicMock(side_effect=lambda url, host, deadline: files[url])
    pages, count = sitemap.collect_pages(
        "https://www.example.com/map.xml", "example.com", fetch, aliases=["www.example.com"],
    )
    assert pages == {"/page": "", "/other": ""} and count == 3
    assert [(call.args[0], call.args[1]) for call in fetch.call_args_list] == [
        (url, "www.example.com" if "//www." in url else "example.com") for url in files
    ]
    with pytest.raises(sitemap.SitemapError):
        sitemap.collect_pages("https://www.example.com/map.xml", "example.com", fetch)
    with pytest.raises(sitemap.SitemapError):
        sitemap.collect_pages("https://example.com/map.xml", "example.com",
                              lambda *args: urlset("https://sub.example.com/foreign"),
                              aliases=["www.example.com"])


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "http://127.0.0.1/map.xml", "https://evil.example/map.xml",
    "https://name:secret@example.com/map.xml", "https://example.com:444/map.xml",
    "https://example.com/map.xml#frag", "https://example.com/\nmap.xml", "//example.com/map.xml",
])
def test_bad_source_url_never_downloads(url):
    fetch = MagicMock()
    with pytest.raises(sitemap.SitemapError):
        sitemap.collect_pages(url, "example.com", fetch)
    fetch.assert_not_called()


@pytest.mark.parametrize("payload", [
    b"<html>login</html>", b"<urlset><url/></urlset>", b"<urlset/>", b"broken",
    b'<!DOCTYPE urlset [<!ENTITY secret "hidden">]><urlset/>',
    gzip.compress(b" " * (sitemap.MAX_FILE_BYTES + 1)), b"\x1f\x8bnot-gzip",
    b"x" * (sitemap.MAX_FILE_BYTES + 1),
])
def test_bad_or_oversize_document_is_rejected(payload):
    with pytest.raises(sitemap.SitemapError):
        sitemap.xml_document(payload)


@pytest.mark.parametrize("mode", ["foreign", "nested", "cycle", "too_many", "pages", "total", "deadline"])
def test_whole_sitemap_job_bounds(monkeypatch, mode):
    first = "https://example.com/map.xml"
    second = "https://example.com/child.xml"
    files = {first: index(second), second: urlset("/a")}
    if mode == "foreign":
        files[first] = index(second, "https://evil.example/map.xml")
    elif mode == "nested":
        files[second] = index(first)
    elif mode == "cycle":
        files[first] = index(first)
    elif mode == "too_many":
        files[first] = index(*(f"https://example.com/{n}.xml" for n in range(20)))
    elif mode == "pages":
        files[second] = urlset(*(["/same"] * 10001))
    elif mode == "total":
        monkeypatch.setattr(sitemap, "MAX_TOTAL_BYTES", 50)
    else:
        monkeypatch.setattr(sitemap, "TASK_SECONDS", -1)
    fetch = MagicMock(side_effect=lambda url, host, deadline: files[url])
    with pytest.raises(sitemap.SitemapError):
        sitemap.collect_pages(first, "example.com", fetch)
    if mode == "foreign":
        assert fetch.call_count == 1  # Validate all child hosts before downloading any child.


@pytest.mark.parametrize("host", ["example.com", "www.example.com"])
@pytest.mark.parametrize("address", ["127.0.0.1", "169.254.169.254", "10.0.0.1", "::1", "224.0.0.1"])
def test_dns_private_target_rejected_before_connection(monkeypatch, address, host):
    monkeypatch.setattr(sitemap.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", (address, 80))])
    connector = MagicMock()
    monkeypatch.setattr(sitemap.socket, "create_connection", connector)
    with pytest.raises(sitemap.SitemapError):
        sitemap.download(f"http://{host}/map.xml", host, time.monotonic() + 60)
    connector.assert_not_called()


@pytest.mark.parametrize("host", ["example.com", "www.example.com"])
@pytest.mark.parametrize("mode", ["http", "https", "redirect", "oversize", "certificate"])
def test_network_pins_public_ip_tls_hostname_and_size(monkeypatch, mode, host):
    resolver = MagicMock(return_value=[(2, 1, 6, "", ("8.8.8.8", 80))])
    monkeypatch.setattr(sitemap.socket, "getaddrinfo", resolver)
    raw, tls, context, connection = MagicMock(), MagicMock(), MagicMock(), MagicMock()
    context.wrap_socket.return_value = tls
    connector = MagicMock(return_value=raw)
    monkeypatch.setattr(sitemap.socket, "create_connection", connector)
    monkeypatch.setattr(sitemap.ssl, "create_default_context", lambda: context)
    monkeypatch.setattr(sitemap.http.client, "HTTPConnection", lambda *a, **k: connection)
    response = connection.getresponse.return_value
    response.length = None
    response.status = 302 if mode == "redirect" else 200
    response.read1.side_effect = [b"x" * (sitemap.MAX_FILE_BYTES + 1), b""] if mode == "oversize" else [b"xml", b""]
    if mode == "certificate":
        context.wrap_socket.side_effect = ssl.SSLCertVerificationError("not trusted")
    secure = mode != "http"
    url = f"{'https' if secure else 'http'}://{host}/map.xml?v=1"
    if mode in {"redirect", "oversize", "certificate"}:
        with pytest.raises((ValueError, ssl.SSLCertVerificationError)):
            sitemap.download(url, host, time.monotonic() + 60)
    else:
        assert sitemap.download(url, host, time.monotonic() + 60) == b"xml"
        assert connection.request.call_args.args == ("GET", "/map.xml?v=1")
        assert connection.request.call_args.kwargs["headers"]["Accept-Encoding"] == "identity"
    assert connector.call_args.args == (("8.8.8.8", 443 if secure else 80),)
    resolver.assert_called_once_with(host, 443 if secure else 80, type=socket.SOCK_STREAM)
    if secure:
        context.wrap_socket.assert_called_once_with(raw, server_hostname=host)
    else:
        context.wrap_socket.assert_not_called()
    connection.close.assert_called_once()


@pytest.mark.parametrize("mode", ["length", "close", "incomplete"])
def test_real_http10_closed_connections_and_incomplete_body(monkeypatch, mode):
    payload = urlset("/actual")

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            if mode != "close":
                self.send_header("Content-Length", str(len(payload) + (10 if mode == "incomplete" else 0)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    worker.start()
    monkeypatch.setattr(sitemap.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("8.8.8.8", 80))])

    def local_connection(address, timeout):
        assert address == ("8.8.8.8", 80)
        # Connect a test-only real socket without using the patched DNS resolver.
        stream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        stream.settimeout(timeout)
        stream.connect(server.server_address)
        return stream

    monkeypatch.setattr(sitemap.socket, "create_connection", local_connection)
    try:
        if mode == "incomplete":
            with pytest.raises(sitemap.SitemapError, match="不完整"):
                sitemap.download("http://example.com/map.xml", "example.com", time.monotonic() + 60)
        else:
            assert sitemap.download("http://example.com/map.xml", "example.com", time.monotonic() + 60) == payload
    finally:
        server.shutdown()
        server.server_close()
        worker.join(1)
