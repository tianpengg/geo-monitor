<script setup lang="ts">
import { computed, nextTick, ref, useId, watch } from 'vue'
import { useWorkspaceContext } from '../composables/workspaceContext'
import UiDialog from '../components/ui/UiDialog.vue'
import UiInput from '../components/ui/UiInput.vue'
import UiSelect from '../components/ui/UiSelect.vue'
import UiIcon from '../components/ui/UiIcon.vue'
import { time } from '../utils/presentation'

const { busy, error, zone, ruleManager } = useWorkspaceContext()
const { items, shown, query, draft, editing, revision, editorOpen, loaded, loading, edit, closeEditor, save, load, toggle, refreshEvidence } = ruleManager
const enabledCount = computed(() => items.value.filter(rule => rule.enabled).length)
const protectedIdentity = computed(() => ['Bytespider', 'HySpider'].includes(draft.value.token))
const formId = useId(), formError = ref<HTMLElement | null>(null)
const evidenceLabel: Record<string, string> = {
  available: '证据可用', unavailable: '证据待获取／不可用', expired: '证据已过期', not_configured: '仅 UA 匹配',
}
const statusOptions = [{ value: 'true', label: '启用' }, { value: 'false', label: '停用' }]
const formatOptions = [{ value: 'json', label: 'JSON IP 清单' }, { value: 'amazon-code', label: '网页中的 JSON 代码块' }]
watch(error, async (value) => {
  if (!value || !editorOpen.value) return
  await nextTick(); formError.value?.focus()
})
</script>

<template>
  <section class="panel rules-panel" aria-label="规则列表">
    <div class="rules-toolbar">
      <div class="rules-search"><UiInput v-model="query" icon="search" clearable aria-label="搜索爬虫规则" placeholder="搜索名称、UA 或运营方" /></div>
      <div class="rules-toolbar-actions">
        <span class="rules-count" aria-live="polite"><template v-if="loaded">{{ items.length }} 条规则<span class="rules-count-divider">/</span>{{ enabledCount }} 条启用</template><template v-else>正在读取规则</template></span>
        <button class="secondary-button" :disabled="busy || loading" @click="load"><UiIcon name="refresh" />刷新</button>
        <button class="primary-button" :disabled="busy" @click="edit()"><UiIcon name="plus" />新增规则</button>
      </div>
    </div>
    <div class="rules-table-wrap" tabindex="0" role="region" aria-label="爬虫规则表格，可横向滚动">
      <table class="rules-table">
        <caption>爬虫识别规则、来源核验与管理操作</caption>
        <thead><tr><th scope="col">爬虫名称</th><th scope="col">UA 匹配词</th><th scope="col">运营方 / 归属</th><th scope="col">来源核验</th><th scope="col">状态</th><th scope="col" class="rule-operation-heading">操作</th></tr></thead>
        <tbody>
          <tr v-if="loading && !loaded"><td colspan="6" class="rules-empty" role="status">正在读取规则…</td></tr>
          <tr v-else-if="!loaded"><td colspan="6" class="rules-empty">规则尚未加载，请重试刷新。</td></tr>
          <tr v-else-if="!shown.length"><td colspan="6" class="rules-empty">没有匹配的规则。</td></tr>
          <template v-else>
            <tr v-for="rule in shown" :key="rule.token" :class="{ 'rule-is-disabled': !rule.enabled }">
              <td class="rule-name-cell"><strong>{{ rule.name }}</strong><span>{{ rule.origin === 'builtin' ? '内置' : '自定义' }} · {{ rule.token }}</span></td>
              <td class="rule-token-cell"><code>{{ rule.match_token }}</code><span>{{ rule.version }}</span></td>
              <td class="rule-operator-cell"><strong>{{ rule.operator }}</strong><span>{{ rule.product_attribution }}</span></td>
              <td class="rule-evidence-cell"><span :class="['rule-evidence-label', { 'is-available': rule.evidence_state === 'available' }]">{{ evidenceLabel[rule.evidence_state] ?? '核验状态待确认' }}</span><small>{{ rule.evidence_fetched_at ? time(rule.evidence_fetched_at, zone) : '尚无证据更新时间' }}</small></td>
              <td><span :class="['badge', rule.enabled ? 'neutral' : 'warning']">{{ rule.enabled ? '已启用' : '已停用' }}</span></td>
              <td><div class="rule-table-actions">
                <button class="text-button" :disabled="busy" :aria-label="`编辑 ${rule.token}`" @click="edit(rule)">编辑</button>
                <button class="text-button rule-toggle" :disabled="busy" :aria-label="`${rule.enabled ? '停用' : '启用'} ${rule.token}`" @click="toggle(rule)">{{ rule.enabled ? '停用' : '启用' }}</button>
                <button class="text-button" :disabled="busy || !rule.enabled || !rule.evidence_url" :aria-label="`刷新 ${rule.token} 核验证据`" @click="refreshEvidence(rule)">刷新核验</button>
              </div></td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
    <div class="rules-table-footer"><span>{{ loaded ? `显示 ${shown.length} / ${items.length} 条规则` : '等待加载' }}</span><span>变更仅作用于后续请求，历史记录不回算。</span></div>
  </section>

  <UiDialog :open="editorOpen" :title="editing ? '编辑规则' : '新增规则'" :description="editing ? `当前修订 ${revision} · 规则标识保持固定` : '添加一个爬虫身份，保存后用于后续新增访问。'" :busy="busy" @close="closeEditor">
    <form :id="formId" class="stack-form rule-form" novalidate @submit.prevent="save">
      <p v-if="error" ref="formError" class="notice danger rule-wide" role="alert" tabindex="-1">{{ error }}</p>
      <label>显示名称<UiInput v-model="draft.name" aria-label="显示名称" placeholder="示例搜索爬虫" :disabled="busy || protectedIdentity" maxlength="100" required /></label>
      <label>运营方<UiInput v-model="draft.operator" aria-label="运营方" placeholder="平台名称" :disabled="busy || protectedIdentity" maxlength="100" required /></label>
      <label>规则标识<UiInput v-model="draft.token" aria-label="规则标识" placeholder="ExampleBot" :disabled="busy || editing" maxlength="100" required /><small>创建后固定，用于历史记录和筛选。</small></label>
      <label>UA 匹配词<UiInput v-model="draft.match_token" aria-label="UA 匹配词" placeholder="ExampleBot" :disabled="busy" maxlength="100" required /><small>匹配完整词，忽略大小写；不填版本号或正则。</small></label>
      <label>产品归属说明<UiInput v-model="draft.product_attribution" aria-label="产品归属说明" :disabled="busy || protectedIdentity" maxlength="200" required /><small v-if="protectedIdentity">保留该身份已确认的展示与未确认产品归属口径。</small></label>
      <label>启用状态<UiSelect v-model="draft.enabled" :options="statusOptions" aria-label="规则启用状态" :disabled="busy" /></label>
      <div class="rule-form-section rule-wide"><h3>来源核验<span>可选</span></h3><p>没有官方证据时只按 UA 识别。</p></div>
      <label class="rule-wide">官方 IP 证据地址<UiInput v-model="draft.evidence_url" type="url" aria-label="官方 IP 证据地址" placeholder="https://platform.example/bot-ips.json" :disabled="busy" maxlength="1024" /></label>
      <label>证据解析格式<UiSelect v-model="draft.evidence_format" :options="formatOptions" aria-label="证据解析格式" :disabled="busy" /></label>
      <label>官方资料地址<UiInput v-model="draft.documentation_url" type="url" aria-label="官方资料地址" placeholder="https://platform.example/bots" :disabled="busy" maxlength="1024" /></label>
      <p class="notice neutral rule-wide">仅接受公网 HTTPS 证据。更换来源后旧证据失效，保存后可在表格刷新核验；核验源的官方适用性由管理员确认，不代表内容被训练或引用。</p>
    </form>
    <template #footer><button type="button" class="secondary-button" :disabled="busy" @click="closeEditor">取消</button><button type="submit" class="primary-button" :form="formId" :disabled="busy">{{ busy ? '正在保存…' : editing ? '保存修改' : '创建规则' }}</button></template>
  </UiDialog>
</template>
