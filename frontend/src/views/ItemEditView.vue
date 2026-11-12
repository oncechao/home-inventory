<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showFailToast } from 'vant'
import { api } from '../api'
import BarcodeScanner from '../components/BarcodeScanner.vue'
import LocationPicker from '../components/LocationPicker.vue'
import { session } from '../session'
import type { Item, Location } from '../types'
import PageNav from '../components/PageNav.vue'
import { toastError } from '../ui'

const route = useRoute()
const router = useRouter()
const editingId = computed(() => (route.params.id ? String(route.params.id) : undefined))
const fid = session.currentFamilyId!
const locations = ref<Location[]>([])
const loaded = ref(false)
const form = reactive({ name: '', barcode: '', note: '', location_id: null as string | null })
const scanning = ref(false)
const saving = ref(false)

onMounted(async () => {
  try {
    locations.value = await api.get<Location[]>(`/families/${fid}/locations`)
    loaded.value = true
    if (editingId.value) {
      const item = await api.get<Item>(`/families/${fid}/items/${editingId.value}`)
      Object.assign(form, {
        name: item.name,
        barcode: item.barcode ?? '',
        note: item.note,
        location_id: item.location_id,
      })
    } else {
      if (typeof route.query.barcode === 'string') form.barcode = route.query.barcode
      if (typeof route.query.location === 'string') form.location_id = route.query.location
    }
  } catch (e) {
    toastError(e)
  }
})

function onScanned(text: string) {
  form.barcode = text
  scanning.value = false
}

async function save() {
  if (!form.location_id) {
    showFailToast('请选择存放位置')
    return
  }
  saving.value = true
  try {
    const body = {
      name: form.name,
      barcode: form.barcode.trim() || null,
      note: form.note,
      location_id: form.location_id,
    }
    const item = editingId.value
      ? await api.patch<Item>(`/families/${fid}/items/${editingId.value}`, body)
      : await api.post<Item>(`/families/${fid}/items`, body)
    router.replace(`/items/${item.id}`)
  } catch (e) {
    toastError(e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <PageNav :title="editingId ? '编辑物品' : '添加物品'" :back="editingId ? `/items/${editingId}` : '/'" home />

  <van-empty v-if="loaded && !locations.length" description="还没有任何位置，先建一个位置才能放物品">
    <van-button round type="primary" @click="router.push('/locations/new')">新建位置</van-button>
  </van-empty>

  <van-form v-else @submit="save">
    <van-cell-group inset style="margin-top: 12px">
      <van-field
        v-model="form.name"
        label="名称"
        placeholder="例如：护照、螺丝刀"
        maxlength="200"
        :rules="[{ required: true, message: '请输入名称' }]"
      />
      <LocationPicker v-model="form.location_id" :locations="locations" label="存放位置" />
      <van-field v-model="form.barcode" label="条码" placeholder="可选" maxlength="64">
        <template #right-icon>
          <van-icon name="scan" size="20" @click="scanning = true" />
        </template>
      </van-field>
      <van-field v-model="form.note" label="备注" type="textarea" rows="2" autosize maxlength="1000" />
    </van-cell-group>
    <div class="block-button">
      <van-button round block type="primary" native-type="submit" :loading="saving">保存</van-button>
    </div>
  </van-form>

  <van-popup v-model:show="scanning" position="bottom" round destroy-on-close>
    <van-nav-bar title="扫描条码" right-text="关闭" @click-right="scanning = false" />
    <BarcodeScanner v-if="scanning" @detected="onScanned" />
  </van-popup>
</template>
