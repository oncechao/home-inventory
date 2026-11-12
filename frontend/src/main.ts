import { createApp } from 'vue'
import Vant from 'vant'
import 'vant/lib/index.css'
import './style.css'
import App from './App.vue'
import router from './router'
import { onFamilyGone, onUnauthorized } from './api'
import { clearSession, refreshFamilies, session } from './session'

onUnauthorized(() => {
  if (router.currentRoute.value.path === '/login') return
  clearSession()
  router.replace({ path: '/login', query: { redirect: router.currentRoute.value.fullPath } })
})

// 当前家庭在别的设备上被解散、或自己被移出时，接口会返回 404
onFamilyGone(async (path) => {
  const fid = session.currentFamilyId
  if (!fid || !new RegExp(`^/families/${fid}(/|$)`).test(path)) return
  try {
    await refreshFamilies()
  } catch {
    return
  }
  // 家庭还在（只是某个位置或物品不存在）时留在当前页面
  if (session.families.some((f) => f.id === fid)) return
  router.replace(session.families.length ? '/' : '/onboarding')
})

createApp(App).use(Vant).use(router).mount('#app')
