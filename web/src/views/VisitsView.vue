<script setup lang="ts">
import { useWorkspaceContext } from '../composables/workspaceContext'
import { time } from '../utils/presentation'
import VisitTable from '../components/dashboard/VisitTable.vue'

const { busy, loading, dataError, visits, applied, nextCursor, previous, health, zone, healthState, dateRange, emptyMessage, next, back, openPage, exportCsv } = useWorkspaceContext()
</script>

<template>
  <section class="panel detail-panel" :aria-busy="loading">
    <div class="section-titlebar">
      <div>
        <h2 class="section-heading">访问记录</h2>
        <p class="section-subtitle">{{ dateRange }} · {{ applied.crawler || '全部已识别爬虫' }}</p>
      </div>
      <div class="record-actions">
        <span class="badge" :class="healthState.tone">{{ healthState.label }}</span
        ><button
          class="secondary-button"
          :disabled="busy || loading || Boolean(dataError)"
          @click="exportCsv"
        >
          导出 CSV
        </button>
      </div>
    </div>
    <p v-if="loading && !visits.length" class="empty-inline" role="status">正在读取访问记录…</p>
    <p v-else-if="!visits.length" class="empty-inline">
      {{ emptyMessage
      }}<small
        >最后心跳：{{ time(health?.heartbeat_at, zone) }} · 最后日志：{{
          time(health?.log_received_at, zone)
        }}</small
      >
    </p>
    <VisitTable v-else :items="visits" :timezone="zone" detailed @page="openPage" />
    <div class="pagination">
      <span>第 {{ previous.length + 1 }} 页 · 当前 {{ visits.length }} 条</span>
      <div>
        <button class="secondary-button" :disabled="!previous.length || loading" @click="back">
          上一页</button
        ><button class="secondary-button" :disabled="!nextCursor || loading" @click="next">
          下一页
        </button>
      </div>
    </div>
  </section>
</template>
