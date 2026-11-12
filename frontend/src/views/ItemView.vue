<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog } from 'vant'
import { api, ApiError } from '../api'
import { session } from '../session'
import type { Item } from '../types'
import { formatTime, goBack, pathText, toastError } from '../ui'

const route = useRoute()
const router = useRouter()
const fid = session.currentFamilyId!
const item = ref<Item | null>(null)
const notFound = ref(false)

onMounted(async () => {
  try {
    item.value = await api.get<Item>(`/families/${fid}/items/${route.params.id}`)
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound.value = true
    else toastError(e)
  }
})

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
    <van-nav-bar
      title="物品"
      left-arrow
      right-text="编辑"
      @click-left="goBack(router, '/')"
      @click-right="router.push(`/items/${item.id}/edit`)"
    />
    <van-cell-group inset style="margin-top: 12px">
      <van-cell title="名称" :value="item.name" />
      <van-cell title="放在" :label="pathText(item.path)" is-link :to="`/l/${item.location_id}`" />
      <van-cell v-if="item.barcode" title="条码" :value="item.barcode" />
      <van-cell v-if="item.note" title="备注" :label="item.note" />
      <van-cell title="最后修改" :label="`${item.updated_by_name ?? '—'} · ${formatTime(item.updated_at)}`" />
    </van-cell-group>
    <div class="block-button">
      <van-button round block type="danger" plain @click="remove">删除物品</van-button>
    </div>
  </template>
  <template v-else-if="notFound">
    <van-nav-bar title="物品" left-arrow @click-left="router.replace('/')" />
    <van-empty image="search" description="找不到这个物品" />
  </template>
  <van-loading v-else class="center" style="margin-top: 40px" />
</template>
