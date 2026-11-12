<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import ListRow from '../components/ListRow.vue'
import { rememberLocation } from '../nav'
import { session } from '../session'
import type { Location } from '../types'
import { toastError } from '../ui'

const router = useRouter()
const locations = ref<Location[]>([])
const loaded = ref(false)

const roots = computed(() => locations.value.filter((l) => l.parent_id === null))
const childCount = computed(() => {
  const counts = new Map<string, number>()
  for (const l of locations.value) if (l.parent_id) counts.set(l.parent_id, (counts.get(l.parent_id) ?? 0) + 1)
  return counts
})

async function load() {
  if (!session.currentFamilyId) return
  rememberLocation(session.currentFamilyId, '/locations')
  try {
    locations.value = await api.get<Location[]>(`/families/${session.currentFamilyId}/locations`)
  } catch (e) {
    toastError(e)
  } finally {
    loaded.value = true
  }
}
watch(() => session.currentFamilyId, load, { immediate: true })
</script>

<template>
  <header class="tab-head">
    <h1>位置</h1>
    <button v-if="locations.length" class="link" @click="router.push('/print')">
      <van-icon name="qr" /> 打印标签
    </button>
  </header>

  <main class="page">
    <div class="section-title">
      <span>房间和区域</span>
      <span v-if="locations.length">共 {{ locations.length }} 个位置</span>
    </div>
    <div v-if="roots.length" class="card">
      <ListRow
        v-for="loc in roots"
        :key="loc.id"
        :title="loc.name"
        :label="loc.note || undefined"
        :extra="childCount.get(loc.id) ? `${childCount.get(loc.id)} 个子位置` : undefined"
        :to="`/l/${loc.id}`"
      />
    </div>
    <div v-else-if="loaded" class="card">
      <van-empty description="还没有位置，先建一个房间吧，比如「客厅」「主卧」" />
    </div>
    <div class="fab-space" />
  </main>

  <button class="fab" @click="router.push('/locations/new')">
    <van-icon name="plus" />
    新建位置
  </button>
</template>
