<script setup lang="ts">
import { computed, nextTick, ref, useAttrs, useId, watch } from 'vue'
import { monthDays, shiftDate, shiftMonth, todayDate, validDate } from '../../utils/controls'
import UiInput from './UiInput.vue'
import UiIcon from './UiIcon.vue'
import UiPopup from './UiPopup.vue'
defineOptions({ inheritAttrs: false })
const props = withDefaults(defineProps<{ timezone?: string; disabled?: boolean }>(), {
  timezone: 'Asia/Shanghai',
})
const model = defineModel<string>({ default: '' })
const attrs = useAttrs(),
  id = useId(),
  anchor = ref<HTMLElement | null>(null),
  field = ref<InstanceType<typeof UiInput> | null>(null)
const open = ref(false),
  focused = ref(todayDate(props.timezone)),
  month = ref(focused.value),
  touched = ref(false)
const today = ref(todayDate(props.timezone)),
  days = computed(() => monthDays(month.value))
const invalid = computed(() => touched.value && Boolean(model.value) && !validDate(model.value))
const label = computed(() => String(attrs['aria-label'] ?? '日期'))
const monthLabel = computed(
  () => `${Number(month.value.slice(0, 4))} 年 ${Number(month.value.slice(5, 7))} 月`,
)
function close(restore = false) {
  open.value = false
  if (restore) field.value?.focus()
}
function show() {
  if (props.disabled) return
  today.value = todayDate(props.timezone)
  focused.value = validDate(model.value) ? model.value : today.value
  month.value = focused.value
  open.value = true
}
function choose(value: string) {
  if (!validDate(value)) return
  model.value = value
  touched.value = true
  close(true)
}
function clearDate() {
  model.value = ''
  close(true)
}
function focusDay() {
  document.getElementById(`${id}-${focused.value}`)?.focus()
}
async function move(value: string) {
  if (!validDate(value)) return
  focused.value = value
  month.value = value
  await nextTick()
  document.getElementById(`${id}-${value}`)?.focus()
}
function key(event: KeyboardEvent) {
  let value = focused.value
  if (event.key === 'ArrowLeft') value = shiftDate(value, -1)
  else if (event.key === 'ArrowRight') value = shiftDate(value, 1)
  else if (event.key === 'ArrowUp') value = shiftDate(value, -7)
  else if (event.key === 'ArrowDown') value = shiftDate(value, 7)
  else if (event.key === 'PageUp') value = shiftMonth(value, -1)
  else if (event.key === 'PageDown') value = shiftMonth(value, 1)
  else if (event.key === 'Home')
    value = shiftDate(value, -(new Date(`${value}T12:00:00Z`).getUTCDay() + 6) % 7)
  else if (event.key === 'End')
    value = shiftDate(value, 6 - ((new Date(`${value}T12:00:00Z`).getUTCDay() + 6) % 7))
  else return
  event.preventDefault()
  void move(value)
}
watch(
  () => props.disabled,
  (disabled) => {
    if (disabled) close()
  },
)
</script>

<template>
  <div ref="anchor" :class="['ui-date', { 'has-error': invalid }]">
    <UiInput
      ref="field"
      v-bind="attrs"
      v-model="model"
      :disabled="disabled"
      maxlength="10"
      placeholder="YYYY-MM-DD"
      :aria-invalid="invalid || undefined"
      @focusout="touched = true"
      @keydown.down.prevent="show"
    >
      <button
        class="ui-icon-button"
        type="button"
        :disabled="disabled"
        :aria-label="'打开' + label + '日历'"
        :aria-expanded="open"
        :aria-controls="id"
        @click="open ? close() : show()"
      >
        <UiIcon name="calendar" />
      </button>
    </UiInput>
    <UiPopup :open="open" :anchor="anchor" :width="312" @close="close" @shown="focusDay">
      <div :id="id" class="ui-calendar" role="dialog" :aria-label="label + '日历'">
        <div class="ui-calendar-header">
          <button
            type="button"
            class="ui-icon-button"
            aria-label="上个月"
            :disabled="month.startsWith('0001-01')"
            @click="move(shiftMonth(month, -1))"
          >
            <UiIcon name="chevron-right" class="ui-left" /></button
          ><strong aria-live="polite">{{ monthLabel }}</strong
          ><button
            type="button"
            class="ui-icon-button"
            aria-label="下个月"
            :disabled="month.startsWith('9999-12')"
            @click="move(shiftMonth(month, 1))"
          >
            <UiIcon name="chevron-right" />
          </button>
        </div>
        <div class="ui-calendar-week" aria-hidden="true">
          <span v-for="day in ['一', '二', '三', '四', '五', '六', '日']" :key="day">{{
            day
          }}</span>
        </div>
        <div class="ui-calendar-days" role="grid" :aria-label="monthLabel" @keydown="key">
          <div v-for="week in 6" :key="week" role="row">
            <button
              v-for="day in days.slice((week - 1) * 7, week * 7)"
              :id="`${id}-${day.value}`"
              :key="day.value"
              type="button"
              role="gridcell"
              :aria-label="day.value"
              :aria-selected="model === day.value"
              :aria-current="day.value === today ? 'date' : undefined"
              :disabled="!validDate(day.value)"
              :tabindex="focused === day.value ? 0 : -1"
              :class="{
                'is-other-month': !day.current,
                'is-selected': model === day.value,
                'is-today': day.value === today,
              }"
              @focus="focused = day.value"
              @click="choose(day.value)"
            >
              {{ day.day }}
            </button>
          </div>
        </div>
        <div class="ui-calendar-footer">
          <button type="button" class="text-button" @click="choose(today)">今天</button
          ><span>{{ timezone }}</span
          ><button
            type="button"
            class="text-button"
            @click="clearDate"
          >
            清空日期
          </button>
        </div>
      </div>
    </UiPopup>
  </div>
</template>
