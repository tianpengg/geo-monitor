<script setup lang="ts">
import { useWorkspaceContext } from '../../composables/workspaceContext'
import UiInput from '../ui/UiInput.vue'
import UiSelect from '../ui/UiSelect.vue'
import UiDatePicker from '../ui/UiDatePicker.vue'

const { busy, loading, applied, draftStart, draftEnd, draftCrawler, draftQ, draftStatus, draftVerification, analyticalTab, filteredTab, crawlerOptions, verificationOptions, statusOptions, zone, refresh, filter, clearQueryResults } = useWorkspaceContext()

function cancelExactPage() {
  applied.value.path = ''
  clearQueryResults()
  void refresh()
}
</script>

<template>
  <form
    v-if="analyticalTab"
    novalidate
    class="filter-bar"
    :class="{ 'expanded-filter': filteredTab }"
    @submit.prevent="filter"
  >
    <label
      >开始日期<UiDatePicker v-model="draftStart" :timezone="zone" aria-label="开始日期" /></label
    ><span class="filter-separator">—</span
    ><label
      >结束日期<UiDatePicker v-model="draftEnd" :timezone="zone" aria-label="结束日期"
    /></label>
    <label v-if="filteredTab" class="crawler-filter"
      >爬虫<UiSelect
        v-model="draftCrawler"
        :options="crawlerOptions"
        searchable
        aria-label="筛选爬虫"
    /></label>
    <template v-if="filteredTab"
      ><label class="path-search"
        >路径搜索<UiInput
          v-model="draftQ"
          type="search"
          icon="search"
          clearable
          maxlength="200"
          placeholder="输入路径片段"
          aria-label="路径搜索" /></label
      ><label
        >状态码<UiSelect
          v-model="draftStatus"
          :options="statusOptions"
          editable
          placeholder="全部 / 403 / 4xx"
          aria-label="筛选状态码" /></label
      ><label
        >来源核验<UiSelect
          v-model="draftVerification"
          :options="verificationOptions"
          aria-label="筛选核验状态" /></label
    ></template>
    <button class="secondary-button" :disabled="busy || loading">查询</button
    ><span v-if="applied.start" class="filter-caption">已应用自定义日期</span>
    <span v-if="filteredTab && applied.path" class="exact-path"
      >精确页面：{{ applied.path }}
      <button
        type="button"
        class="text-button"
        @click="cancelExactPage"
      >
        取消精确页面
      </button></span
    >
  </form>
</template>
