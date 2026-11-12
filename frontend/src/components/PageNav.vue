<script setup lang="ts">
import { useRouter } from 'vue-router'
import { goBack } from '../ui'

defineProps<{
  title?: string
  back?: string // 有值时显示返回箭头；没有站内历史时回到这个地址
  home?: boolean // 显示「回主页」按钮
}>()

const router = useRouter()
</script>

<template>
  <van-nav-bar :title="title" :left-arrow="!!back" :border="false" @click-left="back && goBack(router, back)">
    <template #right>
      <span class="nav-right">
        <slot name="right" />
        <button v-if="home" class="nav-home" aria-label="回到主页" @click.stop="router.push('/')">
          <van-icon name="wap-home-o" />
        </button>
      </span>
    </template>
  </van-nav-bar>
</template>

<style scoped>
.nav-right {
  display: inline-flex;
  align-items: center;
  gap: 14px;
}
.nav-home {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border: 0;
  border-radius: 50%;
  background: var(--hi-primary-soft);
  color: var(--hi-primary);
  font-size: 19px;
}
</style>
