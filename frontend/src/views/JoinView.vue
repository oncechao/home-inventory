<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { refreshFamilies, setCurrentFamily } from '../session'
import type { InvitePreview } from '../types'
import { toastError } from '../ui'

const route = useRoute()
const router = useRouter()
const code = String(route.params.code)
const preview = ref<InvitePreview | null>(null)
const invalid = ref(false)
const joining = ref(false)

onMounted(async () => {
  try {
    preview.value = await api.get<InvitePreview>(`/invites/${encodeURIComponent(code)}`)
  } catch {
    invalid.value = true
  }
})

async function accept() {
  joining.value = true
  try {
    const family = await api.post<{ id: string }>(`/invites/${encodeURIComponent(code)}/accept`)
    await refreshFamilies()
    setCurrentFamily(family.id)
    router.replace('/')
  } catch (e) {
    toastError(e)
  } finally {
    joining.value = false
  }
}
</script>

<template>
  <van-nav-bar title="加入家庭" />
  <van-empty v-if="invalid" image="error" description="邀请无效或已过期">
    <van-button round type="primary" @click="router.replace('/')">返回首页</van-button>
  </van-empty>
  <van-empty v-else-if="preview" image="default" :description="`邀请你加入「${preview.family_name}」`">
    <van-button round type="primary" :loading="joining" @click="accept">
      {{ preview.already_member ? '你已经是成员，进入家庭' : '加入' }}
    </van-button>
  </van-empty>
  <van-loading v-else class="center" style="margin-top: 40px" />
</template>
