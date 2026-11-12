<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { session } from './session'

const route = useRoute()
const router = useRouter()
const showTabbar = computed(() => route.meta.tab === true)
const active = computed(() =>
  route.path.startsWith('/locations') ? 1 : route.path.startsWith('/family') ? 2 : 0,
)

function retry() {
  router.replace(session.pendingPath ?? '/')
}
</script>

<template>
  <van-empty v-if="session.loadError && !session.loaded" image="network" description="连接服务器失败">
    <van-button round type="primary" @click="retry">重试</van-button>
  </van-empty>
  <router-view v-else />
  <van-tabbar v-if="showTabbar" :model-value="active" placeholder safe-area-inset-bottom>
    <van-tabbar-item to="/" icon="search">找东西</van-tabbar-item>
    <van-tabbar-item to="/locations" icon="location-o">位置</van-tabbar-item>
    <van-tabbar-item to="/family" icon="friends-o">家庭与我</van-tabbar-item>
  </van-tabbar>
</template>
