<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog } from 'vant'
import { api, ApiError } from '../api'
import ListRow from '../components/ListRow.vue'
import NameTile from '../components/NameTile.vue'
import PageNav from '../components/PageNav.vue'
import { nav, rememberLocation } from '../nav'
import { refreshFamilies, session, setCurrentFamily } from '../session'
import type { LocationDetail } from '../types'
import { toastError } from '../ui'

const route = useRoute()
const router = useRouter()
const detail = ref<LocationDetail | null>(null)
const notFound = ref(false)
const failed = ref(false)

async function load() {
  const id = String(route.params.id)
  detail.value = null
  notFound.value = false
  failed.value = false
  try {
    // 先问这个位置属于哪个家庭：扫别的家庭的二维码时自动切换过去
    const { family_id } = await api.get<{ family_id: string }>(`/locations/${id}`)
    if (!session.families.some((f) => f.id === family_id)) await refreshFamilies()
    if (session.currentFamilyId !== family_id) setCurrentFamily(family_id)
    detail.value = await api.get<LocationDetail>(`/families/${family_id}/locations/${id}`)
    rememberLocation(family_id, `/l/${id}`)
  } catch (e) {
    if (e instanceof ApiError && (e.status === 404 || e.status === 422)) {
      notFound.value = true
      // 记住的正是这个已经不存在的位置时，下次点「位置」标签改去最上层
      if (nav.lastLocation?.path === `/l/${id}`) rememberLocation(nav.lastLocation.familyId, '/locations')
    } else {
      failed.value = true
      toastError(e)
    }
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
    <PageNav :back="detail.parent_id ? `/l/${detail.parent_id}` : '/locations'">
      <template #right>
        <button class="to-top" @click.stop="router.push('/locations')">
          <van-icon name="wap-nav" /> 全部位置
        </button>
        <span class="nav-link" @click="router.push(`/l/${detail.id}/edit`)">编辑</span>
      </template>
    </PageNav>

    <main class="page">
      <section class="hero card">
        <NameTile :name="detail.name" :size="56" />
        <div class="hero-text">
          <h1>{{ detail.name }}</h1>
          <div class="crumbs">
            <router-link to="/locations">全部</router-link>
            <template v-for="node in detail.path.slice(0, -1)" :key="node.id">
              <span class="sep">›</span>
              <router-link :to="`/l/${node.id}`">{{ node.name }}</router-link>
            </template>
          </div>
          <p v-if="detail.note" class="note">{{ detail.note }}</p>
        </div>
      </section>

      <div class="quick card">
        <button @click="router.push({ path: '/items/new', query: { location: detail.id } })">
          <span class="q-icon primary"><van-icon name="plus" /></span>放入物品
        </button>
        <button @click="router.push({ path: '/locations/new', query: { parent: detail.id } })">
          <span class="q-icon"><van-icon name="cluster-o" /></span>新建子位置
        </button>
        <button @click="router.push({ path: '/print', query: { ids: detail.id } })">
          <span class="q-icon"><van-icon name="qr" /></span>打印二维码
        </button>
        <button @click="remove">
          <span class="q-icon danger"><van-icon name="delete-o" /></span>删除
        </button>
      </div>

      <div class="section-title">
        <span>物品</span><span>{{ detail.items.length }} 件</span>
      </div>
      <div class="card">
        <ListRow
          v-for="item in detail.items"
          :key="item.id"
          :title="item.name"
          :label="item.note || item.barcode || undefined"
          :to="`/items/${item.id}`"
        />
        <div v-if="!detail.items.length" class="empty-row">这里还没有物品</div>
      </div>

      <div class="section-title">
        <span>子位置</span><span>{{ detail.children.length }} 个</span>
      </div>
      <div class="card">
        <ListRow
          v-for="c in detail.children"
          :key="c.id"
          :title="c.name"
          :label="c.note || undefined"
          :to="`/l/${c.id}`"
        />
        <div v-if="!detail.children.length" class="empty-row">没有子位置</div>
      </div>
    </main>
  </template>

  <template v-else-if="notFound">
    <PageNav title="位置" back="/" />
    <van-empty image="search" description="找不到这个位置，或者你不是它所在家庭的成员">
      <van-button round type="primary" @click="router.replace('/')">回到首页</van-button>
    </van-empty>
  </template>

  <template v-else-if="failed">
    <PageNav title="位置" back="/" />
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
.to-top {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  border: 0;
  border-radius: 14px;
  background: var(--hi-primary-soft);
  color: var(--hi-primary-dark);
  font-size: 13px;
  font-weight: 500;
}
.hero {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  padding: 18px;
}
.hero-text {
  min-width: 0;
}
.hero h1 {
  margin: 2px 0 6px;
  font-size: 22px;
  font-weight: 700;
  word-break: break-all;
}
.crumbs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  font-size: 13px;
  color: var(--hi-text-3);
}
.crumbs a {
  color: var(--hi-text-2);
  text-decoration: none;
}
.note {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--hi-text-2);
  white-space: pre-wrap;
}
.quick {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  margin-top: 12px;
  padding: 14px 6px;
}
.quick button {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  border: 0;
  background: none;
  color: var(--hi-text-2);
  font-size: 12px;
}
.q-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: 14px;
  background: #f5efe8;
  color: var(--hi-text);
  font-size: 20px;
}
.q-icon.primary {
  background: var(--hi-primary);
  color: #fff;
}
.q-icon.danger {
  background: #fdeceb;
  color: var(--van-danger-color);
}
</style>
