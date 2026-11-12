<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const showTabbar = computed(() => route.meta.tab === true)
const active = computed(() =>
  route.path.startsWith('/locations') ? 1 : route.path.startsWith('/family') ? 2 : 0,
)
</script>

<template>
  <router-view />
  <van-tabbar v-if="showTabbar" :model-value="active" placeholder safe-area-inset-bottom>
    <van-tabbar-item to="/" icon="search">找东西</van-tabbar-item>
    <van-tabbar-item to="/locations" icon="location-o">位置</van-tabbar-item>
    <van-tabbar-item to="/family" icon="friends-o">家庭与我</van-tabbar-item>
  </van-tabbar>
</template>
