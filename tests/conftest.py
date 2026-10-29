from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from internal.config import ServerConfig
from internal.protocol import batch_identity
from internal.server.app import create_app

TEST_PASSWORD = "synthetic-test-password-2026"


@pytest.fixture
def client(tmp_path):
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<html>functional UI</html>")
    config = ServerConfig(
        database=tmp_path / "data" / "monitor.sqlite3",
        admin_password=TEST_PASSWORD,
        public_url="http://testserver",
        cookie_secure=False,
        web_directory=web,
    )
    with TestClient(create_app(config, refresh_evidence=False, refresh_sitemap=False)) as client:
        yield client


@pytest.fixture
def admin(client):
    result = client.post("/api/auth/login", json={"username": "admin", "password": TEST_PASSWORD})
    assert result.status_code == 200
    client.headers["X-CSRF-Token"] = result.json()["csrf_token"]
    return client


@pytest.fixture
def source(admin):
    assert (
        admin.put(
            "/api/site", json={"domain": "example.com", "client_ip_mode": "trusted"}
        ).status_code
        == 200
    )
    return admin.post("/api/site/credentials").json()


@pytest.fixture
def make_batch(source):
    def build(
        *,
        start=0,
        count=1,
        generation="generation",
        ua="KimiBot/1.0",
        path="/article?q=secret",
        occurred_at=None,
        ip="203.0.113.99",
        status=200,
    ):
        end = start + count * 100
        return {
            "version": 1,
            "site_id": source["site_id"],
            "source_id": source["source_id"],
            "generation": generation,
            "start_offset": start,
            "end_offset": end,
            "batch_id": batch_identity(source["source_id"], generation, start, end),
            "events": [
                {
                    "offset": start + i * 100,
                    "end_offset": start + (i + 1) * 100,
                    "occurred_at": occurred_at or datetime.now(UTC).isoformat(),
                    "client_ip": ip,
                    "method": "GET",
                    "path": path,
                    "status": status,
                    "user_agent": ua,
                }
                for i in range(count)
            ],
        }

    return build


@pytest.fixture
def headers(source):
    return {"Authorization": "Bearer " + source["token"]}
