<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ name: string }>()
// Only trusted SVG files bundled with this application are inserted as markup.
const icons = import.meta.glob<string>('../../assets/icons/*.svg', {
  query: '?raw',
  import: 'default',
  eager: true,
})
const svg = computed(() => icons[`../../assets/icons/${props.name}.svg`] ?? '')
</script>

<template><span class="icon" aria-hidden="true" v-html="svg"></span></template>
