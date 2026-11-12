<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showFailToast } from 'vant'
import { api } from '../api'
import BarcodeScanner from '../components/BarcodeScanner.vue'
import { session } from '../session'
import type { Item } from '../types'
import { goBack, pathText, toastError } from '../ui'

const router = useRouter()
const busy = ref(false)
const scanned = ref('')
const manual = ref('')
const matches = ref<Item[]>([])

/** 本系统生成的位置二维码：http(s)://<域名>/l/<uuid>（不限域名，换过域名的旧标签也能用） */
function locationIdFromQr(text: string): string | null {
  try {
    const url = new URL(text)
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return null
    return url.pathname.match(/^\/l\/([0-9a-f-]{36})\/?$/i)?.[1] ?? null
  } catch {
    return null
  }
}

/** 稍等一会儿再恢复扫码，避免对着同一个码反复触发 */
function resumeLater() {
  setTimeout(() => {
    busy.value = false
  }, 1500)
}

async function handle(text: string) {
  if (busy.value) return
  busy.value = true
  const locationId = locationIdFromQr(text)
  if (locationId) {
    router.replace(`/l/${locationId}`)
    return
  }
  if (text.length > 64 || /^[a-z][a-z0-9+.-]*:\/\//i.test(text)) {
    showFailToast('这不是商品条码')
    resumeLater()
    return
  }
  scanned.value = text
  try {
    const items = await api.get<Item[]>(
      `/families/${session.currentFamilyId}/items?barcode=${encodeURIComponent(text)}`,
    )
    if (items.length === 0) router.replace({ path: '/items/new', query: { barcode: text } })
    else if (items.length === 1) router.replace(`/items/${items[0].id}`)
    else matches.value = items
  } catch (e) {
    toastError(e)
    resumeLater()
  }
}

function rescan() {
  matches.value = []
  busy.value = false
}
</script>

<template>
  <van-nav-bar title="扫码" left-arrow @click-left="goBack(router, '/')" />

  <template v-if="matches.length">
    <van-cell-group inset :title="`条码 ${scanned} 对应 ${matches.length} 个物品`" style="margin-top: 12px">
      <van-cell
        v-for="item in matches"
        :key="item.id"
        :title="item.name"
        :label="pathText(item.path)"
        is-link
        :to="`/items/${item.id}`"
      />
    </van-cell-group>
    <div class="actions">
      <van-button size="small" type="primary" @click="router.push({ path: '/items/new', query: { barcode: scanned } })">
        再添加一个
      </van-button>
      <van-button size="small" @click="rescan">重新扫码</van-button>
    </div>
  </template>

  <template v-else>
    <BarcodeScanner :paused="busy" @detected="handle" />
    <van-cell-group inset title="扫不出来？手动输入条码">
      <van-field v-model="manual" placeholder="条码数字" type="text" inputmode="text">
        <template #button>
          <van-button size="small" type="primary" :disabled="!manual.trim()" @click="handle(manual.trim())">
            查找
          </van-button>
        </template>
      </van-field>
    </van-cell-group>
  </template>
</template>
