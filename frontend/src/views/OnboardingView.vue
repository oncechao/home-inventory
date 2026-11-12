<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showFailToast } from 'vant'
import { api } from '../api'
import { clearSession, refreshFamilies, session, setCurrentFamily } from '../session'
import type { Family } from '../types'
import BrandHeader from '../components/BrandHeader.vue'
import PageNav from '../components/PageNav.vue'
import { toastError } from '../ui'

const router = useRouter()
const familyName = ref('')
const inviteInput = ref('')
const creating = ref(false)

async function create() {
  creating.value = true
  try {
    const family = await api.post<Family>('/families', { name: familyName.value })
    await refreshFamilies()
    setCurrentFamily(family.id)
    router.replace('/')
  } catch (e) {
    toastError(e)
  } finally {
    creating.value = false
  }
}

function join() {
  // 支持粘贴完整链接 https://xxx/join/<code>，也支持只填邀请码
  const match = inviteInput.value.trim().match(/([A-Za-z0-9_-]{8,})\/?$/)
  if (!match) {
    showFailToast('请粘贴邀请链接或邀请码')
    return
  }
  router.push(`/join/${match[1]}`)
}

async function logout() {
  try {
    await api.post('/auth/logout')
  } finally {
    clearSession()
    router.replace('/login')
  }
}
</script>

<template>
  <PageNav v-if="session.families.length > 0" back="/family" home />
  <BrandHeader
    :title="`你好，${session.user?.username ?? ''}`"
    subtitle="先创建一个家庭，或者加入家人的家庭"
  />

  <van-form @submit="create">
    <van-cell-group inset title="创建新家庭">
      <van-field
        v-model="familyName"
        label="家庭名称"
        placeholder="例如：我家"
        :rules="[{ required: true, message: '请输入家庭名称' }]"
      />
    </van-cell-group>
    <div class="block-button">
      <van-button round block type="primary" native-type="submit" :loading="creating">创建</van-button>
    </div>
  </van-form>

  <van-cell-group inset title="加入家人的家庭">
    <van-field v-model="inviteInput" label="邀请" placeholder="粘贴邀请链接或邀请码" />
  </van-cell-group>
  <div class="block-button">
    <van-button round block @click="join">加入</van-button>
  </div>

  <p class="hint center"><a href="#" @click.prevent="logout">退出登录</a></p>
</template>
