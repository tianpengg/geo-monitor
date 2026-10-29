<script setup lang="ts">
import { computed } from 'vue'
import type { Health } from '../../types/index'
import { bytes, healthPresentation, number, time } from '../../utils/presentation'
import UiIcon from '../ui/UiIcon.vue'
const props = defineProps<{
  health: Health | null
  timezone: string
  stale?: boolean
  showLink?: boolean
}>()
defineEmits<{ details: [] }>()
const state = computed(() => healthPresentation(props.health, props.stale))
</script>

<template>
  <section class="panel health-card" aria-labelledby="healthCardTitle" :data-tone="state.tone">
    <div class="section-titlebar">
      <h2 id="healthCardTitle" class="section-heading">采集健康</h2>
      <span class="badge" :class="state.tone"
        ><span class="status-dot"></span>{{ state.label }}</span
      >
    </div>
    <div class="health-summary">
      <h3>{{ state.title }}</h3>
      <p>{{ state.description }}</p>
    </div>
    <dl class="health-checks">
      <div>
        <dt>连接状态</dt>
        <dd>{{ state.connection }}</dd>
      </div>
      <div>
        <dt>日志读取</dt>
        <dd>{{ state.reading }}</dd>
      </div>
      <div>
        <dt>上报处理</dt>
        <dd>{{ state.processing }}</dd>
      </div>
    </dl>
    <dl class="health-rows">
      <div>
        <dt>最后心跳</dt>
        <dd>{{ time(health?.heartbeat_at, timezone) }}</dd>
      </div>
      <div>
        <dt>最后收到日志</dt>
        <dd>{{ time(health?.log_received_at, timezone) }}</dd>
      </div>
    </dl>
    <dl class="health-stats">
      <div>
        <dt>待确认</dt>
        <dd>{{ bytes(health?.pending_bytes) }}</dd>
      </div>
      <div>
        <dt>解析异常</dt>
        <dd>{{ number(health?.parse_errors) }}</dd>
      </div>
      <div>
        <dt>已知缺口</dt>
        <dd>{{ health ? number(health.gaps.length) : '—' }}</dd>
      </div>
    </dl>
    <div v-if="showLink" class="health-bottom">
      <span>心跳独立于网站访问</span
      ><button class="text-button" @click="$emit('details')">
        查看采集详情<UiIcon name="arrow-right" />
      </button>
    </div>
  </section>
</template>
