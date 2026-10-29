import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { ApiError } from '../api/client'
import { monitorApi } from '../api/monitor'
import type {
  Coverage,
  EventPage,
  InventoryList,
  Overview,
  PageDetail,
  PageList,
  SitemapSource,
  Tab,
  UnknownAgent,
} from '../types'
import { dateError, healthPresentation } from '../utils/presentation'
import { useFilters } from './useFilters'
import { useSession } from './useSession'
import { useSiteSettings } from './useSiteSettings'
import { useCrawlerRules } from './useCrawlerRules'

export function useWorkspace() {
  const busy = ref(false),
    loading = ref(false),
    error = ref(''),
    dataError = ref(''),
    success = ref('')
  const filters = useFilters()
  const {
    applied,
    draftStart,
    draftEnd,
    draftCrawler,
    draftQ,
    draftStatus,
    draftVerification,
    resetFilters,
  } = filters
  const {
    site,
    domain,
    timezone,
    ipMode,
    credentials,
    copied,
    zone,
    installCommand,
    saveSite,
    generateCredentials,
    copy,
    resetSite,
  } = useSiteSettings({ attempt, error, success, refresh })
  const {
    ready,
    loggedIn,
    sessionChecked,
    username,
    currentUser,
    password,
    clear: clearSession,
    bootstrap,
    login,
    logout,
  } = useSession({
    loadSite,
    resetWorkspace,
    failure,
    attempt,
    beforeLogout: () => {
      ++requestId
      loading.value = false
    },
    missingFields: () => {
      error.value = '请填写用户名和密码'
    },
    clearError: () => { error.value = '' },
  })
  const tab = ref<Tab>('overview')

  const overview = ref<Overview | null>(null),
    recent = ref<EventPage['items']>([]),
    visits = ref<EventPage['items']>([])
  const rules = ref<Coverage[]>([]),
    unknown = ref<UnknownAgent[]>([]),
    updatedAt = ref<number | null>(null)
  const pages = ref<PageList | null>(null),
    pageDetail = ref<PageDetail | null>(null),
    directory = ref<InventoryList | null>(null)
  const selectedPath = ref(''),
    pageOffset = ref(0),
    inventoryOffset = ref(0),
    inventoryState = ref('')
  const sitemapSource = ref<SitemapSource | null>(null)
  let workspaceEpoch = 0
  watch(() => site.value?.domain, () => { sitemapSource.value = null })
  const analyticalTab = computed(() =>
    ['overview', 'details', 'pages', 'inventory'].includes(tab.value),
  )
  const filteredTab = computed(() => ['details', 'pages', 'inventory'].includes(tab.value))
  const cursor = ref<string | null>(null),
    nextCursor = ref<string | null>(null),
    previous = ref<(string | null)[]>([])
  const mainContent = ref<HTMLElement | null>(null)
  let requestId = 0,
    timer: ReturnType<typeof setInterval> | undefined
  const ruleManager = useCrawlerRules({ loggedIn, success, failure, attempt, changed: refresh, clearError: () => { error.value = '' } })
  const navigation: { id: Tab; name: string; icon: string; description: string }[] = [
    {
      id: 'overview',
      name: '访问概览',
      icon: 'chart-bar',
      description: '了解谁正在读取你的官网，以及采集器的运行状态。',
    },
    {
      id: 'pages',
      name: '页面分析',
      icon: 'layout-list',
      description: '查看哪些页面受到关注，以及爬虫和响应分布。',
    },
    {
      id: 'inventory',
      name: '内容目录',
      icon: 'world',
      description: '对照已知内容，定位指定范围内尚未观察到访问的页面。',
    },
    {
      id: 'details',
      name: '访问明细',
      icon: 'file-text',
      description: '查看每一次可识别访问，以及对应的来源核验依据。',
    },
    {
      id: 'health',
      name: '采集健康',
      icon: 'activity',
      description: '确认采集链路、数据时间与观测完整性。',
    },
    {
      id: 'site',
      name: '官网配置',
      icon: 'settings',
      description: '连接你的官网，安装一次采集器，持续观察新增访问。',
    },
    { id: 'rules', name: '爬虫规则', icon: 'shield-check', description: '维护识别规则与核验来源，保存后用于后续新增访问。' },
  ]
  const crawlerOptions = computed(() => [
    { value: '', label: '全部已识别爬虫' },
    ...rules.value
      .filter((rule) => rule.token)
      .map((rule) => ({
        value: rule.token!,
        label: (rule.name === rule.token ? rule.name : `${rule.name} · ${rule.token}`) + (rule.enabled === false ? '（已停用）' : ''),
      })),
  ])
  const verificationOptions = [
    { value: '', label: '全部核验状态' },
    { value: 'verified', label: '已核验' },
    { value: 'ua_only', label: '仅 UA 匹配' },
    { value: 'ip_mismatch', label: 'IP 不匹配' },
    { value: 'evidence_unavailable', label: '证据不可用／已过期' },
    { value: 'client_ip_unknown', label: '客户端 IP 不可确认' },
  ]
  const statusOptions = [
    { value: '', label: '全部状态码' },
    ...['2xx', '3xx', '4xx', '5xx', '200', '304', '403', '404', '500'].map((value) => ({
      value,
      label: value,
    })),
  ]
  const ipOptions = [
    { value: 'unknown', label: '还不确定（推荐）' },
    { value: 'trusted', label: '已确认是真实访问者 IP' },
  ]
  const current = computed(() => navigation.find((item) => item.id === tab.value)!)
  const health = computed(() => overview.value?.health ?? null)
  const healthState = computed(() => healthPresentation(health.value, Boolean(dataError.value)))
  const verified = computed(() =>
    overview.value ? (overview.value.verification.verified ?? 0) : null,
  )
  const verificationRate = computed(() =>
    !overview.value?.summary.requests
      ? null
      : ((verified.value! / overview.value.summary.requests) * 100).toFixed(1),
  )
  const rangeTitle = computed(() =>
    applied.value.start
      ? '自定义日期'
      : applied.value.days === 1
        ? '今天'
        : `近 ${applied.value.days} 天`,
  )
  const dateRange = computed(() => {
    const points = overview.value?.trend
    if (!points?.length) return rangeTitle.value
    const first = points[0]!.date.replaceAll('-', '/'),
      last = points.at(-1)!.date.replaceAll('-', '/')
    return first === last ? first : `${first} — ${last}`
  })
  const emptyMessage = computed(() => {
    if (dataError.value) return '数据暂时无法更新，请重试并查看上次更新时间。'
    if (
      tab.value === 'details' &&
      (applied.value.crawler ||
        applied.value.q ||
        applied.value.status ||
        applied.value.verification ||
        applied.value.path)
    )
      return `当前筛选无匹配记录。采集状态：${healthState.value.label}。`
    return overview.value?.empty_message ?? '当前范围内暂无记录，请结合采集状态和观测覆盖判断。'
  })

  function resetWorkspace() {
    ++workspaceEpoch
    ++requestId
    loading.value = false
    resetSite()
    ruleManager.reset()
    overview.value = null
    visits.value = []
    recent.value = []
    pages.value = null
    pageDetail.value = null
    directory.value = null
    sitemapSource.value = null
    selectedPath.value = ''
    pageOffset.value = 0
    inventoryOffset.value = 0
    resetFilters()
    inventoryState.value = ''
    rules.value = []
    unknown.value = []
    updatedAt.value = null
    dataError.value = ''
    copied.value = ''
    cursor.value = null
    nextCursor.value = null
    previous.value = []
  }
  function failure(err: unknown) {
    if (err instanceof ApiError && err.status === 401) {
      clearSession()
      error.value = '会话已过期，请重新登录'
      return
    }
    error.value = err instanceof Error ? err.message : '操作失败，请重试'
  }
  async function attempt(action: () => Promise<void>, expiredOnUnauthorized = true) {
    if (busy.value) return
    error.value = ''
    success.value = ''
    busy.value = true
    try {
      await action()
    } catch (err) {
      if (!expiredOnUnauthorized && err instanceof ApiError && err.status === 401)
        error.value = err.message
      else failure(err)
    } finally {
      busy.value = false
    }
  }
  function params(details = false, pageCursor = cursor.value) {
    return filters.params(details, pageCursor)
  }
  async function refresh(): Promise<'success' | 'error' | 'stale'> {
    if (!site.value || !loggedIn.value) return 'stale'
    const id = ++requestId
    const base = params(),
      detail = params(true)
    base.set('limit', '4')
    detail.set('limit', '20')
    loading.value = true
    try {
      const listParams = params(true, null)
      listParams.set('offset', String(pageOffset.value))
      const inventoryParams = params(true, null)
      inventoryParams.set('offset', String(inventoryOffset.value))
      inventoryParams.set('state', inventoryState.value)
      const detailParams = params(true, null)
      if (selectedPath.value) detailParams.set('path', selectedPath.value)
      const [summary, latest, records, capabilities, hints, pageRows, inspected, inventoryRows, sitemap] =
        await Promise.all([
          monitorApi.overview(params()),
          monitorApi.events(base),
          monitorApi.events(detail),
          monitorApi.crawlers(),
          monitorApi.unknown(),
          tab.value === 'pages' ? monitorApi.pages(listParams) : Promise.resolve(null),
          tab.value === 'pages' && selectedPath.value
            ? monitorApi.pageDetail(detailParams)
            : Promise.resolve(null),
          tab.value === 'inventory' ? monitorApi.inventory(inventoryParams) : Promise.resolve(null),
          tab.value === 'inventory' ? monitorApi.sitemap() : Promise.resolve(null),
        ])
      if (id !== requestId || !loggedIn.value) return 'stale'
      overview.value = summary
      recent.value = latest.items
      visits.value = records.items
      nextCursor.value = records.next_cursor
      rules.value = capabilities.rules
      unknown.value = hints.items
      updatedAt.value = Date.now() / 1000
      dataError.value = ''
      if (pageRows) pages.value = pageRows
      if (inspected) pageDetail.value = inspected
      if (inventoryRows) directory.value = inventoryRows
      if (sitemap) sitemapSource.value = sitemap
      return 'success'
    } catch (err) {
      if (id !== requestId) return 'stale'
      if (err instanceof ApiError && err.status === 401) failure(err)
      else dataError.value = err instanceof Error ? err.message : '数据更新失败'
      return 'error'
    } finally {
      if (id === requestId) loading.value = false
    }
  }
  async function loadSite() {
    site.value = await monitorApi.site()
    if (site.value) {
      domain.value = site.value.domain
      timezone.value = site.value.timezone
      ipMode.value = site.value.client_ip_mode
      tab.value = 'overview'
      await refresh()
    } else tab.value = 'site'
  }
  async function navigate(target: Tab) {
    if (!site.value && !['site', 'rules'].includes(target)) return
    tab.value = target
    success.value = ''
    error.value = ''
    await nextTick()
    mainContent.value?.focus({ preventScroll: true })
    window.scrollTo({ top: 0, behavior: 'instant' })
    if (target === 'rules') await ruleManager.load()
    else if (site.value && target !== 'site') await refresh()
  }
  function clearQueryResults() {
    overview.value = null
    recent.value = []
    visits.value = []
    cursor.value = null
    nextCursor.value = null
    previous.value = []
    pages.value = null
    pageDetail.value = null
    directory.value = null
    pageOffset.value = 0
    inventoryOffset.value = 0
  }
  async function selectDays(days: number) {
    applied.value = { ...applied.value, days, start: '', end: '' }
    draftStart.value = ''
    draftEnd.value = ''
    clearQueryResults()
    await refresh()
  }
  async function filter() {
    const validation =
      dateError(draftStart.value, draftEnd.value) ||
      (draftStatus.value && !/^[1-5](xx|[0-9]{2})$/.test(draftStatus.value)
        ? '请输入 100–599 状态码或 1xx–5xx 类别'
        : '')
    if (validation) {
      error.value = validation
      return
    }
    error.value = ''
    applied.value = {
      ...applied.value,
      start: draftStart.value,
      end: draftEnd.value,
      crawler: draftCrawler.value,
      q: draftQ.value,
      status: draftStatus.value,
      verification: draftVerification.value,
    }
    clearQueryResults()
    await refresh()
  }
  async function next() {
    if (!nextCursor.value || loading.value) return
    const prior = cursor.value
    cursor.value = nextCursor.value
    const result = await refresh()
    if (result === 'success') previous.value.push(prior)
    else if (result === 'error') cursor.value = prior
  }
  async function back() {
    if (!previous.value.length || loading.value) return
    const prior = cursor.value
    cursor.value = previous.value.at(-1) ?? null
    const result = await refresh()
    if (result === 'success') previous.value.pop()
    else if (result === 'error') cursor.value = prior
  }
  async function openPage(path: string) {
    selectedPath.value = path
    pageDetail.value = null
    applied.value.path = ''
    pageOffset.value = 0
    if (tab.value === 'pages') await refresh()
    else await navigate('pages')
    if (tab.value === 'pages' && selectedPath.value === path) {
      await nextTick()
      document
        .querySelector('.page-inspector')
        ?.scrollIntoView({ block: 'start', behavior: 'instant' })
    }
  }
  async function openRecords(path = '', crawler = '') {
    if (!path) {
      draftCrawler.value = crawler
      draftQ.value = ''
      draftStatus.value = ''
      draftVerification.value = ''
      applied.value = { ...applied.value, crawler, q: '', status: '', verification: '', path: '' }
    } else applied.value.path = path
    cursor.value = null
    nextCursor.value = null
    previous.value = []
    visits.value = []
    await navigate('details')
  }
  async function changePage(offset: number, inventory = false) {
    if (loading.value) return
    const target = inventory ? inventoryOffset : pageOffset,
      prior = target.value
    target.value = offset
    if ((await refresh()) === 'error') target.value = prior
  }
  async function changeInventoryState(state: string) {
    inventoryState.value = state
    inventoryOffset.value = 0
    directory.value = null
    await refresh()
  }
  async function importDirectory(text: string, format: string) {
    const generation = workspaceEpoch, host = site.value?.domain
    let imported = false
    await attempt(async () => {
      const result = await monitorApi.importInventory(text, format)
      if (generation !== workspaceEpoch || !loggedIn.value || host !== site.value?.domain) return
      imported = true
      success.value = `导入完成：新增 ${result.added} 页，更新 ${result.updated} 页，目录共 ${result.total} 页。`
      inventoryOffset.value = 0
      directory.value = null
      await refresh()
    })
    return imported && generation === workspaceEpoch && loggedIn.value && host === site.value?.domain
  }
  async function saveSitemap(url: string, enabled: boolean) {
    const generation = workspaceEpoch, host = site.value?.domain
    let saved = false
    await attempt(async () => {
      const result = await monitorApi.saveSitemap(url, enabled)
      if (generation !== workspaceEpoch || !loggedIn.value || host !== site.value?.domain) return
      saved = true
      sitemapSource.value = result
      success.value = enabled ? 'Sitemap 已保存，后台已安排同步；请查看同步结果。' : 'Sitemap 已保存，自动同步已暂停，目录保持保留。'
      await refresh()
    })
    return saved && generation === workspaceEpoch && loggedIn.value && host === site.value?.domain
  }
  async function syncSitemap() {
    const generation = workspaceEpoch, host = site.value?.domain
    await attempt(async () => {
      const result = await monitorApi.syncSitemap()
      if (generation !== workspaceEpoch || !loggedIn.value || host !== site.value?.domain) return
      sitemapSource.value = result
      success.value = 'Sitemap 同步已排队，结果会自动更新。'
      await refresh()
    })
  }
  async function removeDirectory(path: string) {
    await attempt(async () => {
      await monitorApi.removeInventory(path)
      success.value = '已从内容目录移除；访问日志保持保留。'
      inventoryOffset.value = 0
      await refresh()
    })
  }
  async function exportCsv() {
    await attempt(async () => {
      const id = requestId,
        blob = await monitorApi.exportEvents(params(true, null))
      if (id !== requestId || !loggedIn.value) return
      const url = URL.createObjectURL(blob),
        link = document.createElement('a')
      link.href = url
      link.download = 'crawler-visits.csv'
      document.body.append(link)
      link.click()
      link.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
      success.value = 'CSV 已生成，包含当前已应用条件下的全部记录（最多 10,000 条）。'
    })
  }
  function visibleRefresh() {
    if (!document.hidden && loggedIn.value && !busy.value)
      void (tab.value === 'rules' ? ruleManager.load() : refresh())
  }
  onMounted(() => {
    void bootstrap()
    timer = setInterval(() => {
      if (loggedIn.value && !busy.value && !loading.value && !document.hidden)
        void (tab.value === 'rules' ? ruleManager.load() : refresh())
    }, 30000)
    document.addEventListener('visibilitychange', visibleRefresh)
  })
  onUnmounted(() => {
    ++requestId
    if (timer) clearInterval(timer)
    document.removeEventListener('visibilitychange', visibleRefresh)
  })

  function closePage() {
    ++requestId
    selectedPath.value = ''
    pageDetail.value = null
    loading.value = false
  }

  return {
    ruleManager,
    ready,
    loggedIn,
    sessionChecked,
    username,
    currentUser,
    password,
    busy,
    loading,
    error,
    dataError,
    success,
    site,
    domain,
    timezone,
    ipMode,
    overview,
    recent,
    visits,
    rules,
    unknown,
    updatedAt,
    applied,
    draftStart,
    draftEnd,
    draftCrawler,
    draftQ,
    draftStatus,
    draftVerification,
    pages,
    pageDetail,
    directory,
    sitemapSource,
    saveSitemap,
    syncSitemap,
    selectedPath,
    pageOffset,
    inventoryOffset,
    inventoryState,
    analyticalTab,
    filteredTab,
    cursor,
    nextCursor,
    previous,
    credentials,
    copied,
    mainContent,
    navigation,
    crawlerOptions,
    verificationOptions,
    statusOptions,
    ipOptions,
    current,
    health,
    zone,
    healthState,
    verified,
    verificationRate,
    dateRange,
    installCommand,
    emptyMessage,
    bootstrap,
    login,
    logout,
    navigate,
    refresh,
    filter,
    selectDays,
    clearQueryResults,
    next,
    back,
    openPage,
    openRecords,
    changePage,
    changeInventoryState,
    importDirectory,
    removeDirectory,
    exportCsv,
    saveSite,
    generateCredentials,
    copy,
    closePage,
    tab,
  }
}
