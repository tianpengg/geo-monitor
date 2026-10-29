import { computed, ref, type Ref } from 'vue'
import { monitorApi } from '../api/monitor'
import type { CrawlerRule } from '../types'
import { editableRule, ruleDraft, rulePayload, searchRules } from '../utils/crawlerRules'

type Callbacks = {
  loggedIn: Ref<boolean>
  success: Ref<string>
  failure: (error: unknown) => void
  attempt: (action: () => Promise<void>) => Promise<void>
  changed: () => Promise<unknown>
  clearError: () => void
}
export function useCrawlerRules(callbacks: Callbacks) {
  const items = ref<CrawlerRule[]>([]), loading = ref(false), loaded = ref(false), query = ref('')
  const draft = ref(ruleDraft()), revision = ref<number | undefined>(), editing = ref(false)
  const editorOpen = ref(false)
  const shown = computed(() => searchRules(items.value, query.value))
  let epoch = 0, requestId = 0
  function reset() {
    ++epoch; ++requestId
    items.value = []; loading.value = false; loaded.value = false; query.value = ''
    draft.value = ruleDraft(); revision.value = undefined; editing.value = false; editorOpen.value = false
  }
  function edit(rule?: CrawlerRule) {
    callbacks.clearError()
    draft.value = ruleDraft(rule); revision.value = rule?.revision; editing.value = Boolean(rule)
    editorOpen.value = true
  }
  function closeEditor() {
    editorOpen.value = false
    draft.value = ruleDraft(); revision.value = undefined; editing.value = false
    callbacks.clearError()
  }
  async function load() {
    const id = ++requestId
    loading.value = true
    try {
      const response = await monitorApi.crawlerRules()
      if (id !== requestId || !callbacks.loggedIn.value) return
      items.value = response.items; loaded.value = true
    } catch (error) {
      if (id === requestId && callbacks.loggedIn.value) callbacks.failure(error)
    } finally { if (id === requestId) loading.value = false }
  }
  async function save() {
    const generation = epoch
    await callbacks.attempt(async () => {
      await monitorApi.saveCrawlerRule(rulePayload(draft.value, revision.value), editing.value)
      if (generation !== epoch || !callbacks.loggedIn.value) return
      closeEditor()
      callbacks.success.value = '规则已保存，将用于下一批新增请求；历史记录不回算。'
      await load(); await callbacks.changed()
    })
  }
  async function toggle(rule: CrawlerRule) {
    const generation = epoch
    await callbacks.attempt(async () => {
      await monitorApi.saveCrawlerRule({ ...editableRule(rule), enabled: !rule.enabled }, true)
      if (generation !== epoch || !callbacks.loggedIn.value) return
      callbacks.success.value = rule.enabled ? '规则已停用，历史记录仍可查询。' : '规则已启用。'
      await load(); await callbacks.changed()
    })
  }
  async function refreshEvidence(rule: CrawlerRule) {
    const generation = epoch
    await callbacks.attempt(async () => {
      const updated = await monitorApi.refreshCrawlerEvidence(rule.token)
      if (generation !== epoch || !callbacks.loggedIn.value) return
      callbacks.success.value = updated.evidence_state === 'available'
        ? '证据已刷新；后续请求将按此清单核验。' : '证据未能更新，请检查来源地址、格式与网络；识别仍会继续。'
      await load()
    })
  }
  return { items, loading, loaded, query, draft, revision, editing, editorOpen, shown, edit, closeEditor, load, save, toggle, refreshEvidence, reset }
}
