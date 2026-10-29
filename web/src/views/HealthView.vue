<script setup lang="ts">
import { useWorkspaceContext } from '../composables/workspaceContext'
import { errorLabels, gapLabels, number, time } from '../utils/presentation'
import HealthCard from '../components/dashboard/HealthCard.vue'

const { dataError, rules, unknown, health, zone } = useWorkspaceContext()
</script>

<template>
<div class="health-page-grid">
    <HealthCard :health="health" :timezone="zone" :stale="Boolean(dataError)" />
    <section class="panel content-panel">
      <h2 class="section-heading">采集时间与完整性</h2>
      <dl class="info-list">
        <div>
          <dt>首次启用</dt>
          <dd>{{ time(health?.baseline_at, zone) }}</dd>
        </div>
        <div>
          <dt>最后处理完成</dt>
          <dd>{{ time(health?.processed_at, zone) }}</dd>
        </div>
        <div>
          <dt>最近错误</dt>
          <dd>
            {{
              health?.error_code
                ? (errorLabels[health.error_code] ?? health.error_code)
                : health
                  ? '无'
                  : '未知'
            }}
          </dd>
        </div>
      </dl>
      <h3 class="subsection-heading">已知缺口与完整性限制</h3>
      <p v-if="!health" class="muted paragraph">尚未取得完整性信息，请先更新采集状态。</p>
      <p v-else-if="!health.gaps.length" class="muted paragraph">
        暂无已知缺口；补采范围受源日志保留期限限制。
      </p>
      <ul v-else class="gap-list">
        <li v-for="gap in health.gaps" :key="gap.id">
          <strong>{{ gapLabels[gap.reason] ?? gap.reason }}</strong
          ><time>{{ time(gap.detected_at, zone) }}</time>
          <p>
            字节范围 {{ gap.start_offset ?? '未知' }} 至
            {{ gap.end_offset ?? '未知' }}；丢失请求数未知。
          </p>
        </li>
      </ul>
    </section>
  </div>
  <div class="capability-grid">
    <section class="panel content-panel">
      <h2 class="section-heading">识别能力</h2>
      <p class="section-subtitle">声明身份与官方来源核验分别判断</p>
      <ul class="capability-list">
        <li v-for="rule in rules" :key="rule.token ?? rule.name">
          <div>
            <strong>{{ rule.name }}</strong
            ><small v-if="rule.product_attribution">{{ rule.product_attribution }}</small
            ><small v-if="rule.rule_version"
              >规则 {{ rule.rule_version }} · 配置更新 {{ rule.reviewed_at
              }}<a
                v-if="rule.documentation_url"
                :href="rule.documentation_url"
                target="_blank"
                rel="noopener noreferrer"
                >官方依据 ↗</a
              ></small
            >
          </div>
          <span :class="['badge', rule.token ? 'neutral' : 'warning']">{{ rule.coverage }}</span>
        </li>
      </ul>
    </section>
    <section class="panel content-panel">
      <h2 class="section-heading">未知爬虫线索</h2>
      <p class="section-subtitle">保留线索，不推定为未确认的平台访问</p>
      <p v-if="!unknown.length" class="empty-inline">暂无未知爬虫线索。</p>
      <ul v-else class="unknown-list">
        <li v-for="item in unknown" :key="item.hint">
          <strong>{{ item.hint }}</strong
          ><span>{{ number(item.request_count) }} 次请求</span
          ><small>最近观察：{{ time(item.last_seen_at, zone) }}</small>
        </li>
      </ul>
    </section>
  </div>
</template>
