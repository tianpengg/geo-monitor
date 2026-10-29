#!/usr/bin/env bash
set +x
set -euo pipefail
umask 077

server_url="${1:?Usage: install-collector.sh SERVER_URL SITE_ID SOURCE_ID}"
site_id="${2:?Missing site ID}"
source_id="${3:?Missing source ID}"
install_root="${GEO_INSTALL_ROOT:-$HOME/.local/share/geo-monitor-collector}"
url_pattern='^https?://([a-zA-Z0-9][a-zA-Z0-9.-]*|\[[0-9a-fA-F:]+\])(:([0-9]{1,5}))?/?$'
[[ "$server_url" =~ $url_pattern ]] || { echo 'Use an HTTP(S) origin without credentials or path.' >&2; exit 2; }
address_port="${BASH_REMATCH[3]:-}"
[[ -z "$address_port" ]] || (( 10#$address_port >= 1 && 10#$address_port <= 65535 )) || { echo 'Invalid server port.' >&2; exit 2; }
[[ "$site_id" =~ ^[a-zA-Z0-9_-]{1,100}$ && "$source_id" =~ ^[a-zA-Z0-9_-]{1,100}$ ]] || { echo 'Invalid site or source ID.' >&2; exit 2; }
server_url="${server_url%/}"
protocols='=https'
if [[ "$server_url" == http://* ]]; then
  protocols='=http,https'
  printf 'HTTP 明文传输：采集凭据和上报的原始日志未经传输加密。\n'
fi
command -v docker >/dev/null || { echo 'Install Docker Engine and Compose first.' >&2; exit 2; }
docker compose version >/dev/null
docker info >/dev/null

read -r -p 'Absolute path to this website Combined access log: ' log_path </dev/tty
[[ "$log_path" = /* && -f "$log_path" && -r "$log_path" ]] || { echo 'Log must be an existing readable absolute file.' >&2; exit 2; }
log_path="$(readlink -f -- "$log_path")"
read -r -s -p 'Collector credential (hidden): ' GEO_COLLECTOR_TOKEN </dev/tty
printf '\n'
[[ -n "$GEO_COLLECTOR_TOKEN" ]] || { echo 'Credential is required.' >&2; exit 2; }
mkdir -p -- "$install_root"
install_root="$(cd -- "$install_root" && pwd -P)"
archive="$(mktemp "$install_root/collector.XXXXXX.tar.gz")"
trap 'rm -f -- "$archive"' EXIT
curl -fSL --proto "$protocols" --proto-redir "$protocols" "$server_url/downloads/collector.tar.gz" -o "$archive"
tar -xzf "$archive" -C "$install_root"

export GEO_COLLECTOR_TOKEN
export GEO_SERVER_URL="$server_url" GEO_SITE_ID="$site_id" GEO_SOURCE_ID="$source_id"
export GEO_LOG_DIRECTORY="$(dirname -- "$log_path")" GEO_LOG_BASENAME="$(basename -- "$log_path")"
docker run --rm -i --user "$(id -u):$(id -g)" \
  --env GEO_COLLECTOR_TOKEN --env GEO_SERVER_URL --env GEO_SITE_ID --env GEO_SOURCE_ID \
  --env GEO_LOG_DIRECTORY --env GEO_LOG_BASENAME \
  --mount "type=bind,src=$install_root,dst=/work" python:3.13-slim-bookworm python - <<'PY'
import json, os, shlex
from pathlib import Path
os.umask(0o077)
root = Path('/work')
config = {
    'server_url': os.environ['GEO_SERVER_URL'], 'site_id': os.environ['GEO_SITE_ID'],
    'source_id': os.environ['GEO_SOURCE_ID'], 'token': os.environ['GEO_COLLECTOR_TOKEN'],
    'log_path': '/logs/' + os.environ['GEO_LOG_BASENAME'], 'state_path': '/state/state.json',
    'allow_http': os.environ['GEO_SERVER_URL'].startswith('http://'),
}
(root / 'collector.json').write_text(json.dumps(config), encoding='utf-8')
(root / 'collector-env.sh').write_text('export GEO_LOG_DIRECTORY=' + shlex.quote(os.environ['GEO_LOG_DIRECTORY']) + '\n', encoding='utf-8')
PY
unset GEO_COLLECTOR_TOKEN
export GEO_COLLECTOR_CONFIG="$install_root/collector.json"
compose_file="$install_root/deploy/collector.compose.yaml"
docker compose -p geo-monitor-collector -f "$compose_file" build collector
docker compose -p geo-monitor-collector -f "$compose_file" run --rm collector --config /config/collector.json --check
docker compose -p geo-monitor-collector -f "$compose_file" up -d --no-build
printf 'Collector installed. State is preserved in the Compose volume.\nControl: bash %q/scripts/collector-control.sh %q stop|reconnect|check\n' "$install_root" "$install_root"
