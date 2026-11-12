<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog } from 'vant'
import { api, ApiError } from '../api'
import { refreshFamilies, session, setCurrentFamily } from '../session'
import type { LocationDetail } from '../types'
import { goBack, toastError } from '../ui'

const route = useRoute()
const router = useRouter()
const detail = ref<LocationDetail | null>(null)
const notFound = ref(false)

async function load() {
  const id = String(route.params.id)
  detail.value = null
  notFound.value = false
  try {
    // 先问这个位置属于哪个家庭：扫别的家庭的二维码时自动切换过去
    const { family_id } = await api.get<{ family_id: string }>(`/locations/${id}`)
    if (!session.families.some((f) => f.id === family_id)) await refreshFamilies()
    if (session.currentFamilyId !== family_id) setCurrentFamily(family_id)
    detail.value = await api.get<LocationDetail>(`/families/${family_id}/locations/${id}`)
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound.value = true
    else toastError(e)
  }
}
watch(() => route.params.id, load, { immediate: true })

async function remove() {
  const loc = detail.value
  if (!loc) return
  try {
    await showConfirmDialog({ title: '删除位置', message: `确定删除「${loc.name}」吗？` })
  } catch {
    return
  }
  try {
    await api.del(`/families/${session.currentFamilyId}/locations/${loc.id}`)
    router.replace(loc.parent_id ? `/l/${loc.parent_id}` : '/locations')
  } catch (e) {
    toastError(e)
  }
}
</script>

<template>
  <template v-if="detail">
    <van-nav-bar
      :title="detail.name"
      left-arrow
      right-text="编辑"
      @click-left="goBack(router, detail.parent_id ? `/l/${detail.parent_id}` : '/locations')"
      @click-right="router.push(`/l/${detail.id}/edit`)"
    />
    <p class="hint crumbs">
      <template v-for="(node, i) in detail.path" :key="node.id">
        <span v-if="i > 0"> › </span>
        <router-link v-if="i < detail.path.length - 1" :to="`/l/${node.id}`">{{ node.name }}</router-link>
        <span v-else>{{ node.name }}</span>
      </template>
    </p>
    <p v-if="detail.note" class="hint">{{ detail.note }}</p>

    <van-cell-group inset :title="`子位置（${detail.children.length}）`">
      <van-cell v-for="c in detail.children" :key="c.id" :title="c.name" is-link :to="`/l/${c.id}`" />
      <van-cell v-if="!detail.children.length" title="没有子位置" />
    </van-cell-group>

    <van-cell-group inset :title="`物品（${detail.items.length}）`">
      <van-cell
        v-for="item in detail.items"
        :key="item.id"
        :title="item.name"
        :label="item.note"
        is-link
        :to="`/items/${item.id}`"
      />
      <van-cell v-if="!detail.items.length" title="这里还没有物品" />
    </van-cell-group>

    <div class="actions">
      <van-button size="small" type="primary" icon="plus" @click="router.push({ path: '/items/new', query: { location: detail.id } })">
        放入物品
      </van-button>
      <van-button size="small" icon="cluster-o" @click="router.push({ path: '/locations/new', query: { parent: detail.id } })">
        新建子位置
      </van-button>
      <van-button size="small" icon="qr" @click="router.push({ path: '/print', query: { ids: detail.id } })">
        打印二维码
      </van-button>
      <van-button size="small" type="danger" plain icon="delete-o" @click="remove">删除</van-button>
    </div>
  </template>

  <template v-else-if="notFound">
    <van-nav-bar title="位置" left-arrow @click-left="router.replace('/')" />
    <van-empty image="search" description="找不到这个位置，或者你不是它所在家庭的成员">
      <van-button round type="primary" @click="router.replace('/')">回到首页</van-button>
    </van-empty>
  </template>

  <van-loading v-else class="center" style="margin-top: 40px" />
</template>
