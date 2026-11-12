<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { loadSession } from '../session'
import BrandHeader from '../components/BrandHeader.vue'
import { safeRedirect, toastError } from '../ui'

const route = useRoute()
const router = useRouter()
const username = ref('')
const password = ref('')
const loading = ref(false)

async function submit() {
  loading.value = true
  try {
    await api.post('/auth/login', { username: username.value, password: password.value })
    await loadSession()
    router.replace(safeRedirect(route.query.redirect))
  } catch (e) {
    toastError(e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <BrandHeader title="家庭物品管理" subtitle="记住家里每样东西放在哪" />
  <van-form @submit="submit">
    <van-cell-group inset>
      <van-field
        v-model="username"
        label="用户名"
        placeholder="用户名"
        autocomplete="username"
        :rules="[{ required: true, message: '请输入用户名' }]"
      />
      <van-field
        v-model="password"
        type="password"
        label="密码"
        placeholder="密码"
        autocomplete="current-password"
        :rules="[{ required: true, message: '请输入密码' }]"
      />
    </van-cell-group>
    <div class="block-button">
      <van-button round block type="primary" native-type="submit" :loading="loading">登录</van-button>
    </div>
  </van-form>
  <p class="hint center">
    还没有账号？<router-link :to="{ path: '/register', query: route.query }">注册</router-link>
  </p>
</template>
