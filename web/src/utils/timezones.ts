import type { SelectOption } from './controls'

const commonZones: SelectOption[] = [
  { value: 'Asia/Shanghai', label: '中国 · 北京 / 上海（北京时间）' },
  { value: 'UTC', label: 'UTC · 协调世界时' },
  { value: 'Asia/Hong_Kong', label: '中国 · 香港' },
  { value: 'Asia/Taipei', label: '中国 · 台北' },
  { value: 'Asia/Singapore', label: '新加坡' },
  { value: 'Asia/Tokyo', label: '日本 · 东京' },
  { value: 'Asia/Seoul', label: '韩国 · 首尔' },
  { value: 'Asia/Kolkata', label: '印度 · 加尔各答' },
  { value: 'Asia/Dubai', label: '阿联酋 · 迪拜' },
  { value: 'Europe/London', label: '英国 · 伦敦' },
  { value: 'Europe/Paris', label: '法国 · 巴黎' },
  { value: 'Europe/Berlin', label: '德国 · 柏林' },
  { value: 'America/New_York', label: '美国 · 纽约' },
  { value: 'America/Chicago', label: '美国 · 芝加哥' },
  { value: 'America/Denver', label: '美国 · 丹佛' },
  { value: 'America/Los_Angeles', label: '美国 · 洛杉矶' },
  { value: 'America/Toronto', label: '加拿大 · 多伦多' },
  { value: 'America/Sao_Paulo', label: '巴西 · 圣保罗' },
  { value: 'Australia/Sydney', label: '澳大利亚 · 悉尼' },
  { value: 'Pacific/Auckland', label: '新西兰 · 奥克兰' },
]

function browserZones(): string[] {
  try {
    return typeof Intl.supportedValuesOf === 'function' ? Intl.supportedValuesOf('timeZone') : []
  } catch { return [] }
}

export function timezoneOptions(current = '', catalog: readonly string[] = browserZones()): SelectOption[] {
  const options = new Map(commonZones.map(option => [option.value, { ...option }]))
  for (const value of catalog) {
    if (!options.has(value)) options.set(value, { value, label: value })
  }
  const selected = current && !options.has(current)
    ? [{ value: current, label: `当前配置 · ${current}` }]
    : []
  return [...selected, ...options.values()]
}
