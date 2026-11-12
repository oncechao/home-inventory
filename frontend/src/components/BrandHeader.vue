<script setup lang="ts">
defineProps<{ title: string; subtitle?: string }>()
</script>

<template>
  <header class="brand">
    <span class="logo"><van-icon name="wap-home" /></span>
    <h1>{{ title }}</h1>
    <p v-if="subtitle">{{ subtitle }}</p>
  </header>
</template>

<style scoped>
.brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 48px 24px 20px;
  text-align: center;
}
.logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 68px;
  height: 68px;
  border-radius: 22px;
  background: linear-gradient(135deg, #f7926f, var(--hi-primary));
  color: #fff;
  font-size: 34px;
  box-shadow: 0 8px 20px rgba(242, 120, 92, 0.35);
}
h1 {
  margin: 18px 0 6px;
  font-size: 24px;
  font-weight: 700;
}
p {
  margin: 0;
  font-size: 14px;
  color: var(--hi-text-2);
}
</style>
