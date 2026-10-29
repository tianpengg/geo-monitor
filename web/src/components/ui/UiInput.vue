<script setup lang="ts">
import { ref, useAttrs } from 'vue'
import UiIcon from './UiIcon.vue'
defineOptions({ inheritAttrs: false })
const props = withDefaults(
  defineProps<{
    type?: string
    icon?: string
    clearable?: boolean
    multiline?: boolean
    disabled?: boolean
  }>(),
  { type: 'text' },
)
const model = defineModel<string>({ default: '' })
const emit = defineEmits<{ clear: [] }>()
const attrs = useAttrs(),
  input = ref<HTMLInputElement | HTMLTextAreaElement | null>(null),
  revealed = ref(false)
function clear() {
  model.value = ''
  emit('clear')
  input.value?.focus()
}
defineExpose({ focus: () => input.value?.focus() })
</script>

<template>
  <div :class="['ui-input', { 'is-disabled': disabled, 'is-multiline': multiline }]">
    <UiIcon v-if="icon" :name="icon" class="ui-field-icon" />
    <textarea
      v-if="multiline"
      ref="input"
      v-bind="attrs"
      v-model="model"
      class="ui-native-input"
      :disabled="disabled"
    />
    <input
      v-else
      ref="input"
      v-bind="attrs"
      v-model="model"
      class="ui-native-input"
      :type="props.type === 'password' && revealed ? 'text' : props.type"
      :disabled="disabled"
    />
    <slot />
    <button
      v-if="clearable && model && !disabled && attrs.readonly === undefined"
      class="ui-icon-button ui-clear"
      type="button"
      :aria-label="'清空' + (attrs['aria-label'] ?? '输入')"
      @click="clear"
    >
      <UiIcon name="x" />
    </button>
    <button
      v-if="type === 'password'"
      class="ui-password-toggle"
      type="button"
      :aria-label="revealed ? '隐藏密码' : '显示密码'"
      :aria-pressed="revealed"
      :disabled="disabled"
      @click="revealed = !revealed"
    >
      {{ revealed ? '隐藏' : '显示' }}
    </button>
  </div>
</template>
