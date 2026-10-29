<script setup lang="ts">
import { computed, ref } from 'vue'
import { useWorkspaceContext } from '../composables/workspaceContext'
import { time } from '../utils/presentation'
import InventoryPanel from '../components/dashboard/InventoryPanel.vue'
import InventoryImportDialog from '../components/dashboard/InventoryImportDialog.vue'
import SitemapPanel from '../components/dashboard/SitemapPanel.vue'
import UiIcon from '../components/ui/UiIcon.vue'

const { busy, loading, error, directory, inventoryOffset, inventoryState, zone, openPage, changePage, changeInventoryState, importDirectory, removeDirectory, site, sitemapSource, saveSitemap, syncSitemap } = useWorkspaceContext()
const dialog = ref<'sitemap' | 'import' | null>(null)
const syncLabel = computed(() => {
  if (!sitemapSource.value) return loading.value ? '正在读取配置' : '配置尚未加载'
  return { not_configured: '尚未配置', pending: '等待同步', running: '正在同步', success: '同步成功', failed: '同步失败', paused: '自动同步已暂停' }[sitemapSource.value.state]
})
const syncNote = computed(() => {
  const source = sitemapSource.value
  if (!source?.revision) return '配置地址自动更新，或导入本地页面清单。'
  const cadence = source.enabled ? '每天自动同步' : '自动同步已暂停'
  return `${cadence} · 最近成功：${time(source.last_success_at, zone.value)}`
})
function openDialog(target: 'sitemap' | 'import') { error.value = ''; dialog.value = target }
function closeDialog() { if (!busy.value) { dialog.value = null; error.value = '' } }
async function save(url: string, enabled: boolean) { if (await saveSitemap(url, enabled)) closeDialog() }
async function upload(text: string, format: string) { if (await importDirectory(text, format)) closeDialog() }
</script>

<template>
  <section class="panel inventory-tools" aria-label="目录管理">
    <div class="inventory-sync-summary">
      <div class="inventory-sync-heading"><strong>Sitemap</strong><span :class="['badge', sitemapSource?.state === 'failed' ? 'warning' : sitemapSource?.state === 'success' ? 'success' : 'neutral']" role="status">{{ syncLabel }}</span></div>
      <p>{{ syncNote }}</p>
    </div>
    <div class="inventory-tool-actions">
      <button class="secondary-button" :disabled="busy || loading" @click="openDialog('import')"><UiIcon name="upload" />手动导入</button>
      <button class="primary-button" :disabled="busy || loading || !sitemapSource" @click="openDialog('sitemap')"><UiIcon name="refresh" />Sitemap 配置</button>
    </div>
    <p v-if="sitemapSource?.last_error" class="inventory-sync-error" role="alert">{{ sitemapSource.last_error }}。已有目录保持保留，可在“Sitemap 配置”中查看并重试。</p>
  </section>
  <InventoryPanel
    :data="directory" :timezone="zone" :loading="loading" :busy="busy"
    :offset="inventoryOffset" :state="inventoryState"
    @remove="removeDirectory" @select="openPage" @state="changeInventoryState"
    @page="changePage($event, true)"
  />
  <SitemapPanel :open="dialog === 'sitemap'" :source="sitemapSource" :host="site?.domain ?? ''" :timezone="zone" :busy="busy" :loading="loading" :error="error" @close="closeDialog" @save="save" @sync="syncSitemap" />
  <InventoryImportDialog :open="dialog === 'import'" :busy="busy" :error="error" @close="closeDialog" @import="upload" />
</template>
