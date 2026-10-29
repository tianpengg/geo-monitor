<script setup lang="ts">
import { nextTick, onUnmounted, ref, watch } from 'vue'
const props = defineProps<{ open: boolean; anchor: HTMLElement | null; width?: number }>()
const emit = defineEmits<{ close: [restoreFocus: boolean]; shown: [] }>()
const popup = ref<HTMLElement | null>(null),
  placed = ref(false)
const style = ref<Record<string, string>>({})
let cleanup = () => {}
function position() {
  if (!props.anchor || !popup.value) return
  const rect = props.anchor.getBoundingClientRect(),
    width = Math.min(props.width ?? Math.max(230, rect.width), window.innerWidth - 24)
  const height = Math.min(popup.value.scrollHeight, 410),
    below = innerHeight - rect.bottom - 12,
    above = rect.top - 12
  const upward = below < height && above > below,
    space = Math.max(100, upward ? above : below)
  style.value = {
    left: `${Math.max(12, Math.min(rect.left, innerWidth - width - 12))}px`,
    top: `${upward ? Math.max(12, rect.top - Math.min(height, space) - 7) : rect.bottom + 7}px`,
    width: `${width}px`,
    maxHeight: `${Math.min(410, space)}px`,
  }
  placed.value = true
}
function outside(event: Event) {
  const target = event.target as Node
  if (!popup.value?.contains(target) && !props.anchor?.contains(target)) emit('close', false)
}
function keyboard(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    emit('close', true)
  }
  if (event.key === 'Tab' && popup.value?.contains(event.target as Node)) {
    const items = Array.from(
      popup.value.querySelectorAll<HTMLElement>(
        'button:not(:disabled),input:not(:disabled),[tabindex="0"]',
      ),
    )
    if (
      (!event.shiftKey && event.target === items.at(-1)) ||
      (event.shiftKey && event.target === items[0])
    )
      emit('close', true)
  }
}
watch(
  () => props.open,
  async (open) => {
    cleanup()
    placed.value = false
    if (!open) return
    await nextTick()
    if (!props.open) return
    position()
    await nextTick()
    if (!props.open) return
    emit('shown')
    const resize = new ResizeObserver(position)
    if (popup.value) resize.observe(popup.value)
    document.addEventListener('pointerdown', outside, true)
    document.addEventListener('focusin', outside)
    document.addEventListener('keydown', keyboard)
    window.addEventListener('resize', position)
    window.addEventListener('scroll', position, true)
    cleanup = () => {
      resize.disconnect()
      document.removeEventListener('pointerdown', outside, true)
      document.removeEventListener('focusin', outside)
      document.removeEventListener('keydown', keyboard)
      window.removeEventListener('resize', position)
      window.removeEventListener('scroll', position, true)
    }
  },
  { flush: 'post' },
)
onUnmounted(() => cleanup())
</script>

<template>
  <Teleport to="body"
    ><div
      v-if="open"
      ref="popup"
      class="ui-popup"
      :style="{ ...style, visibility: placed ? 'visible' : 'hidden' }"
    >
      <slot /></div
  ></Teleport>
</template>
