"""Local, bounded content inventories. No URL is fetched by this module."""

import csv
import io
import json
import time
from urllib.parse import urlsplit
from xml.etree import ElementTree

from internal.server.services.analytics import observation
from internal.server.services.filters import bounds, literal_like
from internal.server.services.queries import health

MAX_FILE_BYTES = 1024 * 1024
MAX_PAGES = 10000


def normalize_page(value, host, aliases=()):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError("目录地址无效或过长")
    value = value.strip()
    if "\\" in value or any(ord(char) < 32 for char in value):
        raise ValueError("目录地址含不支持的字符")
    try:
        url = urlsplit(value)
        if url.netloc or url.scheme:
            hostname = (url.hostname or "").encode("idna").decode().lower().rstrip(".")
            if (
                url.scheme not in {"http", "https"}
                or hostname not in {host, *aliases}
                or url.username is not None
                or url.password is not None
                or url.port not in {None, 443 if url.scheme == "https" else 80}
            ):
                raise ValueError("目录地址必须属于当前官网且使用标准 HTTP(S) 地址")
        elif not value.startswith("/") or value.startswith("//"):
            raise ValueError("目录需要完整同站地址或以 / 开头的路径")
        return url.path or "/"
    except (ValueError, UnicodeError):
        raise ValueError("目录含无效、非本站或不支持的地址；同站 www 等域名请先在官网配置登记别名") from None


def parse_inventory(text, format, host, aliases=()):
    if not text or len(text.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError("文件为空或超过 1 MiB")
    text = text.removeprefix("\ufeff")
    try:
        if format == "xml":
            if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
                raise ValueError("不支持 XML DTD 或实体")
            root = ElementTree.fromstring(text)
            if root.tag.split("}")[-1] != "urlset":
                raise ValueError("仅支持 urlset sitemap；请导入索引引用的实际页面文件")
            entries = []
            for child in root:
                if child.tag.split("}")[-1] != "url":
                    raise ValueError("sitemap 结构无效")
                locations = [node.text for node in child if node.tag.split("}")[-1] == "loc"]
                if len(locations) != 1:
                    raise ValueError("每个 sitemap 页面必须有一个 loc")
                entries.append(locations[0])
        elif format == "csv":
            reader = csv.DictReader(io.StringIO(text, newline=""))
            if not reader.fieldnames or not {"path", "url"}.intersection(reader.fieldnames):
                raise ValueError("CSV 需要 path 或 url 列，可选 title 列")
            entries = list(reader)
        elif format == "json":
            entries = json.loads(text)
        else:
            raise ValueError("仅支持 XML、CSV 或 JSON")
        if not isinstance(entries, list) or not entries or len(entries) > MAX_PAGES:
            raise ValueError("每次导入需要 1 至 10000 条页面")
        pages = {}
        for entry in entries:
            title = ""
            if isinstance(entry, dict):
                value = entry.get("path") or entry.get("url")
                title = entry.get("title") or ""
                if None in entry:  # csv row wider than its header
                    raise ValueError("CSV 列数无效")
            else:
                value = entry
            if not isinstance(title, str) or len(title) > 300 or any(ord(c) < 32 for c in title):
                raise ValueError("页面标题无效或超过 300 字符")
            pages[normalize_page(value, host, aliases)] = title
        return pages
    except (ElementTree.ParseError, json.JSONDecodeError, csv.Error, RecursionError):
        raise ValueError("文件格式无效，请检查 XML、CSV 或 JSON 内容") from None


def import_pages(database, site, text, format):
    pages = parse_inventory(text, format, site["domain"], site.get("aliases", ()))
    with database.transaction() as conn:
        assert_current_site(conn, site)
        return merge_pages(conn, site, pages)


def assert_current_site(conn, site):
    row = conn.execute("SELECT domain,aliases FROM site WHERE id=?", (site["id"],)).fetchone()
    if (
        not row or row["domain"] != site["domain"]
        or json.loads(row["aliases"]) != list(site.get("aliases", ()))
    ):
        raise ValueError("官网或别名配置已变更，请刷新后重试")


def merge_pages(conn, site, pages, *, preserve_titles=False):
    before = conn.execute(
        "SELECT COUNT(*) FROM content_pages WHERE site_id=? AND host=?",
        (site["id"], site["domain"]),
    ).fetchone()[0]
    title = "content_pages.title" if preserve_titles else "excluded.title"
    now = time.time()
    conn.executemany(
        f"""INSERT INTO content_pages VALUES(?,?,?,?,?) ON CONFLICT(site_id,host,path)
        DO UPDATE SET title={title},imported_at=excluded.imported_at""",
        [(site["id"], site["domain"], path, name, now) for path, name in pages.items()],
    )
    total = conn.execute(
        "SELECT COUNT(*) FROM content_pages WHERE site_id=? AND host=?",
        (site["id"], site["domain"]),
    ).fetchone()[0]
    if total > MAX_PAGES:
        raise ValueError("目录总量超过 10000 条，请先移除不需要的页面")
    return {
        "accepted": len(pages),
        "added": total - before,
        "updated": len(pages) - (total - before),
        "total": total,
    }


def remove_page(database, site, path):
    path = normalize_page(path, site["domain"], site.get("aliases", ()))
    with database.transaction() as conn:
        deleted = conn.execute(
            "DELETE FROM content_pages WHERE site_id=? AND host=? AND path=?",
            (site["id"], site["domain"], path),
        ).rowcount
    return {"removed": bool(deleted)}


def inventory_list(database, site, filters, state="", limit=20, offset=0, timeout=90):
    where, values = filters.where(site)
    conditions = "c.site_id=? AND c.host=?"
    parameters = [site["id"], site["domain"]]
    if filters.q:
        conditions += " AND c.path LIKE ? ESCAPE '\\'"
        parameters.append(literal_like(filters.q))
    if filters.path:
        conditions += " AND c.path=?"
        parameters.append(filters.path)
    cte = f"""WITH activity AS (SELECT path,COUNT(*) requests,MAX(occurred_at) last_visit
        FROM events WHERE {where} GROUP BY path), directory AS (
        SELECT c.path,c.title,c.imported_at,COALESCE(a.requests,0) requests,a.last_visit
        FROM content_pages c LEFT JOIN activity a ON c.path=a.path WHERE {conditions}) """
    params = [*values, *parameters]
    selected = (
        " WHERE requests>0"
        if state == "observed"
        else " WHERE requests=0"
        if state == "unobserved"
        else ""
    )
    with database.read() as conn:
        conn.execute("BEGIN")
        summary = dict(
            conn.execute(
                cte + "SELECT COUNT(*) pages,COALESCE(SUM(requests>0),0) observed FROM directory",
                params,
            ).fetchone()
        )
        total = conn.execute(cte + "SELECT COUNT(*) FROM directory" + selected, params).fetchone()[
            0
        ]
        items = [
            dict(row)
            for row in conn.execute(
                cte + "SELECT * FROM directory" + selected + " ORDER BY path LIMIT ? OFFSET ?",
                (*params, limit, offset),
            )
        ]
    summary["unobserved"] = summary["pages"] - summary["observed"]
    summary["ratio"] = summary["observed"] / summary["pages"] if summary["pages"] else None
    first, stop = bounds(site["timezone"], filters.days, filters.start, filters.end)
    return {
        "items": items,
        "summary": summary,
        "total": total,
        "observation": observation(health(database, site["source_id"], timeout), first, stop),
        "host": site["domain"],
        "timezone": site["timezone"],
    }
