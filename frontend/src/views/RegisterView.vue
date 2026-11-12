<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { loadSession } from '../session'
import { safeRedirect, toastError } from '../ui'

const route = useRoute()
const router = useRouter()
const username = ref('')
const password = ref('')
const confirm = ref('')
const loading = ref(false)

const usernameRule = {
  validator: (v: string) => /^[\p{L}\p{N}_]{3,50}$/u.test(v.trim()),
  message: '3-50 个字符，只能用中文、字母、数字或下划线',
}

async function submit() {
  loading.value = true
  try {
    await api.post('/auth/register', { username: username.value.trim(), password: password.value })
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
  <van-nav-bar title="注册" />
  <van-form @submit="submit">
    <van-cell-group inset style="margin-top: 16px">
      <van-field
        v-model="username"
        label="用户名"
        placeholder="3-50 个字符"
        autocomplete="username"
        :rules="[{ required: true, message: '请输入用户名' }, usernameRule]"
      />
      <van-field
        v-model="password"
        type="password"
        label="密码"
        placeholder="至少 8 位"
        autocomplete="new-password"
        :rules="[{ validator: (v: string) => v.length >= 8, message: '密码至少 8 位' }]"
      />
      <van-field
        v-model="confirm"
        type="password"
        label="确认密码"
        placeholder="再输入一次"
        autocomplete="new-password"
        :rules="[{ validator: (v: string) => v === password, message: '两次输入的密码不一致' }]"
      />
    </van-cell-group>
    <div class="block-button">
      <van-button round block type="primary" native-type="submit" :loading="loading">注册</van-button>
    </div>
  </van-form>
  <p class="hint center">
    已有账号？<router-link :to="{ path: '/login', query: route.query }">登录</router-link>
  </p>
</template>
