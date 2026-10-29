import { computed, ref, type Ref } from 'vue'
import { monitorApi } from '../api/monitor'
import type { Site, Credentials } from '../types'
import { collectorInstallCommand } from '../utils/installation'

type Callbacks = {
  attempt: (action: () => Promise<void>) => Promise<void>
  error: Ref<string>
  success: Ref<string>
  refresh: () => Promise<unknown>
}
export function useSiteSettings(callbacks: Callbacks) {
  const site = ref<Site | null>(null),
    domain = ref(''),
    timezone = ref('Asia/Shanghai'),
    ipMode = ref('unknown')
  const credentials = ref<Credentials | null>(null),
    copied = ref('')
  const zone = computed(() => site.value?.timezone ?? 'Asia/Shanghai')
  const installCommand = computed(() =>
    credentials.value ? collectorInstallCommand(credentials.value) : '',
  )
  async function saveSite() {
    if (!domain.value.trim() || !timezone.value.trim()) {
      callbacks.error.value = '请填写官网域名和统计时区'
      return
    }
    await callbacks.attempt(async () => {
      site.value = await monitorApi.saveSite(domain.value, timezone.value, ipMode.value)
      domain.value = site.value.domain
      timezone.value = site.value.timezone
      ipMode.value = site.value.client_ip_mode
      callbacks.success.value = '官网配置已保存'
      await callbacks.refresh()
    })
  }
  async function generateCredentials() {
    await callbacks.attempt(async () => {
      credentials.value = await monitorApi.credentials()
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
    site.value = null
    credentials.value = null
    copied.value = ''
  }
  return {
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
  }
}
