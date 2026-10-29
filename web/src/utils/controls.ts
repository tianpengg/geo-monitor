export type SelectOption = { value: string; label: string }

export function matchingOptions(options: SelectOption[], query: string): SelectOption[] {
  const needle = query.trim().toLocaleLowerCase()
  return options.filter((item) =>
    `${item.label} ${item.value}`.toLocaleLowerCase().includes(needle),
  )
}

export function validDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000')) return false
  const parsed = new Date(`${value}T12:00:00Z`)
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value
}

export function todayDate(timezone: string, now = new Date()): string {
  const parts = new Intl.DateTimeFormat('en', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(now)
  const part = (name: string) => parts.find((item) => item.type === name)!.value
  return `${part('year').padStart(4, '0')}-${part('month')}-${part('day')}`
}

export function shiftDate(value: string, days: number): string {
  const date = new Date(`${value}T12:00:00Z`)
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

export function shiftMonth(value: string, amount: number): string {
  const date = new Date(`${value}T12:00:00Z`),
    day = date.getUTCDate()
  date.setUTCDate(1)
  date.setUTCMonth(date.getUTCMonth() + amount)
  const end = new Date(date)
  end.setUTCMonth(end.getUTCMonth() + 1)
  end.setUTCDate(0)
  date.setUTCDate(Math.min(day, end.getUTCDate()))
  return date.toISOString().slice(0, 10)
}

export function monthDays(value: string): { value: string; day: number; current: boolean }[] {
  const first = `${value.slice(0, 7)}-01`,
    weekday = new Date(`${first}T12:00:00Z`).getUTCDay()
  const start = shiftDate(first, -(weekday + 6) % 7)
  return Array.from({ length: 42 }, (_, index) => {
    const date = shiftDate(start, index)
    return {
      value: date,
      day: Number(date.slice(8)),
      current: date.slice(0, 7) === value.slice(0, 7),
    }
  })
}
