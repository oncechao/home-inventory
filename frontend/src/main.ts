import { createApp } from 'vue'
import Vant from 'vant'
import 'vant/lib/index.css'
import './style.css'
import App from './App.vue'
import router from './router'
import { onUnauthorized } from './api'
import { clearSession } from './session'

onUnauthorized(() => {
  clearSession()
  router.replace({ path: '/login', query: { redirect: router.currentRoute.value.fullPath } })
})

createApp(App).use(Vant).use(router).mount('#app')
