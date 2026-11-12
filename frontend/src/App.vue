<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { locationTabTarget } from './nav'
import { session } from './session'

const route = useRoute()
const router = useRouter()
const showTabbar = computed(() => route.meta.tab === true)
// 位置详情 /l/... 归到「位置」标签，物品详情归到「找东西」
const active = computed(() =>
  route.path.startsWith('/locations') || route.path.startsWith('/l/')
    ? 1
    : route.path.startsWith('/family')
      ? 2
      : 0,
)
// 从别的标签切回「位置」时回到上次看的层级；已经在「位置」里再点一次，就回到最上层。
// 不用 to：Vant 不会响应对当前标签的点击，所以自己处理跳转
function openLocations() {
  router.push(active.value === 1 ? '/locations' : locationTabTarget(session.currentFamilyId))
}

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
    <van-tabbar-item icon="location-o" @click="openLocations">位置</van-tabbar-item>
    <van-tabbar-item to="/family" icon="friends-o">家庭与我</van-tabbar-item>
  </van-tabbar>
</template>
