#!/usr/bin/env bash
set -euo pipefail
install_root="${1:?Usage: collector-control.sh INSTALL_ROOT stop|reconnect|check}"
action="${2:?Missing action}"
install_root="$(cd -- "$install_root" && pwd -P)"
source "$install_root/collector-env.sh"
export GEO_COLLECTOR_CONFIG="$install_root/collector.json"
compose=(docker compose -p geo-monitor-collector -f "$install_root/deploy/collector.compose.yaml")
case "$action" in
  stop) "${compose[@]}" stop collector ;;
  reconnect) "${compose[@]}" up -d --no-build --force-recreate collector ;;
  check) "${compose[@]}" run --rm collector --config /config/collector.json --check ;;
  *) echo 'Allowed actions: stop, reconnect, check' >&2; exit 2 ;;
esac
