<script setup lang="ts">
import { computed, nextTick, ref, useAttrs, useId, watch } from 'vue'
import { matchingOptions, type SelectOption } from '../../utils/controls'
import UiIcon from './UiIcon.vue'
import UiPopup from './UiPopup.vue'
defineOptions({ inheritAttrs: false })
const props = defineProps<{
  options: SelectOption[]
  searchable?: boolean
  editable?: boolean
  disabled?: boolean
  placeholder?: string
}>()
const model = defineModel<string>({ default: '' })
const attrs = useAttrs(),
  id = useId(),
  open = ref(false),
  query = ref(''),
  active = ref(-1)
const anchor = ref<HTMLElement | null>(null),
  trigger = ref<HTMLElement | null>(null),
  search = ref<HTMLInputElement | null>(null)
const items = computed(() =>
  matchingOptions(props.options, props.editable ? model.value : query.value),
)
const label = computed(
  () =>
    props.options.find((item) => item.value === model.value)?.label ??
    props.placeholder ??
    '请选择',
)
const ariaLabel = computed(() => String(attrs['aria-label'] ?? '选择选项'))
function close(restore = false) {
  open.value = false
  if (restore) trigger.value?.focus()
}
async function show() {
  if (props.disabled) return
  open.value = true
  query.value = ''
  active.value = props.editable
    ? -1
    : Math.max(
        0,
        items.value.findIndex((item) => item.value === model.value),
      )
  await nextTick()
}
function choose(value: string) {
  model.value = value
  close(true)
}
async function key(event: KeyboardEvent) {
  if (event.key === 'Tab') {
    if (open.value) close(true)
    return
  }
  if (event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    close(true)
    return
  }
  if (
    event.key === 'Enter' ||
    (event.key === ' ' && event.target === trigger.value && !props.editable)
  ) {
    if (!open.value) {
      if (!props.editable) {
        event.preventDefault()
        await show()
      }
      return
    }
    if (items.value[active.value]) {
      event.preventDefault()
      choose(items.value[active.value]!.value)
    } else close()
    return
  }
  if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
    if (props.editable && ['Home', 'End'].includes(event.key)) return
    event.preventDefault()
    if (!open.value) await show()
    const count = items.value.length
    active.value = !count
      ? -1
      : event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? count - 1
          : active.value < 0
            ? event.key === 'ArrowDown'
              ? 0
              : count - 1
            : (active.value + (event.key === 'ArrowDown' ? 1 : -1) + count) % count
    await nextTick()
    document.getElementById(`${id}-${active.value}`)?.scrollIntoView({ block: 'nearest' })
  }
}
function edit(event: Event) {
  model.value = (event.target as HTMLInputElement).value
  open.value = true
  active.value = -1
}
watch(query, () => {
  active.value = items.value.length ? 0 : -1
})
watch(
  () => props.disabled,
  (value) => {
    if (value) close()
  },
)
</script>

<template>
  <div ref="anchor" :class="['ui-select', { 'is-open': open, 'is-disabled': disabled }]">
    <div v-if="editable" class="ui-input ui-combo">
      <input
        ref="trigger"
        v-bind="attrs"
        :value="model"
        class="ui-native-input"
        role="combobox"
        aria-autocomplete="list"
        :aria-label="ariaLabel"
        :aria-expanded="open"
        :aria-controls="id"
        :aria-activedescendant="open && active >= 0 ? `${id}-${active}` : undefined"
        :placeholder="placeholder"
        :disabled="disabled"
        @input="edit"
        @keydown="key"
      />
      <button
        class="ui-icon-button"
        type="button"
        :disabled="disabled"
        :aria-label="'打开' + ariaLabel + '建议'"
        @click="open ? close() : show()"
      >
        <UiIcon name="chevron-right" class="ui-down" />
      </button>
    </div>
    <button
      v-else
      ref="trigger"
      v-bind="attrs"
      type="button"
      class="ui-select-trigger"
      role="combobox"
      aria-haspopup="listbox"
      :aria-expanded="open"
      :aria-controls="id"
      :aria-activedescendant="open && active >= 0 ? `${id}-${active}` : undefined"
      :disabled="disabled"
      @click="open ? close() : show()"
      @keydown="key"
    >
      <span class="ui-selected-text">{{ label }}</span
      ><UiIcon name="chevron-right" class="ui-down" />
    </button>
    <UiPopup
      :open="open"
      :anchor="anchor"
      @close="close"
      @shown="editable ? trigger?.focus() : searchable ? search?.focus() : undefined"
    >
      <div v-if="searchable && !editable" class="ui-select-search">
        <UiIcon name="search" /><input
          ref="search"
          v-model="query"
          :aria-label="'搜索' + ariaLabel"
          placeholder="输入名称或标识搜索"
          autocomplete="off"
          role="combobox"
          :aria-expanded="open"
          :aria-controls="id"
          :aria-activedescendant="active >= 0 ? `${id}-${active}` : undefined"
          @keydown="key"
        />
      </div>
      <div :id="id" class="ui-options" role="listbox" :aria-label="ariaLabel">
        <button
          v-for="(item, index) in items"
          :id="`${id}-${index}`"
          :key="item.value"
          type="button"
          role="option"
          tabindex="-1"
          :aria-selected="model === item.value"
          :class="['ui-option', { 'is-active': active === index }]"
          @pointermove="active = index"
          @click="choose(item.value)"
        >
          <span>{{ item.label }}</span
          ><UiIcon v-if="model === item.value" name="check" />
        </button>
        <p v-if="!items.length" class="ui-no-options" role="status">
          {{ editable ? '可直接输入完整状态码或类别' : '没有匹配选项，请更换搜索词' }}
        </p>
      </div>
      <p v-if="!editable" class="ui-select-hint">↑ ↓ 切换 · Enter 选择 · Esc 关闭</p>
    </UiPopup>
  </div>
</template>
