<script setup lang="ts">
import { nextTick, onUnmounted, ref, useId, watch } from 'vue'
import UiIcon from './UiIcon.vue'

const props = defineProps<{ open: boolean; title: string; description?: string; busy?: boolean }>()
const emit = defineEmits<{ close: [] }>()
const dialog = ref<HTMLElement | null>(null), titleId = useId(), descriptionId = useId()
let cleanup = () => {}
let restoreTarget: HTMLElement | null = null
function restoreFocus() {
  if (props.busy || !restoreTarget?.isConnected) return
  restoreTarget.focus({ preventScroll: true })
  restoreTarget = null
}
function close() { if (!props.busy) emit('close') }
function focusable() {
  return Array.from(dialog.value?.querySelectorAll<HTMLElement>(
    'a[href],button:not(:disabled),input:not(:disabled),textarea:not(:disabled),[tabindex="0"]',
  ) ?? []).filter(element => element.getClientRects().length > 0)
}
function firstFocus() {
  const elements = focusable()
  const field = elements.find(element => element.matches('input,textarea'))
    ?? elements.find(element => element.matches('form button'))
  ;(field ?? elements[0] ?? dialog.value)?.focus({ preventScroll: true })
}
function keyboard(event: KeyboardEvent) {
  if (event.defaultPrevented) return
  if (event.key === 'Escape') {
    if (document.querySelector('.ui-popup')) return
    event.preventDefault(); close()
  }
  if (event.key !== 'Tab' || (event.target as HTMLElement)?.closest('.ui-popup')) return
  const elements = focusable(), first = elements[0], last = elements.at(-1)
  if (!first || !last) { event.preventDefault(); dialog.value?.focus(); return }
  if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.value)) {
    event.preventDefault(); last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault(); first.focus()
  }
}
function containFocus(event: FocusEvent) {
  const target = event.target as HTMLElement
  if (!dialog.value?.contains(target) && !target.closest('.ui-popup')) firstFocus()
}
watch(() => props.open, async (open) => {
  cleanup()
  if (!open) return
  restoreTarget = null
  const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
  const app = document.getElementById('app'), wasInert = app?.inert ?? false
  const overflow = document.body.style.overflow
  if (app) app.inert = true
  document.body.style.overflow = 'hidden'
  document.addEventListener('keydown', keyboard)
  document.addEventListener('focusin', containFocus)
  cleanup = () => {
    document.removeEventListener('keydown', keyboard)
    document.removeEventListener('focusin', containFocus)
    if (app) app.inert = wasInert
    document.body.style.overflow = overflow
    restoreTarget = previous
    restoreFocus()
    cleanup = () => {}
  }
  await nextTick()
  if (props.open) firstFocus()
}, { flush: 'post', immediate: true })
watch(() => props.busy, () => { if (!props.open) restoreFocus() }, { flush: 'post' })
onUnmounted(() => cleanup())
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="ui-dialog-backdrop" @pointerdown.self="close">
      <section ref="dialog" class="ui-dialog" role="dialog" aria-modal="true" :aria-labelledby="titleId" :aria-describedby="description ? descriptionId : undefined" :aria-busy="busy" tabindex="-1">
        <header class="ui-dialog-header">
          <div><h2 :id="titleId">{{ title }}</h2><p v-if="description" :id="descriptionId">{{ description }}</p></div>
          <button type="button" class="ui-dialog-close" aria-label="关闭弹窗" :disabled="busy" @click="close"><UiIcon name="x" /></button>
        </header>
        <div class="ui-dialog-body"><slot /></div>
        <footer v-if="$slots.footer" class="ui-dialog-footer"><slot name="footer" /></footer>
      </section>
    </div>
  </Teleport>
</template>
