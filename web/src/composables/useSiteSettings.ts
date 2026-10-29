import { computed, ref, type Ref } from 'vue'
import { monitorApi } from '../api/monitor'
import type { Site, Credentials } from '../types'
import { collectorInstallCommand } from '../utils/installation'
import { parseSiteAliases } from '../utils/siteAliases'

type Callbacks = {
  attempt: (action: () => Promise<void>) => Promise<void>
  error: Ref<string>
  success: Ref<string>
  refresh: () => Promise<unknown>
}
export function useSiteSettings(callbacks: Callbacks) {
  const site = ref<Site | null>(null),
    domain = ref(''),
    aliasDomains = ref(''),
    timezone = ref('Asia/Shanghai'),
    ipMode = ref('unknown')
  const credentials = ref<Credentials | null>(null),
    copied = ref('')
  let epoch = 0
  const zone = computed(() => site.value?.timezone ?? 'Asia/Shanghai')
  const installCommand = computed(() =>
    credentials.value ? collectorInstallCommand(credentials.value) : '',
  )
  async function saveSite() {
    if (!domain.value.trim() || !timezone.value.trim()) {
      callbacks.error.value = '请填写官网域名和统计时区'
      return
    }
    let aliases: string[]
    try { aliases = parseSiteAliases(aliasDomains.value) }
    catch (error) { callbacks.error.value = (error as Error).message; return }
    const generation = epoch
    await callbacks.attempt(async () => {
      try {
        const saved = await monitorApi.saveSite(domain.value, timezone.value, ipMode.value, aliases)
        if (generation !== epoch) return
        site.value = saved
        domain.value = saved.domain
        aliasDomains.value = (saved.aliases ?? []).join('\n')
        timezone.value = saved.timezone
        ipMode.value = saved.client_ip_mode
        callbacks.success.value = '官网配置已保存'
        await callbacks.refresh()
      } catch (error) { if (generation === epoch) throw error }
    })
  }
  async function generateCredentials() {
    const generation = epoch
    await callbacks.attempt(async () => {
      const result = await monitorApi.credentials()
      if (generation !== epoch) return
      credentials.value = result
      copied.value = ''
      callbacks.success.value = '新凭据已生成，请在离开页面前保存并更新采集器。'
    })
  }
  async function copy(value: string, target: string) {
    await callbacks.attempt(async () => {
      if (!navigator.clipboard) throw new Error('当前浏览器无法访问剪贴板，请手动复制下方内容')
      await navigator.clipboard.writeText(value)
      copied.value = target
    })
  }

  function resetSite() {
    ++epoch
    site.value = null
    domain.value = ''
    aliasDomains.value = ''
    timezone.value = 'Asia/Shanghai'
    ipMode.value = 'unknown'
    credentials.value = null
    copied.value = ''
  }
  return {
    site,
    domain,
    aliasDomains,
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
  }
}
