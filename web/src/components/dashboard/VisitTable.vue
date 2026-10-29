<script setup lang="ts">
import type { Visit } from '../../types/index'
import { time, verificationInfo } from '../../utils/presentation'
import UiIcon from '../ui/UiIcon.vue'
defineProps<{ items: Visit[]; timezone: string; detailed?: boolean }>()
defineEmits<{ page: [path: string] }>()
</script>

<template>
  <div class="table-scroll" :class="{ 'detailed-table': detailed }">
    <table class="visits-table" :aria-label="detailed ? '爬虫访问明细' : '最近爬虫访问'">
      <thead>
        <tr>
          <th scope="col">访问时间</th>
          <th scope="col">页面路径</th>
          <th v-if="detailed" scope="col">方法</th>
          <th scope="col">爬虫名称</th>
          <th scope="col">状态码</th>
          <th scope="col">核验结果</th>
          <th v-if="detailed" scope="col">核验依据</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="visit in items" :key="visit.id">
          <td data-label="访问时间" class="visit-time">
            <time>{{ time(visit.occurred_at, timezone) }}</time>
          </td>
          <td data-label="页面路径" class="visit-path" :title="visit.path">
            <button class="path-link" @click="$emit('page', visit.path)">{{ visit.path }}</button>
          </td>
          <td v-if="detailed" data-label="请求方法" class="visit-method">
            <code>{{ visit.method }}</code>
          </td>
          <td data-label="爬虫名称" class="visit-crawler">
            <span>{{ visit.name }}</span
            ><small v-if="detailed && visit.name !== visit.crawler">{{ visit.crawler }}</small
            ><small v-if="detailed && visit.product_attribution">{{
              visit.product_attribution
            }}</small>
          </td>
          <td data-label="HTTP 状态" class="visit-status">
            <span :class="['status-code', { warning: visit.status >= 400 }]">{{
              visit.status
            }}</span>
          </td>
          <td data-label="核验结果" class="visit-verification">
            <span
              class="badge"
              :class="
                verificationInfo(visit.verification, visit.evidence_expires_at, visit.received_at)
                  .tone
              "
              ><UiIcon v-if="visit.verification === 'verified'" name="shield-check" />{{
                verificationInfo(visit.verification, visit.evidence_expires_at, visit.received_at)
                  .label
              }}</span
            >
          </td>
          <td v-if="detailed" data-label="核验依据" class="visit-evidence">
            <details>
              <summary><UiIcon name="chevron-right" />查看依据</summary>
              <div class="evidence-content">
                <p>
                  {{
                    verificationInfo(
                      visit.verification,
                      visit.evidence_expires_at,
                      visit.received_at,
                    ).explanation
                  }}
                </p>
                <p>识别规则：{{ visit.rule_version }}</p>
                <p>证据更新时间：{{ time(visit.evidence_fetched_at, timezone) }}</p>
                <a
                  v-if="visit.evidence_source"
                  :href="visit.evidence_source"
                  target="_blank"
                  rel="noopener noreferrer"
                  >官方证据来源<UiIcon name="arrow-up-right"
                /></a>
                <p v-else>尚无已确认的官方核验依据。</p>
              </div>
            </details>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
