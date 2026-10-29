#!/usr/bin/env bash
# Run from the uploaded source tree. No host Python/Node installation is needed.
set +x
set -euo pipefail
umask 077

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
project_root="$(cd -- "$script_dir/.." && pwd -P)"
env_file="$project_root/deploy/.env"
public_url="${GEO_PUBLIC_URL:-}"
admin_user="${GEO_ADMIN_USERNAME:-admin}"
admin_password="${GEO_ADMIN_PASSWORD:-}"
port="${GEO_PORT:-}"
non_interactive=false
explicit_values=false
temporary_env=''

fail() {
  printf '部署失败：%s\n' "$*" >&2
  if [[ -f "$env_file" ]]; then
    printf '查看日志：docker compose --env-file %q -f %q logs --tail=100 monitor\n' "$env_file" "$project_root/deploy/compose.yaml" >&2
  fi
  exit 1
}
cleanup() { if [[ -n "$temporary_env" && -f "$temporary_env" ]]; then rm -f -- "$temporary_env"; fi; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

usage() {
  cat <<'HELP'
用法：
  bash scripts/deploy.sh
  bash scripts/deploy.sh --public-url http://192.0.2.10:8000
  bash scripts/deploy.sh --public-url https://monitor.example.com --port 8000
  bash scripts/deploy.sh --non-interactive --env-file /path/to/deploy.env
  bash scripts/deploy.sh --collector SERVER_URL SITE_ID SOURCE_ID

选项：
  --public-url URL      后台 HTTP / HTTPS 地址（不带路径）
  --port PORT           主机监听端口；HTTP 默认跟随地址端口，HTTPS 默认 8000
  --admin-user USER     管理员账号，默认 admin
  --env-file FILE       配置文件，默认项目 deploy/.env
  --non-interactive    无交互模式，首次部署需通过环境变量提供密码和地址
  --collector          转交已有采集器安装流程，按提示输入日志路径及采集凭据
  -h, --help           显示说明

密码只从隐藏终端或 GEO_ADMIN_PASSWORD 环境变量输入，不接受密码参数。
已有配置自动复用；如需更改，请编辑原配置后重新执行，不会删除数据卷。
HTTP 可直接访问 IP 和端口，会明文传输密码、会话、采集凭据和上报数据。
HTTPS 证书、反向代理和官网日志由管理员配置，脚本不修改防火墙。
HELP
}

valid_url() {
  local pattern='^https?://([a-zA-Z0-9][a-zA-Z0-9.-]*|\[[0-9a-fA-F:]+\])(:([0-9]{1,5}))?/?$'
  [[ "$1" =~ $pattern ]] || return 1
  local address_port="${BASH_REMATCH[3]:-}"
  [[ -z "$address_port" ]] || (( 10#$address_port >= 1 && 10#$address_port <= 65535 ))
}

if [[ "${1:-}" == '--collector' ]]; then
  [[ "$#" -eq 4 ]] || fail '采集器模式需要后台地址、网站标识和来源标识。'
  valid_url "$2" || fail '后台地址必须是无路径的 HTTP 或 HTTPS 地址。'
  [[ "$3" =~ ^[a-zA-Z0-9_-]{1,100}$ && "$4" =~ ^[a-zA-Z0-9_-]{1,100}$ ]] || fail '网站或来源标识无效。'
  [[ "$(uname -s)" == Linux ]] || fail '请在官网所在的 Linux 服务器运行。'
  exec bash "$script_dir/install-collector.sh" "$2" "$3" "$4"
fi

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --public-url|--port|--admin-user|--env-file)
      [[ "$#" -ge 2 && -n "$2" ]] || fail "$1 缺少值。"
      case "$1" in
        --public-url) public_url="$2"; explicit_values=true ;;
        --port) port="$2"; explicit_values=true ;;
        --admin-user) admin_user="$2"; explicit_values=true ;;
        --env-file) env_file="$2" ;;
      esac
      shift 2 ;;
    --non-interactive) non_interactive=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail '未知参数，请运行 --help；密码不能作为命令行参数。' ;;
  esac
done

[[ "$(uname -s)" == Linux ]] || fail '请在安装了 Docker 的 Linux / 1Panel 服务器运行。'
for required in pyproject.toml uv.lock README.md deploy/compose.yaml deploy/server.Dockerfile \
  deploy/collector.Dockerfile deploy/collector.compose.yaml internal/server/app.py \
  internal/collector/runtime.py cmd/server/main.py cmd/collector/main.py \
  web/package.json web/package-lock.json web/src/App.vue; do
  [[ -f "$project_root/$required" ]] || fail "源码不完整，缺少 $required；请上传整个项目源码。"
done
command -v docker >/dev/null || fail '未找到 Docker，请先在 1Panel 安装并启动 Docker。'
docker compose version >/dev/null 2>&1 || fail '需要可用的 Docker Compose v2。'
docker info >/dev/null 2>&1 || fail '无法连接 Docker，请检查服务状态和当前用户权限。'

[[ -n "$env_file" && "$env_file" != *$'\n'* && "$env_file" != *$'\r'* ]] || fail '配置文件路径无效。'
mkdir -p -- "$(dirname -- "$env_file")"
env_file="$(cd -- "$(dirname -- "$env_file")" && pwd -P)/$(basename -- "$env_file")"
[[ ! -L "$env_file" ]] || fail '配置文件不能是符号链接。'

ask() {
  [[ "$non_interactive" == false ]] || fail '首次无交互部署需设置 GEO_PUBLIC_URL 和 GEO_ADMIN_PASSWORD。'
  IFS= read -r -p "$2" "$1" </dev/tty || fail '无法读取终端，请使用 --non-interactive 和环境变量。'
}

dotenv_value() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//\$/\$\$}"
  printf '"%s"' "$value"
}

if [[ -e "$env_file" ]]; then
  [[ -f "$env_file" ]] || fail '配置路径不是普通文件。'
  [[ "$explicit_values" == false ]] || fail '已有配置不会被参数覆盖；请编辑原配置后重跑。'
  printf '复用现有配置：%s（保留密码、域名及数据卷）\n' "$env_file"
else
  [[ -n "$public_url" ]] || ask public_url '监测后台地址，例如 http://服务器IP:8000 或 https://monitor.example.com：'
  valid_url "$public_url" || fail '后台地址必须是无路径、无账号信息的 HTTP 或 HTTPS 地址。'
  public_url="${public_url%/}"
  cookie_secure=true
  bind_address=127.0.0.1
  default_port=8000
  if [[ "$public_url" == http://* ]]; then
    cookie_secure=false
    bind_address=0.0.0.0
    default_port=80
    if [[ "${public_url#http://}" =~ :([0-9]+)$ ]]; then default_port="${BASH_REMATCH[1]}"; fi
  fi
  if [[ -z "$port" ]]; then
    if [[ "$non_interactive" == false ]]; then ask port "主机端口 [$default_port]："; fi
    port="${port:-$default_port}"
  fi
  [[ "$port" =~ ^[0-9]{1,5}$ ]] || fail '端口必须为 1–65535 的整数。'
  (( 10#$port >= 1 && 10#$port <= 65535 )) || fail '端口必须为 1–65535。'
  port="$((10#$port))"
  [[ ${#admin_user} -ge 1 && ${#admin_user} -le 100 && "$admin_user" != *$'\n'* && "$admin_user" != *$'\r'* ]] || fail '管理员账号长度或格式无效。'
  if [[ -z "$admin_password" ]]; then
    [[ "$non_interactive" == false ]] || fail '请通过 GEO_ADMIN_PASSWORD 环境变量提供管理员密码。'
    IFS= read -r -s -p '管理员密码（12–1024 个字符，隐藏输入）：' admin_password </dev/tty || fail '无法读取密码。'
    printf '\n'
    IFS= read -r -s -p '再次输入管理员密码：' confirm_password </dev/tty || fail '无法读取密码。'
    printf '\n'
    [[ "$admin_password" == "$confirm_password" ]] || fail '两次密码不一致。'
    unset confirm_password
  fi
  [[ ${#admin_password} -ge 12 && ${#admin_password} -le 1024 && "$admin_password" != *$'\n'* && "$admin_password" != *$'\r'* ]] || fail '密码需为 12–1024 个字符，且不能包含换行。'
  temporary_env="$(mktemp "${env_file}.tmp.XXXXXX")"
  {
    printf 'GEO_ADMIN_USERNAME='; dotenv_value "$admin_user"; printf '\n'
    printf 'GEO_ADMIN_PASSWORD='; dotenv_value "$admin_password"; printf '\n'
    printf 'GEO_PUBLIC_URL='; dotenv_value "$public_url"; printf '\n'
    printf 'GEO_COOKIE_SECURE=%s\nGEO_BIND_ADDRESS=%s\nGEO_PORT=%s\n' "$cookie_secure" "$bind_address" "$port"
  } > "$temporary_env"
  # A hard link publishes a complete file atomically and refuses replacement.
  ln -- "$temporary_env" "$env_file" 2>/dev/null || fail '配置文件已出现或无法创建；没有覆盖已有文件。'
  rm -f -- "$temporary_env"
  temporary_env=''
  printf '已创建受限配置：%s\n' "$env_file"
fi
chmod 600 -- "$env_file"
admin_password=''
unset GEO_ADMIN_PASSWORD GEO_ADMIN_USERNAME GEO_PUBLIC_URL GEO_COOKIE_SECURE GEO_BIND_ADDRESS GEO_PORT

compose=(docker compose --env-file "$env_file" -f "$project_root/deploy/compose.yaml")
"${compose[@]}" config --quiet >/dev/null 2>&1 || fail 'Compose 配置无效，请检查配置文件；为保护凭据，不打印完整配置。'
if ! docker image inspect python:3.13-slim-bookworm >/dev/null 2>&1; then
  docker pull python:3.13-slim-bookworm >/dev/null || fail '无法拉取配置校验镜像，请检查镜像仓库连接。'
fi

validator="$(cat <<'PY'
import json
import sys
from urllib.parse import urlsplit

try:
    service = json.load(sys.stdin)['services']['monitor']
    # Compose config emits a reusable model and escapes literal dollars again.
    env = {key: value.replace('$$', '$') if isinstance(value, str) else value
           for key, value in service['environment'].items()}
    url = env['GEO_PUBLIC_URL']
    parsed = urlsplit(url)
    assert parsed.scheme in ('http', 'https') and parsed.hostname and parsed.username is None
    assert parsed.path in ('', '/') and not parsed.query and not parsed.fragment
    assert parsed.port is None or 1 <= parsed.port <= 65535
    assert not any(ord(char) < 32 for char in url)
    assert str(env['GEO_COOKIE_SECURE']).lower() == str(parsed.scheme == 'https').lower()
    assert 1 <= len(env['GEO_ADMIN_USERNAME']) <= 100
    assert 12 <= len(env['GEO_ADMIN_PASSWORD']) <= 1024
    assert '\n' not in env['GEO_ADMIN_PASSWORD'] and '\r' not in env['GEO_ADMIN_PASSWORD']
    ports = [port for port in service['ports'] if int(port['target']) == 8000]
    assert len(ports) == 1
    bind, port = ports[0]['host_ip'], int(ports[0]['published'])
    allowed = ('127.0.0.1', '::1') if parsed.scheme == 'https' else ('127.0.0.1', '::1', '0.0.0.0', '::')
    assert bind in allowed and 1 <= port <= 65535
    bind = {'0.0.0.0': '127.0.0.1', '::': '::1'}.get(bind, bind)
    print(url.rstrip('/'))
    print('http://' + ('[' + bind + ']' if ':' in bind else bind) + ':' + str(port))
except (AssertionError, KeyError, TypeError, ValueError):
    print('配置校验失败：请检查 HTTP(S) 地址、有效账号密码、匹配协议的 Cookie 和端口绑定；HTTPS 须本机绑定。', file=sys.stderr)
    sys.exit(2)
PY
)"
if ! addresses="$("${compose[@]}" config --format json 2>/dev/null |
  docker run --rm -i --network none python:3.13-slim-bookworm python -c "$validator")"; then
  fail '配置检查未通过或校验容器无法运行；配置和数据卷均保留。'
fi
public_url="${addresses%%$'\n'*}"
upstream="${addresses#*$'\n'}"
if [[ "$public_url" == http://* ]]; then
  printf 'HTTP 明文传输：管理员密码、会话、采集凭据和上报的原始日志未经传输加密。\n'
fi

printf '正在构建并启动控制台，首次构建需要下载依赖……\n'
"${compose[@]}" up -d --build monitor || fail '构建或启动失败，配置与数据卷保留；检查 Docker 构建输出后重跑。'
container_id="$("${compose[@]}" ps -q monitor)"
[[ -n "$container_id" ]] || fail '未找到控制台容器，请检查 Compose 状态。'
healthy=false
for ((attempt=0; attempt<60; attempt++)); do
  status="$(docker inspect --format '{{.State.Health.Status}}' "$container_id" 2>/dev/null)" || fail '控制台容器已退出或无法读取状态。'
  case "$status" in
    healthy) healthy=true; break ;;
    unhealthy) fail '控制台健康检查失败；请使用下方说明中的 Compose logs 命令排查，数据卷保留。' ;;
    starting) sleep 2 ;;
    *) fail '镜像缺少有效健康检查或容器状态异常。' ;;
  esac
done
[[ "$healthy" == true ]] || fail '等待健康检查超时（120 秒）；检查容器日志后重跑。'

printf '\n控制台容器已启动，健康检查通过。\n'
printf '后台地址：%s\n本机上游地址：%s\n' "$public_url" "$upstream"
printf '配置文件：%s（密码仅保存在此文件，不在终端展示）\n' "$env_file"
if [[ "$public_url" == http://* ]]; then
  printf '\nHTTP 无需证书或反向代理。请在 1Panel / 云防火墙放行所选端口，确认后台地址可达。\n'
  printf '如使用已有 HTTP 反向代理，请关闭代理缓存，请求体允许至少 2m。\n'
else
  printf '\n请在 1Panel 配置有效 HTTPS 证书并代理至本机上游，关闭缓存，请求体允许至少 2m。\n'
  printf '本机上游适用于 host 网络的 OpenResty；桥接模式需配置共享网络及可达上游。\n'
fi
cat <<'NEXT'

下一步：
1. 通过上述后台地址登录，配置被监测官网并生成采集凭据。
2. 在官网服务器执行后台提供的安装命令，或运行：
   bash scripts/deploy.sh --collector SERVER_URL SITE_ID SOURCE_ID
   安装时输入宿主机上的独立 Combined 日志路径及采集凭据。
容器就绪不代表公网访问或真实官网接入已经完成。
NEXT
printf '\n查看日志：docker compose --env-file %q -f %q logs --tail=100 monitor\n' "$env_file" "$project_root/deploy/compose.yaml"
