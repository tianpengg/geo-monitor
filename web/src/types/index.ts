export type Tab = 'overview' | 'pages' | 'inventory' | 'details' | 'health' | 'site' | 'rules'
export type Site = {
  id: string
  source_id: string
  domain: string
  timezone: string
  client_ip_mode: string
  aliases: string[]
}
export type Session = { username: string; csrf_token: string }
export type Gap = {
  id: string
  reason: string
  detected_at: number
  start_offset: number | null
  end_offset: number | null
}
export type Health = {
  overall: string
  message: string
  heartbeat_at?: number | null
  baseline_at?: number | null
  log_received_at?: number | null
  processed_at?: number | null
  state?: string
  error_code?: string | null
  pending_bytes?: number | null
  parse_errors?: number | null
  gaps: Gap[]
  origin_note: string
}
export type Visit = {
  id: string
  occurred_at: number
  received_at: number
  path: string
  method: string
  status: number
  crawler: string
  name: string
  verification: string
  product_attribution: string
  rule_version: string
  evidence_source: string | null
  evidence_fetched_at: number | null
  evidence_expires_at?: number | null
}
export type TrendPoint = { date: string; requests: number | null; coverage: string }
export type Overview = {
  summary: { requests: number; pages: number; last_visit: number | null }
  crawlers: { crawler: string; name: string; requests: number; pages: number; last_visit: number }[]
  verification: Record<string, number>
  trend: TrendPoint[]
  health: Health
  empty_message: string | null
  timezone: string
}
export type Coverage = {
  enabled?: boolean
  token?: string | null
  name: string
  coverage: string
  product_attribution?: string
  documentation_url?: string | null
  rule_version?: string
  reviewed_at?: string
}
export type CrawlerRuleInput = {
  token: string
  match_token: string
  name: string
  operator: string
  product_attribution: string
  evidence_url: string | null
  documentation_url: string | null
  evidence_format: 'json' | 'amazon-code'
  enabled: boolean
  revision?: number
}
export type CrawlerRule = CrawlerRuleInput & {
  origin: 'builtin' | 'custom'
  revision: number
  version: string
  updated_at: number
  evidence_state: string
  evidence_fetched_at: number | null
}
export type Credentials = { server_url: string; site_id: string; source_id: string; token: string }
export type UnknownAgent = { hint: string; request_count: number; last_seen_at: number }
export type EventPage = { items: Visit[]; next_cursor: string | null }
export type Observation = { state: string; note: string }
export type PageRow = {
  path: string
  requests: number
  verified: number
  successful: number
  crawlers: number
  last_visit: number
}
export type PageList = {
  items: PageRow[]
  total: number
  summary: { requests: number; pages: number; verified: number }
}
export type PageDetail = {
  path: string
  summary: { requests: number; verified: number; last_visit: number | null }
  crawlers: { crawler: string; name: string; requests: number }[]
  statuses: { status: number; requests: number }[]
  trend: TrendPoint[]
  observation: Observation
}
export type InventoryList = {
  items: {
    path: string
    title: string
    imported_at: number
    requests: number
    last_visit: number | null
  }[]
  total: number
  summary: { pages: number; observed: number; unobserved: number; ratio: number | null }
  observation: Observation
  host: string
}
export type SitemapSource = {
  host: string
  url: string
  enabled: boolean
  revision: number
  state: 'not_configured' | 'pending' | 'running' | 'success' | 'failed' | 'paused'
  last_attempt_at: number | null
  last_success_at: number | null
  next_run_at: number | null
  last_error: string | null
  pages: number | null
  files: number | null
  added: number | null
  interval_seconds: number
}
