<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { currentFamily, session } from '../session'
import type { Item } from '../types'
import { pathText, toastError } from '../ui'

const router = useRouter()
const q = ref('')
const items = ref<Item[]>([])
const loading = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined

async function search() {
  const fid = session.currentFamilyId
  if (!fid) return
  loading.value = true
  try {
    const query = q.value.trim()
    items.value = await api.get<Item[]>(
      `/families/${fid}/items${query ? `?q=${encodeURIComponent(query)}` : ''}`,
    )
  } catch (e) {
    toastError(e)
  } finally {
    loading.value = false
  }
}

watch(q, () => {
  clearTimeout(timer)
  timer = setTimeout(search, 300)
})
watch(() => session.currentFamilyId, search, { immediate: true })
</script>

<template>
  <van-nav-bar :title="currentFamily()?.name ?? '找东西'">
    <template #right>
      <van-icon name="scan" size="22" @click="router.push('/scan')" />
      <van-icon name="plus" size="22" style="margin-left: 16px" @click="router.push('/items/new')" />
    </template>
  </van-nav-bar>
  <van-search v-model="q" placeholder="搜索物品名称、条码或备注" />
  <van-cell-group v-if="items.length" :title="q.trim() ? '搜索结果' : '最近更新'" inset>
    <van-cell
      v-for="item in items"
      :key="item.id"
      :title="item.name"
      :label="pathText(item.path)"
      is-link
      :to="`/items/${item.id}`"
    />
  </van-cell-group>
  <van-empty v-else-if="!loading" :description="q.trim() ? '没有找到' : '还没有物品，点右上角 + 添加'" />
</template>
