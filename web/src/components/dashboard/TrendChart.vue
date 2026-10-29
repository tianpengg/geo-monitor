<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { TrendPoint } from '../../types/index'
import { coverageLabels, number, observed, trendSegments } from '../../utils/presentation'

const props = defineProps<{ points: TrendPoint[] }>()
const active = ref(-1)
const host = ref<HTMLElement | null>(null)
const width = ref(720)
const height = 256,
  left = 40,
  right = 18,
  top = 20,
  bottom = 30
let observer: ResizeObserver | undefined
onMounted(() => {
  observer = new ResizeObserver((entries) => {
    width.value = Math.max(240, Math.round(entries[0]!.contentRect.width))
  })
  if (host.value) observer.observe(host.value)
})
onUnmounted(() => observer?.disconnect())
const maximum = computed(() => {
  const n = Math.max(4, ...props.points.filter(observed).map((p) => p.requests!))
  const step = 10 ** Math.floor(Math.log10(n / 4))
  return Math.ceil(n / 4 / step) * step * 4
})
const coordinates = computed(() =>
  props.points.map((point, index) => ({
    ...point,
    x:
      left +
      (props.points.length === 1
        ? (width.value - left - right) / 2
        : (index / (props.points.length - 1)) * (width.value - left - right)),
    y: height - bottom - ((point.requests ?? 0) / maximum.value) * (height - top - bottom),
  })),
)
const paths = computed(() =>
  trendSegments(props.points).map((segment) => {
    const vertices = segment.map((point) => coordinates.value[props.points.indexOf(point)]!)
    const line = vertices.map((p, i) => `${i ? 'L' : 'M'} ${p.x} ${p.y}`).join(' ')
    return {
      line,
      area: `${line} L ${vertices.at(-1)!.x} ${height - bottom} L ${vertices[0]!.x} ${height - bottom} Z`,
    }
  }),
)
const ticks = computed(() =>
  Array.from({ length: 5 }, (_, index) => ({
    value: (maximum.value * index) / 4,
    y: height - bottom - (index / 4) * (height - top - bottom),
  })),
)
const selected = computed(() => coordinates.value[active.value])
const step = computed(() => Math.max(1, Math.ceil(props.points.length / 7)))
const coverage = computed(() => ({
  unobserved: props.points.filter((p) => !observed(p)).length,
  incomplete: props.points.filter((p) => p.coverage === 'incomplete').length,
}))
const summary = computed(() =>
  props.points
    .map(
      (p) =>
        `${p.date}：${observed(p) ? number(p.requests) + ' 条' : '未观测'}，${coverageLabels[p.coverage] ?? '覆盖未知'}`,
    )
    .join('；'),
)
function move(event: PointerEvent) {
  const rect = (event.currentTarget as SVGElement).getBoundingClientRect()
  const x = ((event.clientX - rect.left) / rect.width) * width.value
  active.value = coordinates.value.reduce(
    (best, p, i, all) => (Math.abs(p.x - x) < Math.abs(all[best]!.x - x) ? i : best),
    0,
  )
}
function key(event: KeyboardEvent) {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
  event.preventDefault()
  active.value =
    event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? props.points.length - 1
        : Math.max(
            0,
            Math.min(props.points.length - 1, active.value + (event.key === 'ArrowRight' ? 1 : -1)),
          )
}
function bandBounds(x: number) {
  const half = (width.value - left - right) / Math.max(1, props.points.length - 1) / 2
  const start = Math.max(left, x - half)
  return { start, width: Math.min(width.value - right, x + half) - start }
}
watch(
  () => props.points,
  () => {
    active.value = -1
  },
)
</script>

<template>
  <div ref="host" class="trend-chart">
    <svg
      :viewBox="`0 0 ${width} ${height}`"
      role="img"
      tabindex="0"
      :aria-label="`爬虫请求趋势。${summary}。可用左右方向键查看。`"
      @pointermove="move"
      @pointerleave="active = -1"
      @keydown="key"
      @blur="active = -1"
    >
      <defs>
        <linearGradient id="trendArea" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="#8f7de8" stop-opacity=".2" />
          <stop offset="100%" stop-color="#8f7de8" stop-opacity=".01" />
        </linearGradient>
        <pattern id="unobservedPattern" width="7" height="7" patternUnits="userSpaceOnUse">
          <path d="M0 7L7 0" stroke="#e8e6ee" stroke-width="1" />
        </pattern>
      </defs>
      <g v-for="tick in ticks" :key="tick.value">
        <line
          :x1="left"
          :x2="width - right"
          :y1="tick.y"
          :y2="tick.y"
          stroke="#e9e7f0"
          stroke-dasharray="3 4"
        />
        <text :x="left - 10" :y="tick.y + 4" text-anchor="end">
          {{ number(Number(tick.value.toFixed(1))) }}
        </text>
      </g>
      <g v-for="(point, index) in coordinates" :key="point.date">
        <rect
          v-if="!observed(point)"
          :x="bandBounds(point.x).start"
          :y="top"
          :width="bandBounds(point.x).width"
          :height="height - bottom - top"
          fill="url(#unobservedPattern)"
        />
        <text
          v-if="index % step === 0 || index === points.length - 1"
          :x="point.x"
          :y="height - 8"
          :text-anchor="index === 0 ? 'start' : index === points.length - 1 ? 'end' : 'middle'"
        >
          {{ point.date.slice(5).replace('-', '/') }}
        </text>
      </g>
      <g v-for="(path, index) in paths" :key="index">
        <path :d="path.area" fill="url(#trendArea)" />
        <path
          :d="path.line"
          fill="none"
          stroke="#8b78dc"
          stroke-width="2.2"
          stroke-linejoin="round"
        />
      </g>
      <circle
        v-for="point in coordinates.filter(observed)"
        :key="point.date"
        :cx="point.x"
        :cy="point.y"
        :r="points.length === 1 || point.coverage === 'incomplete' ? 4 : 2.7"
        :fill="point.coverage === 'incomplete' ? '#ae8239' : '#8b78dc'"
        stroke="white"
        stroke-width="1.5"
      />
      <g v-if="selected">
        <line
          :x1="selected.x"
          :x2="selected.x"
          :y1="top"
          :y2="height - bottom"
          stroke="#9d8bbd"
          stroke-dasharray="3 4"
        />
      </g>
    </svg>
    <div
      v-if="selected"
      class="trend-tooltip"
      :style="{ left: `${Math.max(12, Math.min(87, (selected.x / width) * 100))}%` }"
      role="status"
    >
      <span>{{ selected.date }}</span
      ><strong>{{ observed(selected) ? `${number(selected.requests)} 条请求` : '未观测' }}</strong
      ><small>{{ coverageLabels[selected.coverage] ?? '覆盖未知' }}</small>
    </div>
    <p v-if="coverage.unobserved || coverage.incomplete" class="coverage-note">
      <span v-if="coverage.unobserved"
        >斜纹区域：{{ coverage.unobserved }} 天未观测，不计为零访问。</span
      ><span v-if="coverage.incomplete">琥珀色标记：{{ coverage.incomplete }} 天观测不完整。</span>
    </p>
    <p class="sr-only">{{ summary }}</p>
  </div>
</template>
