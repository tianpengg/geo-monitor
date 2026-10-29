import { api, apiCsv } from './client'
import type {
  Site,
  Credentials,
  Overview,
  EventPage,
  Coverage,
  UnknownAgent,
  PageList,
  PageDetail,
  InventoryList,
  CrawlerRule,
  CrawlerRuleInput,
  SitemapSource,
} from '../types'

export const monitorApi = {
  site: () => api<Site | null>('/site'),
  saveSite: (domain: string, timezone: string, client_ip_mode: string, aliases: string[]) =>
    api<Site>('/site', {
      method: 'PUT',
      body: JSON.stringify({ domain, timezone, client_ip_mode, aliases }),
    }),
  credentials: () => api<Credentials>('/site/credentials', { method: 'POST' }),
  overview: (params: URLSearchParams) => api<Overview>(`/overview?${params}`),
  events: (params: URLSearchParams) => api<EventPage>(`/events?${params}`),
  crawlers: () => api<{ rules: Coverage[] }>('/crawlers'),
  crawlerRules: () => api<{ items: CrawlerRule[]; limit: number }>('/crawler-rules'),
  saveCrawlerRule: (payload: CrawlerRuleInput, existing = false) =>
    api<CrawlerRule>(existing ? `/crawler-rules/${encodeURIComponent(payload.token)}` : '/crawler-rules', {
      method: existing ? 'PUT' : 'POST', body: JSON.stringify(payload),
    }),
  refreshCrawlerEvidence: (token: string) =>
    api<CrawlerRule>(`/crawler-rules/${encodeURIComponent(token)}/refresh-evidence`, { method: 'POST' }),
  unknown: () => api<{ items: UnknownAgent[] }>('/unknown-agents'),
  pages: (params: URLSearchParams) => api<PageList>(`/pages?${params}`),
  pageDetail: (params: URLSearchParams) => api<PageDetail>(`/pages/detail?${params}`),
  inventory: (params: URLSearchParams) => api<InventoryList>(`/inventory?${params}`),
  sitemap: () => api<SitemapSource>('/inventory/sitemap'),
  saveSitemap: (url: string, enabled: boolean) => api<SitemapSource>('/inventory/sitemap', {
    method: 'PUT', body: JSON.stringify({ url, enabled }),
  }),
  syncSitemap: () => api<SitemapSource>('/inventory/sitemap/sync', { method: 'POST' }),
  importInventory: (text: string, format: string) =>
    api<{ added: number; updated: number; total: number }>('/inventory/import', {
      method: 'POST',
      body: JSON.stringify({ text, format }),
    }),
  removeInventory: (path: string) =>
    api(`/inventory?${new URLSearchParams({ path })}`, { method: 'DELETE' }),
  exportEvents: (params: URLSearchParams) => apiCsv(`/events/export?${params}`),
}
