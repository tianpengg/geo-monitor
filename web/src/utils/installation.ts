import type { Credentials } from '../types'

export function collectorInstallCommand(credentials: Credentials): string {
  const { server_url, site_id, source_id } = credentials
  const protocols = server_url.startsWith('https://') ? '=https' : '=http,https'
  return `install_script=$(mktemp) && curl -fsSL --proto '${protocols}' --proto-redir '${protocols}' '${server_url}/downloads/install-collector.sh' -o "$install_script" && bash "$install_script" '${server_url}' '${site_id}' '${source_id}'`
}
