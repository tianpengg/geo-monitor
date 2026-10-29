<script setup lang="ts">
import type { PageDetail, PageList } from '../../types/index'
import { number, time } from '../../utils/presentation'
import TrendChart from './TrendChart.vue'
defineProps<{
  data: PageList | null
  detail: PageDetail | null
  selected: string
  timezone: string
  loading: boolean
  offset: number
}>()
defineEmits<{
  select: [path: string]
  close: []
  records: [path: string]
  page: [offset: number]
}>()
</script>

<template>
  <section class="panel content-panel analysis-panel" :aria-busy="loading">
    <div class="section-titlebar">
      <div>
        <h2 class="section-heading">页面访问排行</h2>
        <p class="section-subtitle">按当前条件统计 · 请求量降序 · 路径已去除查询参数</p>
      </div>
      <span class="badge neutral">{{ data ? number(data.total) + ' 个页面' : '等待数据' }}</span>
    </div>
    <div v-if="data" class="mini-metrics">
      <div>
        <span>识别请求</span><strong>{{ number(data.summary.requests) }}</strong>
      </div>
      <div>
        <span>已核验请求</span><strong>{{ number(data.summary.verified) }}</strong>
      </div>
      <div>
        <span>有访问记录的路径</span><strong>{{ number(data.summary.pages) }}</strong>
      </div>
    </div>
    <p v-if="!data" class="empty-inline">
      {{ loading ? '正在读取页面分析…' : '尚未取得页面分析，请刷新重试。' }}
    </p>
    <p v-else-if="!data.items.length" class="empty-inline">
      当前条件下未观察到页面记录，请结合采集健康和观测范围判断。
    </p>
    <div v-else class="analysis-table-wrap">
      <table class="analysis-table">
        <thead>
          <tr>
            <th>页面路径</th>
            <th>请求量</th>
            <th>已核验</th>
            <th>2xx 响应</th>
            <th>爬虫数</th>
            <th>最近访问</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in data.items" :key="row.path">
            <td data-label="页面路径">
              <button class="path-link" @click="$emit('select', row.path)">{{ row.path }}</button>
            </td>
            <td data-label="请求量">{{ number(row.requests) }}</td>
            <td data-label="已核验">{{ number(row.verified) }}</td>
            <td data-label="2xx 响应">{{ number(row.successful) }}</td>
            <td data-label="爬虫数">{{ number(row.crawlers) }}</td>
            <td data-label="最近访问">{{ time(row.last_visit, timezone) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="data" class="pagination">
      <span>第 {{ offset / 20 + 1 }} 页 · {{ data.total }} 个路径</span>
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
  </section>
  <section v-if="selected" class="panel content-panel page-inspector" aria-label="单页面详情">
    <div class="section-titlebar">
      <div>
        <h2 class="section-heading">单页面详情</h2>
        <p class="page-path">{{ selected }}</p>
      </div>
      <button class="text-button" @click="$emit('close')">关闭详情</button>
    </div>
    <p v-if="!detail" class="empty-inline">
      {{ loading ? '正在读取当前页面…' : '页面详情未取得，请刷新重试。' }}
    </p>
    <template v-else
      ><div class="mini-metrics">
        <div>
          <span>识别请求</span><strong>{{ number(detail.summary.requests) }}</strong>
        </div>
        <div>
          <span>已核验请求</span><strong>{{ number(detail.summary.verified) }}</strong>
        </div>
        <div>
          <span>最近访问</span
          ><strong class="metric-time">{{ time(detail.summary.last_visit, timezone) }}</strong>
        </div>
      </div>
      <p class="notice" :class="detail.observation.state === 'observed' ? 'neutral' : 'warning'">
        {{ detail.observation.note }}
      </p>
      <TrendChart :points="detail.trend" />
      <div class="distribution-grid">
        <div>
          <h3 class="subsection-heading">爬虫分布</h3>
          <ul class="distribution-list">
            <li v-for="row in detail.crawlers" :key="row.crawler">
              <span>{{ row.name }}</span
              ><strong>{{ number(row.requests) }}</strong>
            </li>
          </ul>
          <p v-if="!detail.crawlers.length" class="muted paragraph">当前范围无匹配记录。</p>
        </div>
        <div>
          <h3 class="subsection-heading">状态码分布</h3>
          <ul class="distribution-list">
            <li v-for="row in detail.statuses" :key="row.status">
              <span>HTTP {{ row.status }}</span
              ><strong>{{ number(row.requests) }}</strong>
            </li>
          </ul>
        </div>
      </div>
      <button class="secondary-button" @click="$emit('records', selected)">
        查看该页面访问明细
      </button>
    </template>
  </section>
</template>
