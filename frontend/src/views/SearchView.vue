<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import ListRow from '../components/ListRow.vue'
import { currentFamily, session } from '../session'
import type { Item } from '../types'
import { pathText, toastError } from '../ui'

const router = useRouter()
const q = ref('')
const items = ref<Item[]>([])
const loading = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined
let latest = 0 // 只采用最后一次请求的结果

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 5) return '夜深了'
  if (h < 11) return '早上好'
  if (h < 13) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

async function search() {
  const fid = session.currentFamilyId
  if (!fid) return
  const seq = ++latest
  loading.value = true
  try {
    const query = q.value.trim()
    const result = await api.get<Item[]>(
      `/families/${fid}/items${query ? `?q=${encodeURIComponent(query)}` : ''}`,
    )
    if (seq === latest) items.value = result
  } catch (e) {
    if (seq === latest) toastError(e)
  } finally {
    if (seq === latest) loading.value = false
  }
}

watch(q, () => {
  clearTimeout(timer)
  timer = setTimeout(search, 300)
})
watch(() => session.currentFamilyId, search, { immediate: true })
</script>

<template>
  <header class="home-head">
    <div class="home-top">
      <div>
        <div class="greet">{{ greeting }}，{{ session.user?.username }}</div>
        <h1 class="headline">东西放哪了？</h1>
      </div>
      <button class="family-chip" @click="router.push('/family')">
        <van-icon name="wap-home-o" />
        <span>{{ currentFamily()?.name }}</span>
      </button>
    </div>
    <div class="search-box">
      <van-icon name="search" class="search-icon" />
      <input v-model="q" type="search" placeholder="搜索物品名称、条码或备注" enterkeyhint="search" />
      <van-icon v-if="q" name="clear" class="search-clear" @click="q = ''" />
      <button class="scan-btn" aria-label="扫码查找" @click="router.push('/scan')">
        <van-icon name="scan" />
      </button>
    </div>
  </header>

  <main class="page">
    <div class="section-title">
      <span>{{ q.trim() ? '搜索结果' : '最近更新' }}</span>
      <span v-if="items.length && q.trim()">{{ items.length }} 件</span>
    </div>
    <div v-if="items.length" class="card">
      <ListRow
        v-for="item in items"
        :key="item.id"
        :title="item.name"
        :label="pathText(item.path)"
        :to="`/items/${item.id}`"
      />
    </div>
    <div v-else-if="!loading" class="card">
      <van-empty
        :image="q.trim() ? 'search' : 'default'"
        :description="q.trim() ? '没有找到，换个关键词试试' : '还没有物品，点右下角「添加物品」开始记录'"
      />
    </div>
    <div class="fab-space" />
  </main>

  <button class="fab" @click="router.push('/items/new')">
    <van-icon name="plus" />
    添加物品
  </button>
</template>

<style scoped>
.home-head {
  padding: 20px 16px 4px;
}
.home-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  padding: 0 4px;
}
.greet {
  font-size: 14px;
  color: var(--hi-text-2);
}
.headline {
  margin: 4px 0 0;
  font-size: 26px;
  font-weight: 700;
}
.family-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 45%;
  padding: 6px 12px;
  border: 0;
  border-radius: 16px;
  background: var(--hi-primary-soft);
  color: var(--hi-primary-dark);
  font-size: 13px;
  font-weight: 500;
}
.family-chip span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 18px;
  padding: 6px 6px 6px 14px;
  border-radius: 16px;
  background: var(--hi-card);
  box-shadow: var(--hi-shadow);
}
.search-icon,
.search-clear {
  font-size: 18px;
  color: var(--hi-text-3);
}
.search-box input {
  flex: 1;
  min-width: 0;
  height: 36px;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--hi-text);
  font-size: 15px;
  -webkit-appearance: none;
}
.search-box input::-webkit-search-cancel-button {
  display: none;
}
.scan-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border: 0;
  border-radius: 12px;
  background: var(--hi-primary);
  color: #fff;
  font-size: 20px;
}
</style>
