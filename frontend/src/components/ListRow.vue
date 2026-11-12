<script setup lang="ts">
import NameTile from './NameTile.vue'

defineProps<{
  title: string
  to: string
  label?: string
  extra?: string
}>()
</script>

<template>
  <router-link :to="to" class="row">
    <NameTile :name="title" :size="40" />
    <span class="row-text">
      <span class="row-title">{{ title }}</span>
      <span v-if="label" class="row-label">{{ label }}</span>
    </span>
    <span v-if="extra" class="row-extra">{{ extra }}</span>
    <van-icon name="arrow" class="row-arrow" />
  </router-link>
</template>

<style scoped>
.row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  color: inherit;
  text-decoration: none;
}
.row + .row {
  border-top: 1px solid var(--hi-border);
}
.row:active {
  background: var(--van-active-color);
}
.row-text {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.row-title,
.row-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.row-title {
  font-size: 15px;
  font-weight: 500;
  color: var(--hi-text);
}
.row-label {
  font-size: 12px;
  color: var(--hi-text-3);
}
.row-extra {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--hi-text-3);
}
.row-arrow {
  flex-shrink: 0;
  color: var(--hi-text-3);
}
</style>
