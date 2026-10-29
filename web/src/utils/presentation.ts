import type { Health, TrendPoint } from '../types/index'
import { validDate } from './controls.ts'

export const originNote = '数据来自源站日志，可能不包含 CDN 缓存命中或边缘拦截请求。'
export const coverageLabels: Record<string, string> = {
  observed: '已观测',
  incomplete: '部分观测',
  unobserved: '未观测',
}
export const errorLabels: Record<string, string> = {
  unreadable: '日志不可读，请检查读取权限',
  missing: '日志文件不存在',
  network: '网络连接失败',
  authentication: '采集凭据校验失败',
  protocol: '上报协议或确认位置异常',
}
export const gapLabels: Record<string, string> = {
  file_missing: '待采日志文件已丢失',
  truncated: '日志已截断',
  copytruncate_uncertain: '发生复制截断轮转，完整性受限',
  state_reset: '采集状态已重置',
}

export function number(value: number | null | undefined): string {
  return value == null ? '—' : new Intl.NumberFormat('en-US').format(value)
}

export function time(
  value: number | null | undefined,
  timezone = 'Asia/Shanghai',
  short = false,
): string {
  if (value == null) return '暂无'
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: timezone,
    ...(short ? {} : { dateStyle: 'short' as const }),
    timeStyle: 'medium',
    hour12: false,
  }).format(new Date(value * 1000))
}

export function bytes(value: number | null | undefined): string {
  if (value == null) return '未知'
  if (value < 1024) return `${value} B`
  const unit = value < 1024 ** 2 ? 'KB' : value < 1024 ** 3 ? 'MB' : 'GB'
  const divisor = unit === 'KB' ? 1024 : unit === 'MB' ? 1024 ** 2 : 1024 ** 3
  return `${Number((value / divisor).toFixed(1))} ${unit}`
}

export function verificationInfo(state: string, expiresAt?: number | null, receivedAt?: number) {
  const values: Record<string, { label: string; tone: string; explanation: string }> = {
    verified: {
      label: '已核验',
      tone: 'success',
      explanation: '请求地址与当时可用的官方来源证据匹配。',
    },
    ua_only: {
      label: '仅 UA 匹配',
      tone: 'warning',
      explanation: 'User-Agent 声明了该身份，当前没有已确认的官方来源核验规则。',
    },
    ip_mismatch: {
      label: 'IP 不匹配',
      tone: 'danger',
      explanation: '请求地址未匹配当时可用的官方证据；不能据此确认官方身份。',
    },
    evidence_unavailable: {
      label: '证据暂不可用',
      tone: 'neutral',
      explanation: '未取得可用的官方证据，当前只能保留声明身份。',
    },
    client_ip_unknown: {
      label: '客户端 IP 不可确认',
      tone: 'neutral',
      explanation: '日志是否记录真实客户端地址尚未确认，未进行官方来源确认。',
    },
  }
  if (
    state === 'evidence_unavailable' &&
    expiresAt != null &&
    receivedAt != null &&
    expiresAt <= receivedAt
  ) {
    return {
      label: '证据已过期',
      tone: 'warning',
      explanation: '核验时缓存的官方证据已过有效期，未将该请求标为已核验。',
    }
  }
  return (
    values[state] ?? {
      label: '核验状态未知',
      tone: 'neutral',
      explanation: '暂时无法解释该核验状态，请查看规则与证据。',
    }
  )
}

export function healthPresentation(health: Health | null, stale = false) {
  const overall = stale ? 'stale' : (health?.overall ?? 'unknown')
  const values: Record<string, { label: string; title: string; tone: string }> = {
    healthy: { label: '采集正常', title: '日志采集运行中', tone: 'success' },
    not_installed: { label: '待安装', title: '等待采集器连接', tone: 'neutral' },
    disconnected: { label: '采集器断连', title: '等待采集器重连', tone: 'danger' },
    backlog: { label: '正在补采', title: '正在处理积压日志', tone: 'warning' },
    error: { label: '采集异常', title: '采集需要处理', tone: 'danger' },
    degraded: { label: '完整性受限', title: '采集数据存在限制', tone: 'warning' },
    stale: { label: '状态待刷新', title: '暂时无法更新状态', tone: 'neutral' },
    unknown: { label: '状态未知', title: '等待采集状态', tone: 'neutral' },
  }
  const info = values[overall] ?? values.unknown!
  const unavailable =
    !values[overall] || ['not_installed', 'disconnected', 'stale', 'unknown'].includes(overall)
  return {
    ...info,
    description: stale
      ? '当前显示上次成功取得的数据，请重试更新。'
      : (health?.message ?? '尚未取得采集器状态。'),
    connection: unavailable ? (overall === 'disconnected' ? '已断连' : '待确认') : '已连接',
    reading: unavailable ? '待确认' : health?.state === 'read_error' ? '读取异常' : '可读取',
    processing: unavailable
      ? '待确认'
      : overall === 'error'
        ? '处理异常'
        : overall === 'backlog'
          ? '补采中'
          : health?.processed_at == null
            ? '暂无日志'
            : '已确认',
  }
}

export function observed(point: TrendPoint): boolean {
  return point.coverage !== 'unobserved' && point.requests != null
}

export function trendSegments(points: TrendPoint[]): TrendPoint[][] {
  const segments: TrendPoint[][] = []
  let current: TrendPoint[] = []
  for (const point of points) {
    if (observed(point)) current.push(point)
    else if (current.length) {
      segments.push(current)
      current = []
    }
  }
  if (current.length) segments.push(current)
  return segments
}

export function dateError(start: string, end: string): string {
  if ((start && !validDate(start)) || (end && !validDate(end)))
    return '请输入有效日期，格式为 YYYY-MM-DD'
  if (Boolean(start) !== Boolean(end)) return '请同时填写开始和结束日期'
  if (start && start > end) return '开始日期不能晚于结束日期'
  return ''
}
