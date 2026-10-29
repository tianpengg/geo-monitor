<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, useId, watch } from 'vue'
import { readInventoryFile } from '../../utils/inventoryImport'
import UiDialog from '../ui/UiDialog.vue'
import UiFilePicker from '../ui/UiFilePicker.vue'
import UiIcon from '../ui/UiIcon.vue'

const props = defineProps<{ open: boolean; busy: boolean; error: string }>()
const emit = defineEmits<{ close: []; import: [text: string, format: string] }>()
const formId = useId(), file = ref<File | null>(null), fileError = ref(''), reading = ref(false)
const alert = ref<HTMLElement | null>(null), message = computed(() => fileError.value || props.error)
let readEpoch = 0
watch(() => props.open, () => { ++readEpoch; file.value = null; fileError.value = ''; reading.value = false })
watch(message, async value => { if (value && props.open) { await nextTick(); alert.value?.focus() } })
onUnmounted(() => { ++readEpoch })
async function upload() {
  if (props.busy || reading.value) return
  fileError.value = ''
  reading.value = true
  const epoch = readEpoch
  try {
    const result = await readInventoryFile(file.value)
    if (epoch === readEpoch && props.open) emit('import', result.text, result.format)
  } catch (error) {
    if (epoch === readEpoch && props.open) fileError.value = error instanceof Error ? error.message : '无法读取文件'
  } finally { if (epoch === readEpoch) reading.value = false }
}
</script>

<template>
  <UiDialog :open="open" title="手动导入目录" description="上传本地页面清单，合并更新并按路径去重。" :busy="busy || reading" @close="emit('close')">
    <form :id="formId" class="inventory-import-form" @submit.prevent="upload">
      <p v-if="message" ref="alert" class="notice danger" role="alert" tabindex="-1">{{ message }}</p>
      <label>目录文件<UiFilePicker v-model="file" :disabled="busy || reading" @update:model-value="fileError = ''" /></label>
      <p class="paragraph muted">支持 Sitemap urlset XML、CSV（url 或 path，可选 title）和 JSON 数组。仅接受当前官网页面，每个文件最多 1 MiB，目录最多 10,000 页；仅保存路径与标题，不访问页面正文。</p>
      <p class="notice neutral">本地 Sitemap 索引需先展开为页面文件，也可在“Sitemap 配置”中填写索引地址自动同步。</p>
      <details class="format-help"><summary><UiIcon name="chevron-right" />查看文件示例</summary><pre>CSV：
path,title
/docs/getting-started,入门指南

JSON：
["/docs/getting-started", {"path":"/products","title":"产品"}]

XML：
&lt;urlset&gt;&lt;url&gt;&lt;loc&gt;https://你的官网域名/products&lt;/loc&gt;&lt;/url&gt;&lt;/urlset&gt;</pre></details>
    </form>
    <template #footer><button type="button" class="secondary-button" :disabled="busy || reading" @click="emit('close')">取消</button><button type="submit" :form="formId" class="primary-button" :disabled="busy || reading || !file">{{ reading ? '正在读取…' : busy ? '正在导入…' : '合并导入目录' }}</button></template>
  </UiDialog>
</template>
