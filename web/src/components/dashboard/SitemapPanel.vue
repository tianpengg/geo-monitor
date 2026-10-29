<script setup lang="ts">
import { computed, nextTick, ref, useId, watch } from 'vue'
import type { SitemapSource } from '../../types'
import { number, time } from '../../utils/presentation'
import UiDialog from '../ui/UiDialog.vue'
import UiInput from '../ui/UiInput.vue'
import UiSelect from '../ui/UiSelect.vue'
import UiIcon from '../ui/UiIcon.vue'

const props = defineProps<{
  open: boolean
  source: SitemapSource | null
  host: string
  timezone: string
  busy: boolean
  loading: boolean
  error: string
}>()
const emit = defineEmits<{ close: []; save: [url: string, enabled: boolean]; sync: [] }>()
const formId = useId(), url = ref(''), enabled = ref('true'), alert = ref<HTMLElement | null>(null)
watch(() => props.open, open => {
  url.value = open ? props.source?.url ?? '' : ''
  enabled.value = open && props.source?.revision ? String(props.source.enabled) : 'true'
})
watch(() => props.error, async value => {
  if (value && props.open) { await nextTick(); alert.value?.focus() }
})
const active = computed(() => ['pending', 'running'].includes(props.source?.state ?? ''))
const syncLabel = computed(() => ({ not_configured: '尚未配置', pending: '等待同步', running: '正在同步', success: '同步成功', failed: '同步失败', paused: '自动同步已暂停' }[props.source?.state ?? 'not_configured']))
const unavailable = computed(() => props.busy || props.loading || !props.source)
</script>

<template>
  <UiDialog :open="open" title="Sitemap 配置" description="配置官网清单地址，后台持续合并更新页面。" :busy="busy" @close="emit('close')">
    <form :id="formId" class="sitemap-form" @submit.prevent="emit('save', url.trim(), enabled === 'true')">
      <p v-if="error" ref="alert" class="notice danger" role="alert" tabindex="-1">{{ error }}</p>
      <label>官网 Sitemap 地址<UiInput v-model="url" type="url" aria-label="官网 Sitemap 地址" :placeholder="`https://${host}/sitemap.xml`" :disabled="unavailable" maxlength="2048" required /></label>
      <label class="sitemap-frequency">自动同步<UiSelect v-model="enabled" aria-label="Sitemap 自动同步" :options="[{value:'true',label:'每天自动同步'}, {value:'false',label:'暂停自动同步'}]" :disabled="unavailable" /></label>
      <p class="section-subtitle sitemap-note">支持当前官网同主机的 HTTP / HTTPS、普通 Sitemap、单层索引和 gzip。启用后每 24 小时同步一次；仅合并页面，保留已有标题，不自动删除旧页面。</p>
    </form>
    <template v-if="source && source.revision">
      <div class="sitemap-dialog-status"><span>已保存配置的同步状态</span><span :class="['badge', source.state === 'failed' ? 'warning' : source.state === 'success' ? 'success' : 'neutral']" role="status">{{ syncLabel }}</span></div>
      <div class="sitemap-status-grid">
        <div><span>最近尝试</span><strong>{{ time(source.last_attempt_at, timezone) }}</strong></div>
        <div><span>最近成功</span><strong>{{ time(source.last_success_at, timezone) }}</strong></div>
        <div><span>下次自动同步</span><strong>{{ !source.enabled ? '已暂停' : active ? '本次完成后安排' : time(source.next_run_at, timezone) }}</strong></div>
        <div><span>上次成功清单</span><strong>{{ source.pages === null ? '—' : `${number(source.pages)} 页 · ${source.files} 个文件` }}</strong></div>
      </div>
      <p v-if="source.last_error" class="notice danger sitemap-error" role="alert">{{ source.last_error }}。已有目录与最后成功结果保持保留。</p>
      <div class="sitemap-actions"><p class="section-subtitle">已保存地址：<span>{{ source.url }}</span></p><button type="button" class="secondary-button" :disabled="unavailable || active" @click="emit('sync')"><UiIcon name="refresh" />{{ active ? '等待同步完成' : '立即同步' }}</button></div>
    </template>
    <details class="format-help sitemap-help"><summary><UiIcon name="chevron-right" />同步范围与限制</summary><p class="paragraph muted">最多 20 个文件（包含索引），单文件下载及解压后各 1 MiB，累计解压 10 MiB，最多 10,000 页。不会访问页面正文；拒绝内网、跨站、跳转及无效 XML。失败后保留目录并按周期重试。手动移除但仍在 Sitemap 的页面，下次同步会重新加入；暂停不删除目录。立即同步使用已保存地址，状态随页面自动刷新。</p></details>
    <template #footer><button type="button" class="secondary-button" :disabled="busy" @click="emit('close')">取消</button><button type="submit" :form="formId" class="primary-button" :disabled="unavailable || !url.trim()">{{ busy ? '正在处理…' : enabled === 'true' ? '保存并同步' : '保存配置' }}</button></template>
  </UiDialog>
</template>
