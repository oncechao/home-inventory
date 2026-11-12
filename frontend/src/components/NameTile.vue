<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{ name: string; size?: number }>(), { size: 44 })

// 按名字固定挑一种暖色，同一个名字每次颜色都一样
const PALETTE: [string, string][] = [
  ['#fde9e3', '#e2603f'],
  ['#fdf0d9', '#cf8412'],
  ['#e4f2ea', '#3f9466'],
  ['#e2eff6', '#3a84ad'],
  ['#ece7f6', '#7a62b8'],
  ['#fbe4ec', '#c95281'],
]

const colors = computed(() => {
  let h = 0
  for (const ch of props.name) h = (h * 31 + (ch.codePointAt(0) ?? 0)) >>> 0
  return PALETTE[h % PALETTE.length]
})
const initial = computed(() => Array.from(props.name.trim())[0] ?? '?')
</script>

<template>
  <span
    class="tile"
    :style="{
      width: `${size}px`,
      height: `${size}px`,
      background: colors[0],
      color: colors[1],
      fontSize: `${Math.round(size * 0.42)}px`,
      borderRadius: `${Math.round(size * 0.3)}px`,
    }"
    aria-hidden="true"
  >
    {{ initial }}
  </span>
</template>

<style scoped>
.tile {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  font-weight: 600;
}
</style>
