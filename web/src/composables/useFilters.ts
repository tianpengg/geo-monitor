import { ref } from 'vue'

export function useFilters() {
  const applied = ref({
    days: 7,
    start: '',
    end: '',
    crawler: '',
    q: '',
    status: '',
    verification: '',
    path: '',
  })
  const draftStart = ref(''),
    draftEnd = ref(''),
    draftCrawler = ref('')
  const draftQ = ref(''),
    draftStatus = ref(''),
    draftVerification = ref('')
  function params(details = false, pageCursor: string | null = null) {
    const value = new URLSearchParams({ days: String(applied.value.days) })
    if (applied.value.start) {
      value.set('start', applied.value.start)
      value.set('end', applied.value.end)
    }
    if (details && applied.value.crawler) value.set('crawler', applied.value.crawler)
    if (details)
      for (const field of ['q', 'status', 'verification', 'path'] as const) {
        if (applied.value[field]) value.set(field, applied.value[field])
      }
    if (details && pageCursor) value.set('cursor', pageCursor)
    return value
  }

  function resetFilters() {
    applied.value = {
      days: 7,
      start: '',
      end: '',
      crawler: '',
      q: '',
      status: '',
      verification: '',
      path: '',
    }
    draftStart.value = ''
    draftEnd.value = ''
    draftCrawler.value = ''
    draftQ.value = ''
    draftStatus.value = ''
    draftVerification.value = ''
  }
  return {
    applied,
    draftStart,
    draftEnd,
    draftCrawler,
    draftQ,
    draftStatus,
    draftVerification,
    params,
    resetFilters,
  }
}
