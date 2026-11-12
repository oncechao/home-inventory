<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
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
  <van-nav-bar title="位置" right-text="打印标签" @click-right="router.push('/print')" />
  <van-cell-group v-if="roots.length" inset style="margin-top: 12px">
    <van-cell
      v-for="loc in roots"
      :key="loc.id"
      :title="loc.name"
      :value="childCount.get(loc.id) ? `${childCount.get(loc.id)} 个子位置` : ''"
      is-link
      :to="`/l/${loc.id}`"
    />
  </van-cell-group>
  <van-empty v-else-if="loaded" description="还没有位置，先建一个房间吧" />
  <div class="block-button">
    <van-button round block type="primary" icon="plus" @click="router.push('/locations/new')">新建位置</van-button>
  </div>
</template>
