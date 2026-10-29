"""Exercise the actual Bash entry point and Compose's dotenv parser on Linux."""

import hashlib
import json
import os
import platform
import select
import shutil
import signal
import ssl
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

if platform.system() == "Linux":
    import pty

ROOT = Path(__file__).resolve().parents[3]
BASH = shutil.which("bash")
DOCKER = shutil.which("docker-real") or shutil.which("docker")
pytestmark = pytest.mark.skipif(
    platform.system() != "Linux" or not BASH or not DOCKER,
    reason="deployment script regression requires Linux Bash and Compose CLI",
)


@pytest.fixture
def deployment(tmp_path):
    project = tmp_path / "project"
    required = [
        "pyproject.toml",
        "uv.lock",
        "README.md",
        "deploy/compose.yaml",
        "deploy/server.Dockerfile",
        "deploy/collector.Dockerfile",
        "deploy/collector.compose.yaml",
        "internal/server/app.py",
        "internal/collector/runtime.py",
        "cmd/server/main.py",
        "cmd/collector/main.py",
        "web/package.json",
        "web/package-lock.json",
        "web/src/App.vue",
        "scripts/deploy.sh",
        "scripts/install-collector.sh",
    ]
    for name in required:
        target = project / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    tools = tmp_path / "tools"
    tools.mkdir()
    fake = tools / "docker"
    fake.write_text(
        f"#!{sys.executable}\n"
        + r"""import json, os, subprocess, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ['DEPLOY_CALLS'], 'a') as output:
    output.write(json.dumps(args) + '\n')
if args[0] == 'info':
    sys.exit(1 if os.environ.get('DEPLOY_FAIL') == 'info' else 0)
if args[0] in ('image', 'pull'):
    sys.exit(0)
if args[0] == 'run':
    sys.exit(subprocess.call([sys.executable, '-c', args[-1]]))
if args[0] == 'inspect':
    print('unhealthy' if os.environ.get('DEPLOY_FAIL') == 'health' else 'healthy')
    sys.exit(0)
if args[0] == 'compose':
    if 'version' in args: sys.exit(0)
    if 'config' in args:
        sys.exit(subprocess.call([os.environ['DEPLOY_REAL_DOCKER'], *args]))
    if 'up' in args: sys.exit(1 if os.environ.get('DEPLOY_FAIL') == 'build' else 0)
    if 'ps' in args: print('synthetic-monitor'); sys.exit(0)
sys.exit(2)
""",
        encoding="utf-8",
    )
    fake.chmod(0o700)
    env = os.environ | {
        "PATH": str(tools) + os.pathsep + os.environ["PATH"],
        "DEPLOY_CALLS": str(tmp_path / "calls.jsonl"),
        "DEPLOY_REAL_DOCKER": DOCKER,
        "GEO_PUBLIC_URL": "https://monitor.example.test",
        "GEO_ADMIN_PASSWORD": "synthetic-deploy-password-2026",
        "GEO_ADMIN_USERNAME": "synthetic-admin",
        "GEO_PORT": "18080",
        "COMPOSE_PROJECT_NAME": "geo-monitor-deploy-unit",
    }
    return project, env


def run(deployment, *args, **changes):
    project, env = deployment
    return subprocess.run(
        [BASH, str(project / "scripts/deploy.sh"), *args],
        env=env | changes,
        capture_output=True,
        text=True,
        timeout=45,
    )


def calls(deployment):
    path = Path(deployment[1]["DEPLOY_CALLS"])
    return [json.loads(row) for row in path.read_text().splitlines()] if path.exists() else []


def test_help_and_invalid_password_flag_do_not_invoke_docker(deployment):
    assert run(deployment, "--help").returncode == 0
    result = run(deployment, "--password", "do-not-echo-this-password")
    assert result.returncode != 0
    assert "do-not-echo-this-password" not in result.stdout + result.stderr
    assert calls(deployment) == []


@pytest.mark.parametrize(
    "password",
    [
        "plain-synthetic-password-2026",
        "Synthetic $dollar ${HOME} # space and \"double\" 'single'",
        "Synthetic\\path\\with\\slashes\\",
        "Synthetic\\'mixed\\\"quotes$and${GEO_PORT}",
        "a" * 12 + "$" * 1012,
    ],
)
def test_first_deployment_preserves_password_and_permissions(deployment, password):
    result = run(deployment, "--non-interactive", GEO_ADMIN_PASSWORD=password)
    assert result.returncode == 0, result.stderr
    path = deployment[0] / "deploy/.env"
    assert path.stat().st_mode & 0o777 == 0o600
    config = subprocess.check_output(
        [
            DOCKER,
            "compose",
            "--env-file",
            str(path),
            "-f",
            str(deployment[0] / "deploy/compose.yaml"),
            "config",
            "--environment",
        ],
        env={key: value for key, value in deployment[1].items() if not key.startswith("GEO_")},
        text=True,
    )
    # Inspect raw dotenv values; the reusable JSON model escapes dollars again.
    values = dict(row.split("=", 1) for row in config.splitlines() if "=" in row)
    assert values["GEO_ADMIN_PASSWORD"] == password
    assert password not in result.stdout + result.stderr
    assert not list(path.parent.glob(".env.tmp.*"))
    assert not any("down" in call for call in calls(deployment))


def test_repeat_reuses_file_and_ignores_inherited_secret_override(deployment):
    assert run(deployment, "--non-interactive").returncode == 0
    path = deployment[0] / "deploy/.env"
    before = path.read_bytes()
    result = run(deployment, "--non-interactive", GEO_ADMIN_PASSWORD="other-synthetic-secret")
    assert result.returncode == 0, result.stderr
    assert path.read_bytes() == before
    assert "other-synthetic-secret" not in result.stdout + result.stderr
    assert run(deployment, "--port", "19090").returncode != 0
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "address,port",
    [
        ("http://192.0.2.10:18081", "18081"),
        ("http://monitor.example.test", "80"),
        ("http://[::1]:18082/", "18082"),
    ],
)
def test_http_defaults_match_address_and_repeat_keeps_configuration(deployment, address, port):
    project, env = deployment
    env = {key: value for key, value in env.items() if key != "GEO_PORT"}
    result = run((project, env), "--non-interactive", GEO_PUBLIC_URL=address)
    assert result.returncode == 0, result.stderr
    path = project / "deploy/.env"
    before = path.read_bytes()
    assert b"GEO_COOKIE_SECURE=false\nGEO_BIND_ADDRESS=0.0.0.0\n" in before
    assert f"GEO_PORT={port}\n".encode() in before
    assert "HTTP 明文传输" in result.stdout
    assert "HTTP 无需证书或反向代理" in result.stdout
    assert f"http://127.0.0.1:{port}" in result.stdout
    assert path.stat().st_mode & 0o777 == 0o600
    assert run((project, env), "--non-interactive").returncode == 0
    assert path.read_bytes() == before
    path.write_text(path.read_text().replace("GEO_COOKIE_SECURE=false", "GEO_COOKIE_SECURE=true"))
    assert run((project, env), "--non-interactive").returncode != 0


@pytest.mark.parametrize(
    "changes",
    [
        {"GEO_PUBLIC_URL": "ftp://monitor.example.test"},
        {"GEO_PUBLIC_URL": "http://192.0.2.10:65536"},
        {"GEO_PUBLIC_URL": "https://monitor.example.test/subpath"},
        {"GEO_PUBLIC_URL": "https://user:private@monitor.example.test"},
        {"GEO_PORT": "65536"},
        {"GEO_PORT": "08bad"},
        {"GEO_ADMIN_PASSWORD": "short"},
        {"GEO_ADMIN_PASSWORD": "synthetic\nmultiline-secret"},
    ],
)
def test_bad_inputs_fail_without_publishing_config(deployment, changes):
    result = run(deployment, "--non-interactive", **changes)
    assert result.returncode != 0
    assert not (deployment[0] / "deploy/.env").exists()
    assert "private" not in result.stdout + result.stderr


@pytest.mark.parametrize("failure", ["info", "build", "health"])
def test_failures_are_not_reported_as_success_and_do_not_delete_data(deployment, failure):
    result = run(deployment, "--non-interactive", DEPLOY_FAIL=failure)
    assert result.returncode != 0
    assert "健康检查通过" not in result.stdout
    assert deployment[1]["GEO_ADMIN_PASSWORD"] not in result.stdout + result.stderr
    assert not any("down" in call for call in calls(deployment))
    if failure != "info":
        assert (deployment[0] / "deploy/.env").is_file()


def test_symlink_config_is_rejected_without_modifying_target(deployment, tmp_path):
    target = tmp_path / "preserved.env"
    target.write_text("preserve-me")
    (deployment[0] / "deploy/.env").symlink_to(target)
    assert run(deployment, "--non-interactive").returncode != 0
    assert target.read_text() == "preserve-me"


@pytest.mark.parametrize(
    "old,new",
    [
        ("GEO_COOKIE_SECURE=true", "GEO_COOKIE_SECURE=false"),
        ("GEO_BIND_ADDRESS=127.0.0.1", "GEO_BIND_ADDRESS=0.0.0.0"),
        ("https://monitor.example.test", "http://monitor.example.test"),
    ],
)
def test_invalid_existing_production_config_is_preserved_and_rejected(deployment, old, new):
    assert run(deployment, "--non-interactive").returncode == 0
    path = deployment[0] / "deploy/.env"
    before = path.read_text().replace(old, new)
    path.write_text(before)
    previous_starts = sum("up" in call for call in calls(deployment))
    result = run(deployment, "--non-interactive")
    assert result.returncode != 0
    assert path.read_text() == before
    assert sum("up" in call for call in calls(deployment)) == previous_starts


@pytest.mark.parametrize("scheme", ["http", "https"])
def test_collector_mode_delegates_identifiers_without_changing_server_config(deployment, scheme):
    marker = deployment[0] / "handoff"
    (deployment[0] / "scripts/install-collector.sh").write_text(
        '#!/bin/bash\nprintf "%s\\n" "$@" > "$HANDOFF"\n'
    )
    result = run(
        deployment,
        "--collector",
        f"{scheme}://monitor.example.test",
        "site-1",
        "source-1",
        HANDOFF=str(marker),
    )
    assert result.returncode == 0
    assert marker.read_text().splitlines() == [
        f"{scheme}://monitor.example.test",
        "site-1",
        "source-1",
    ]
    assert not (deployment[0] / "deploy/.env").exists()


def test_interactive_password_input_is_hidden(deployment):
    project, env = deployment
    env = {key: value for key, value in env.items() if not key.startswith("GEO_")}
    password = "hidden-terminal-password-2026"
    pid, terminal = pty.fork()
    if pid == 0:
        os.execve(BASH, [BASH, str(project / "scripts/deploy.sh")], env)
    output, sent = b"", set()
    prompts = [
        ("监测后台地址", "https://monitor.example.test"),
        ("主机端口", "18080"),
        ("隐藏输入", password),
        ("再次输入管理员密码", password),
    ]
    deadline = time.monotonic() + 40
    try:
        while time.monotonic() < deadline:
            if select.select([terminal], [], [], 0.2)[0]:
                try:
                    chunk = os.read(terminal, 8192)
                except OSError:
                    break
                if not chunk:
                    break
                output += chunk
                for index, (prompt, value) in enumerate(prompts):
                    if index not in sent and prompt.encode() in output:
                        os.write(terminal, (value + "\n").encode())
                        sent.add(index)
        else:
            pytest.fail("interactive deployment timed out")
    finally:
        os.close(terminal)
        waited, status = os.waitpid(pid, os.WNOHANG)
        if not waited:
            os.kill(pid, signal.SIGTERM)
            _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 0, output.decode(errors="replace")
    assert len(sent) == 4
    assert password.encode() not in output


@pytest.mark.parametrize(
    "address",
    [
        "ftp://127.0.0.1",
        "http://user:private@127.0.0.1",
        "https://127.0.0.1/subpath",
        "http://127.0.0.1:65536",
    ],
)
def test_installer_rejects_invalid_origins_before_prompting(deployment, address):
    project, env = deployment
    result = subprocess.run(
        [BASH, str(project / "scripts/install-collector.sh"), address, "site", "source"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "private" not in result.stdout + result.stderr
    assert calls(deployment) == []


@pytest.mark.parametrize("trust_certificate", [False, True])
def test_https_installer_rejects_untrusted_certificate_and_http_redirect(
    deployment, tmp_path, trust_certificate
):
    certificate, key = tmp_path / "tls.crt", tmp_path / "tls.key"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=IP:127.0.0.1",
            "-keyout",
            str(key),
            "-out",
            str(certificate),
        ],
        check=True,
        capture_output=True,
    )
    received = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            received.append(self.server is secure)
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{plain.server_port}/downgrade")
            self.end_headers()

    plain = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    secure = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certificate, key)
    secure.socket = context.wrap_socket(secure.socket, server_side=True)
    for server in (plain, secure):
        threading.Thread(target=server.serve_forever, daemon=True).start()
    project, env = deployment
    env = {name: value for name, value in env.items() if name != "CURL_CA_BUNDLE"}
    if trust_certificate:
        env["CURL_CA_BUNDLE"] = str(certificate)
    env["GEO_INSTALL_ROOT"] = str(tmp_path / "installed")
    log = tmp_path / "access.log"
    log.touch()
    token = "hidden-synthetic-collector-token"
    pid, terminal = pty.fork()
    if pid == 0:
        os.execve(
            BASH,
            [
                BASH,
                str(project / "scripts/install-collector.sh"),
                f"https://127.0.0.1:{secure.server_port}",
                "site",
                "source",
            ],
            env,
        )
    output, sent = b"", set()
    prompts = [(b"Combined access log:", str(log)), (b"credential (hidden):", token)]
    deadline = time.monotonic() + 30
    try:
        while time.monotonic() < deadline:
            if select.select([terminal], [], [], 0.2)[0]:
                try:
                    chunk = os.read(terminal, 8192)
                except OSError:
                    break
                if not chunk:
                    break
                output += chunk
                for index, (prompt, value) in enumerate(prompts):
                    if index not in sent and prompt in output:
                        os.write(terminal, (value + "\n").encode())
                        sent.add(index)
        else:
            pytest.fail("installer transport check timed out")
    finally:
        os.close(terminal)
        waited, status = os.waitpid(pid, os.WNOHANG)
        if not waited:
            os.kill(pid, signal.SIGTERM)
            _, status = os.waitpid(pid, 0)
        for server in (plain, secure):
            server.shutdown()
            server.server_close()
    assert os.waitstatus_to_exitcode(status) != 0
    assert len(sent) == 2
    assert token.encode() not in output and b"Collector installed." not in output
    assert False not in received
    assert received == ([True] if trust_certificate else [])
    if trust_certificate:
        assert b"disabled" in output
    else:
        assert b"certificate" in output
    assert not list((tmp_path / "installed").glob("collector.*.tar.gz"))


@pytest.mark.skipif(
    not os.environ.get("GEO_DEPLOY_DOCKER_TEST_PROJECT"),
    reason="explicit isolated Docker smoke only",
)
@pytest.mark.parametrize("scheme", ["http", "https"])
def test_real_first_and_repeat_deployment_keep_login_and_data(tmp_path, scheme):
    project = os.environ["GEO_DEPLOY_DOCKER_TEST_PROJECT"]
    assert project.startswith("geo-monitor-deploy-check-") and len(project) > 32
    env_file = tmp_path / "real.env"
    password = 'Real-synthetic$with"quotes\\and-spaces 2026'
    port = subprocess.check_output(
        [
            DOCKER,
            "run",
            "--rm",
            "--network",
            "host",
            "python:3.13-slim-bookworm",
            "python",
            "-c",
            "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1]); s.close()",
        ],
        text=True,
    ).strip()
    env = os.environ | {
        "COMPOSE_PROJECT_NAME": project,
        "GEO_PUBLIC_URL": f"{scheme}://monitor.example.test",
        "GEO_ADMIN_USERNAME": "synthetic-admin",
        "GEO_ADMIN_PASSWORD": password,
        "GEO_PORT": port,
        "GEO_DEPLOY_TEST_PASSWORD": password,
    }
    compose = [
        DOCKER,
        "compose",
        "-p",
        project,
        "--env-file",
        str(env_file),
        "-f",
        str(ROOT / "deploy/compose.yaml"),
    ]
    command = [
        BASH,
        str(ROOT / "scripts/deploy.sh"),
        "--env-file",
        str(env_file),
        "--non-interactive",
    ]
    login = """import http.cookiejar, json, os, urllib.request
base=os.environ.get('GEO_DEPLOY_TEST_URL','http://127.0.0.1:8000')
data=json.dumps({'username':'synthetic-admin','password':os.environ['GEO_DEPLOY_TEST_PASSWORD']}).encode()
request=urllib.request.Request(base+'/api/auth/login',data,{'Content-Type':'application/json'})
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
response=opener.open(request)
assert response.status==200
secure=os.environ['GEO_COOKIE_SECURE']=='true'
assert ('Secure' in response.headers['Set-Cookie'])==secure
assert 'HttpOnly' in response.headers['Set-Cookie'] and 'SameSite=strict' in response.headers['Set-Cookie']
if not secure:
    assert opener.open(base+'/api/auth/me').status==200
"""
    try:
        first = subprocess.run(command, env=env, capture_output=True, text=True, timeout=600)
        assert first.returncode == 0, first.stderr[-3000:]
        assert password not in first.stdout + first.stderr
        before = hashlib.sha256(env_file.read_bytes()).hexdigest()
        container = subprocess.check_output(
            [*compose, "ps", "-q", "monitor"], env=env, text=True
        ).strip()
        subprocess.run(
            [DOCKER, "exec", "-e", "GEO_DEPLOY_TEST_PASSWORD", container, "python", "-c", login],
            env=env,
            check=True,
        )
        if scheme == "http":
            subprocess.run(
                [
                    DOCKER,
                    "run",
                    "--rm",
                    "--network",
                    "host",
                    "-e",
                    "GEO_DEPLOY_TEST_PASSWORD",
                    "-e",
                    "GEO_COOKIE_SECURE=false",
                    "-e",
                    f"GEO_DEPLOY_TEST_URL=http://127.0.0.1:{port}",
                    "python:3.13-slim-bookworm",
                    "python",
                    "-c",
                    login,
                ],
                env=env,
                check=True,
            )
        seed = "from internal.storage.database import Database; import os; db=Database(os.environ['GEO_DATABASE']);\nwith db.transaction() as c: c.execute(\"INSERT INTO site(id,source_id,domain,timezone,client_ip_mode) VALUES('preserved-site','preserved-source','example.test','Asia/Shanghai','unknown')\")"
        subprocess.run([DOCKER, "exec", container, "python", "-c", seed], check=True)
        second = subprocess.run(
            command,
            env=env | {"GEO_ADMIN_PASSWORD": "unused-inherited-override"},
            capture_output=True,
            text=True,
            timeout=600,
        )
        assert second.returncode == 0, second.stderr[-3000:]
        assert hashlib.sha256(env_file.read_bytes()).hexdigest() == before
        container = subprocess.check_output(
            [*compose, "ps", "-q", "monitor"], env=env, text=True
        ).strip()
        subprocess.run(
            [DOCKER, "exec", "-e", "GEO_DEPLOY_TEST_PASSWORD", container, "python", "-c", login],
            env=env,
            check=True,
        )
        check = "from internal.storage.database import Database; import os; db=Database(os.environ['GEO_DATABASE']);\nwith db.read() as c: assert c.execute('SELECT id FROM site').fetchone()[0]=='preserved-site'"
        subprocess.run([DOCKER, "exec", container, "python", "-c", check], check=True)
    finally:
        subprocess.run(
            [*compose, "down", "--volumes", "--remove-orphans", "--rmi", "local"],
            env=env,
            check=False,
            capture_output=True,
        )
