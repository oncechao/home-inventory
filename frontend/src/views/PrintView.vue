<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { toDataURL } from 'qrcode'
import { api } from '../api'
import { session } from '../session'
import type { Location } from '../types'
import PageNav from '../components/PageNav.vue'
import { pathText, toastError } from '../ui'

const route = useRoute()
const all = ref<Location[]>([])
const selected = ref<string[]>([])
const qr = ref<Record<string, string>>({})

onMounted(async () => {
  try {
    all.value = await api.get<Location[]>(`/families/${session.currentFamilyId}/locations`)
    const ids = String(route.query.ids ?? '').split(',').filter(Boolean)
    selected.value = ids.filter((id) => all.value.some((l) => l.id === id))
  } catch (e) {
    toastError(e)
  }
})

const labels = computed(() => all.value.filter((l) => selected.value.includes(l.id)))
const qrReady = computed(() => labels.value.every((l) => qr.value[l.id]))

watch(labels, async (list) => {
  const entries = await Promise.all(
    list.map(async (l): Promise<[string, string]> => [
      l.id,
      qr.value[l.id] ??
        (await toDataURL(`${window.location.origin}/l/${l.id}`, { margin: 1, width: 300, errorCorrectionLevel: 'M' })),
    ]),
  )
  qr.value = { ...qr.value, ...Object.fromEntries(entries) }
})

function toggleAll() {
  selected.value = selected.value.length === all.value.length ? [] : all.value.map((l) => l.id)
}

function print() {
  window.print()
}
</script>

<template>
  <div class="no-print">
    <PageNav title="打印二维码标签" back="/locations" home />
    <p class="hint">勾选要打印的位置。打印后贴在收纳箱上，用手机相机扫一下就能看到里面放了什么。</p>
    <van-checkbox-group v-model="selected">
      <van-cell-group inset>
        <van-cell v-for="l in all" :key="l.id" :title="pathText(l.path)">
          <template #right-icon>
            <van-checkbox :name="l.id" />
          </template>
        </van-cell>
      </van-cell-group>
    </van-checkbox-group>
    <div class="actions">
      <van-button size="small" @click="toggleAll">
        {{ selected.length === all.length && all.length ? '全不选' : '全选' }}
      </van-button>
      <van-button size="small" type="primary" icon="printer" :disabled="!labels.length || !qrReady" @click="print">
        打印 {{ labels.length }} 张
      </van-button>
    </div>
  </div>

  <div class="labels">
    <div v-for="l in labels" :key="l.id" class="label">
      <img v-if="qr[l.id]" :src="qr[l.id]" :alt="l.name" />
      <div class="label-name">{{ l.name }}</div>
      <div class="label-path">{{ pathText(l.path) }}</div>
    </div>
  </div>
</template>

<style scoped>
.labels {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 8px;
  padding: 16px;
}
.label {
  background: #fff;
  border: 1px dashed #c8c9cc;
  border-radius: 6px;
  padding: 8px;
  text-align: center;
  break-inside: avoid;
}
.label img {
  width: 100%;
  max-width: 160px;
}
.label-name {
  font-size: 15px;
  font-weight: 600;
}
.label-path {
  color: #646566;
  font-size: 11px;
  word-break: break-all;
}
@media print {
  .no-print {
    display: none !important;
  }
  .labels {
    grid-template-columns: repeat(3, 1fr);
    gap: 4mm;
    padding: 0;
  }
  .label {
    border-color: #999;
  }
}
</style>
