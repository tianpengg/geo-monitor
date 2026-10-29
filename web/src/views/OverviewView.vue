<script setup lang="ts">
import { useWorkspaceContext } from '../composables/workspaceContext'
import { number, time } from '../utils/presentation'
import UiIcon from '../components/ui/UiIcon.vue'
import HealthCard from '../components/dashboard/HealthCard.vue'
import TrendChart from '../components/dashboard/TrendChart.vue'
import VisitTable from '../components/dashboard/VisitTable.vue'

const { loading, dataError, overview, recent, health, zone, healthState, verified, verificationRate, emptyMessage, navigate, openPage, openRecords } = useWorkspaceContext()
</script>

<template>
<div v-if="!overview" class="panel loading-panel" role="status">
    <UiIcon :name="dataError ? 'info-circle' : 'activity'" />
    <h2>{{ dataError ? '暂时无法读取访问数据' : '正在读取访问数据' }}</h2>
    <p>
      {{ dataError ? '请重试更新，失败不会计为零访问。' : '正在获取统计、访问记录和采集状态。' }}
    </p>
  </div>
  <template v-else>
    <section class="metrics" aria-label="访问统计" :aria-busy="loading">
      <div class="metric primary-metric">
        <div class="metric-label">已识别请求<UiIcon name="chart-bar" /></div>
        <div class="metric-value">{{ number(overview.summary.requests) }}</div>
        <p class="metric-foot"><UiIcon name="circle-check" />去重后的爬虫请求</p>
      </div>
      <div class="metric">
        <div class="metric-label">已核验请求<UiIcon name="shield-check" /></div>
        <div class="metric-value">{{ number(verified) }}</div>
        <p class="metric-foot">
          {{
            verificationRate === null
              ? '当前范围暂无识别请求'
              : `占已识别请求的 ${verificationRate}%`
          }}
        </p>
      </div>
      <div class="metric">
        <div class="metric-label">访问页面<UiIcon name="layout-list" /></div>
        <div class="metric-value">{{ number(overview.summary.pages) }}</div>
        <p class="metric-foot">按页面路径去重</p>
      </div>
      <div class="metric">
        <div class="metric-label">活跃爬虫<UiIcon name="robot" /></div>
        <div class="metric-value">{{ number(overview.crawlers.length) }}</div>
        <p class="metric-foot">当前范围内有访问的爬虫</p>
      </div>
    </section>
    <div
      v-if="overview.empty_message"
      class="notice"
      :class="health?.overall === 'healthy' && !dataError ? 'neutral' : 'warning'"
      role="status"
    >
      <UiIcon name="info-circle" /><span
        >{{ emptyMessage
        }}<small v-if="health?.overall !== 'healthy'"
          >{{ healthState.label }} · 最后日志：{{ time(health?.log_received_at, zone) }}</small
        ></span
      >
    </div>
    <div class="dashboard-grid">
      <section class="panel chart-card" aria-labelledby="trendTitle">
        <div class="section-titlebar">
          <div>
            <h2 id="trendTitle" class="section-heading">访问趋势</h2>
            <p class="section-subtitle">按官网时区的自然日统计 · 已去重</p>
          </div>
          <span class="chart-legend"><span class="legend-dot"></span>已识别请求</span>
        </div>
        <TrendChart :points="overview.trend" />
        <div class="chart-footer">
          <span
            ><UiIcon name="clock" />最近访问
            <strong>{{ time(overview.summary.last_visit, zone) }}</strong></span
          ><span>按访问发生时间统计</span>
        </div>
      </section>
      <HealthCard
        :health="health"
        :timezone="zone"
        :stale="Boolean(dataError)"
        show-link
        @details="navigate('health')"
      />
    </div>
    <div class="lower-grid">
      <section class="panel ranking">
        <div class="section-titlebar">
          <h2 class="section-heading">爬虫访问排行</h2>
          <span class="section-meta">请求数</span>
        </div>
        <ol v-if="overview.crawlers.length" class="rank-list">
          <li v-for="(item, index) in overview.crawlers" :key="item.crawler" class="rank-item">
            <span class="rank-index">{{ String(index + 1).padStart(2, '0') }}</span
            ><button
              class="rank-body"
              :title="`${item.name} · ${item.crawler}，查看访问明细`"
              @click="openRecords('', item.crawler)"
            >
              <span
                class="rank-fill"
                :style="{ width: `${(item.requests / overview.crawlers[0]!.requests) * 100}%` }"
              ></span
              ><span class="rank-name">{{ item.name }}</span></button
            ><strong class="rank-count">{{ number(item.requests) }}</strong>
          </li>
        </ol>
        <p v-else class="empty-inline">当前范围暂无匹配爬虫。</p>
        <p class="rank-foot">按已识别的爬虫身份分别统计</p>
      </section>
      <section class="panel recent">
        <div class="section-titlebar">
          <div>
            <h2 class="section-heading">最近访问</h2>
            <p class="section-subtitle">当前日期范围内的最近请求</p>
          </div>
          <button class="secondary-button" @click="openRecords()">
            查看明细<UiIcon name="arrow-right" />
          </button>
        </div>
        <VisitTable v-if="recent.length" :items="recent" :timezone="zone" @page="openPage" />
        <p v-else class="empty-inline">{{ emptyMessage }}</p>
        <div class="table-footer">
          <span>展示最近 {{ recent.length }} 条记录</span><span>识别与来源核验分别展示</span>
        </div>
      </section>
    </div>
  </template>
</template>
