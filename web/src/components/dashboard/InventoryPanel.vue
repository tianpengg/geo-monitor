<script setup lang="ts">
import type { InventoryList } from '../../types/index'
import { number, time } from '../../utils/presentation'
import UiSelect from '../ui/UiSelect.vue'
defineProps<{
  data: InventoryList | null
  timezone: string
  loading: boolean
  busy: boolean
  offset: number
  state: string
}>()
defineEmits<{
  remove: [path: string]
  select: [path: string]
  state: [value: string]
  page: [offset: number]
}>()
</script>

<template>
  <section class="panel content-panel inventory-panel" :aria-busy="loading">
    <div class="section-titlebar">
      <div>
        <h2 class="section-heading">目录观察覆盖</h2>
        <p class="section-subtitle">分母为已导入目录中符合路径搜索的页面，不代表整个官网</p>
      </div>
      <label class="state-filter"
        >观察状态<UiSelect
          :model-value="state"
          :options="[
            { value: '', label: '全部目录页面' },
            { value: 'observed', label: '已观察到访问' },
            { value: 'unobserved', label: '未观察到访问' },
          ]"
          aria-label="目录观察状态"
          @update:model-value="$emit('state', $event)"
      /></label>
    </div>
    <template v-if="data"
      ><div class="mini-metrics">
        <div>
          <span>已知页面</span><strong>{{ number(data.summary.pages) }}</strong>
        </div>
        <div>
          <span>已观察页面</span><strong>{{ number(data.summary.observed) }}</strong>
        </div>
        <div>
          <span>未观察页面</span><strong>{{ number(data.summary.unobserved) }}</strong>
        </div>
        <div>
          <span>目录观察比例</span
          ><strong>{{
            data.summary.ratio === null ? '—' : (data.summary.ratio * 100).toFixed(1) + '%'
          }}</strong>
        </div>
      </div>
      <p class="notice" :class="data.observation.state === 'observed' ? 'neutral' : 'warning'">
        {{
          data.observation.note
        }}
        未观察仅表示选定日期、爬虫与响应条件下无保留记录，不代表从未抓取。
      </p>
      <div class="analysis-table-wrap">
        <table class="analysis-table">
          <thead>
            <tr>
              <th>页面</th>
              <th>观察状态</th>
              <th>请求量</th>
              <th>最近访问</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!data.items.length" class="inventory-empty-row"><td colspan="5">{{ !data.summary.pages ? '尚无符合条件的内容目录。请通过 Sitemap 配置同步或手动导入；目录为空时不计算观察比例。' : '当前观察状态下没有符合条件的页面。' }}</td></tr>
            <tr v-for="row in data.items" :key="row.path">
              <td data-label="页面">
                <button class="path-link" @click="$emit('select', row.path)">{{ row.path }}</button
                ><small v-if="row.title">{{ row.title }}</small>
              </td>
              <td data-label="观察状态">
                <span class="badge" :class="row.requests ? 'success' : 'neutral'">{{
                  row.requests ? '已观察' : '未观察'
                }}</span>
              </td>
              <td data-label="请求量">{{ number(row.requests) }}</td>
              <td data-label="最近访问">{{ time(row.last_visit, timezone) }}</td>
              <td data-label="操作">
                <button
                  class="text-button"
                  :disabled="busy || loading"
                  :aria-label="'移除目录页面 ' + row.path"
                  @click="$emit('remove', row.path)"
                >
                  移除目录
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="pagination">
        <span>第 {{ offset / 20 + 1 }} 页 · {{ data.total }} 个页面</span>
        <div>
          <button
            class="secondary-button"
            :disabled="loading || !offset"
            @click="$emit('page', Math.max(0, offset - 20))"
          >
            上一页</button
          ><button
            class="secondary-button"
            :disabled="loading || offset + 20 >= data.total"
            @click="$emit('page', offset + 20)"
          >
            下一页
          </button>
        </div>
      </div>
    </template>
    <p v-else class="empty-inline">
      {{ loading ? '正在读取目录与观测情况…' : '尚未取得目录，请刷新重试。' }}
    </p>
  </section>
</template>
