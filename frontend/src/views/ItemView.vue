<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog } from 'vant'
import { api, ApiError } from '../api'
import NameTile from '../components/NameTile.vue'
import PageNav from '../components/PageNav.vue'
import { session } from '../session'
import type { Item } from '../types'
import { formatTime, pathText, toastError } from '../ui'

const route = useRoute()
const router = useRouter()
const fid = session.currentFamilyId!
const item = ref<Item | null>(null)
const notFound = ref(false)
const failed = ref(false)

async function load() {
  notFound.value = false
  failed.value = false
  try {
    item.value = await api.get<Item>(`/families/${fid}/items/${route.params.id}`)
  } catch (e) {
    if (e instanceof ApiError && (e.status === 404 || e.status === 422)) notFound.value = true
    else {
      failed.value = true
      toastError(e)
    }
  }
}
onMounted(load)

async function remove() {
  if (!item.value) return
  try {
    await showConfirmDialog({ title: '删除物品', message: `确定删除「${item.value.name}」吗？` })
  } catch {
    return
  }
  try {
    await api.del(`/families/${fid}/items/${item.value.id}`)
    router.replace(`/l/${item.value.location_id}`)
  } catch (e) {
    toastError(e)
  }
}
</script>

<template>
  <template v-if="item">
    <PageNav back="/">
      <template #right>
        <span class="nav-link" @click="router.push(`/items/${item.id}/edit`)">编辑</span>
      </template>
    </PageNav>

    <main class="page">
      <section class="hero card">
        <NameTile :name="item.name" :size="64" />
        <h1>{{ item.name }}</h1>
        <span v-if="item.barcode" class="barcode"><van-icon name="scan" /> {{ item.barcode }}</span>
      </section>

      <div class="section-title"><span>放在哪</span></div>
      <router-link :to="`/l/${item.location_id}`" class="where card">
        <span class="where-icon"><van-icon name="location" /></span>
        <span class="where-text">
          <span class="where-name">{{ item.path[item.path.length - 1]?.name }}</span>
          <span class="where-path">{{ pathText(item.path) }}</span>
        </span>
        <van-icon name="arrow" class="where-arrow" />
      </router-link>

      <template v-if="item.note">
        <div class="section-title"><span>备注</span></div>
        <div class="card note">{{ item.note }}</div>
      </template>

      <p class="meta">由 {{ item.updated_by_name ?? '—' }} 于 {{ formatTime(item.updated_at) }} 更新</p>

      <van-button round block plain type="danger" icon="delete-o" @click="remove">删除物品</van-button>
    </main>
  </template>

  <template v-else-if="notFound">
    <PageNav title="物品" back="/" />
    <van-empty image="search" description="找不到这个物品">
      <van-button round type="primary" @click="router.replace('/')">回到首页</van-button>
    </van-empty>
  </template>

  <template v-else-if="failed">
    <PageNav title="物品" back="/" />
    <van-empty image="error" description="加载失败">
      <van-button round type="primary" @click="load">重试</van-button>
      <van-button round style="margin-left: 8px" @click="router.replace('/')">回到首页</van-button>
    </van-empty>
  </template>

  <van-loading v-else class="center" style="margin-top: 40px" />
</template>

<style scoped>
.nav-link {
  color: var(--hi-primary);
  font-size: 15px;
}
.hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 24px 18px 20px;
  text-align: center;
}
.hero h1 {
  margin: 4px 0 0;
  font-size: 22px;
  font-weight: 700;
  word-break: break-all;
}
.barcode {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 10px;
  background: #f5efe8;
  color: var(--hi-text-2);
  font-family: ui-monospace, Menlo, monospace;
  font-size: 13px;
}
.where {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  color: inherit;
  text-decoration: none;
}
.where-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: var(--hi-primary-soft);
  color: var(--hi-primary);
  font-size: 20px;
  flex-shrink: 0;
}
.where-text {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.where-name {
  font-size: 16px;
  font-weight: 600;
}
.where-path {
  font-size: 12px;
  color: var(--hi-text-3);
}
.where-arrow {
  color: var(--hi-text-3);
}
.note {
  padding: 14px 16px;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
}
.meta {
  margin: 18px 4px;
  font-size: 12px;
  color: var(--hi-text-3);
  text-align: center;
}
</style>
