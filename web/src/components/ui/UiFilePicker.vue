<script setup lang="ts">
import { ref } from 'vue'
import UiIcon from './UiIcon.vue'
const props = defineProps<{ disabled?: boolean }>()
const model = defineModel<File | null>({ default: null })
const input = ref<HTMLInputElement | null>(null),
  dragging = ref(false),
  error = ref('')
function selected(files: FileList | null) {
  error.value = ''
  if (!files?.length) return
  if (files.length !== 1) {
    error.value = '请一次选择一个目录文件'
    return
  }
  model.value = files[0]!
}
function choose() {
  if (input.value) {
    input.value.value = ''
    input.value.click()
  }
}
function clear() {
  model.value = null
  error.value = ''
  if (input.value) input.value.value = ''
}

function dropFile(event: DragEvent) {
  dragging.value = false
  if (!props.disabled) selected(event.dataTransfer?.files ?? null)
}
</script>

<template>
  <div
    class="ui-file-picker"
    :class="{ 'is-dragging': dragging, 'is-disabled': disabled }"
    @dragover.prevent="dragging = !disabled"
    @dragleave.prevent="dragging = false"
    @drop.prevent="dropFile"
  >
    <input
      ref="input"
      type="file"
      hidden
      tabindex="-1"
      aria-hidden="true"
      accept=".xml,.csv,.json"
      :disabled="disabled"
      @change="selected(($event.target as HTMLInputElement).files)"
    />
    <span class="ui-file-symbol"><UiIcon :name="model ? 'file-text' : 'upload'" /></span>
    <div class="ui-file-copy">
      <strong>{{ model?.name ?? '选择或拖入内容目录' }}</strong
      ><span>{{
        model
          ? `${(model.size / 1024).toFixed(1)} KB · 已选择，等待导入`
          : 'XML、CSV 或 JSON · UTF-8 · 最大 1 MiB'
      }}</span>
    </div>
    <button class="ui-file-choose" type="button" :disabled="disabled" @click="choose">
      {{ model ? '重新选择' : '选择文件' }}
    </button>
    <button
      v-if="model"
      type="button"
      class="ui-icon-button"
      aria-label="移除已选文件"
      :disabled="disabled"
      @click="clear"
    >
      <UiIcon name="x" />
    </button>
    <p v-if="error" class="ui-file-error" role="alert">{{ error }}</p>
  </div>
</template>
