<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import LocationPicker from '../components/LocationPicker.vue'
import { session } from '../session'
import type { Location } from '../types'
import PageNav from '../components/PageNav.vue'
import { toastError } from '../ui'

const route = useRoute()
const router = useRouter()
const editingId = computed(() => (route.params.id ? String(route.params.id) : undefined))
const fid = session.currentFamilyId!
const locations = ref<Location[]>([])
const form = reactive({ name: '', note: '', parent_id: null as string | null })
const saving = ref(false)

onMounted(async () => {
  try {
    locations.value = await api.get<Location[]>(`/families/${fid}/locations`)
    if (editingId.value) {
      const loc = locations.value.find((l) => l.id === editingId.value)
      if (loc) Object.assign(form, { name: loc.name, note: loc.note, parent_id: loc.parent_id })
    } else if (typeof route.query.parent === 'string') {
      form.parent_id = route.query.parent
    }
  } catch (e) {
    toastError(e)
  }
})

async function save() {
  saving.value = true
  try {
    const body = { name: form.name, note: form.note, parent_id: form.parent_id }
    const loc = editingId.value
      ? await api.patch<Location>(`/families/${fid}/locations/${editingId.value}`, body)
      : await api.post<Location>(`/families/${fid}/locations`, body)
    router.replace(`/l/${loc.id}`)
  } catch (e) {
    toastError(e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <PageNav :title="editingId ? '编辑位置' : '新建位置'" :back="editingId ? `/l/${editingId}` : '/locations'" home />
  <van-form @submit="save">
    <van-cell-group inset style="margin-top: 12px">
      <van-field
        v-model="form.name"
        label="名称"
        placeholder="例如：主卧、衣柜、蓝色收纳盒"
        maxlength="100"
        :rules="[{ required: true, message: '请输入名称' }]"
      />
      <LocationPicker
        v-model="form.parent_id"
        :locations="locations"
        label="上级位置"
        allow-root
        :exclude-id="editingId"
      />
      <van-field v-model="form.note" label="备注" type="textarea" rows="2" autosize maxlength="1000" />
    </van-cell-group>
    <div class="block-button">
      <van-button round block type="primary" native-type="submit" :loading="saving">保存</van-button>
    </div>
  </van-form>
</template>
