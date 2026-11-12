import { createRouter, createWebHistory } from 'vue-router'
import { loadSession, session } from './session'
import { safeRedirect, toastError } from './ui'

declare module 'vue-router' {
  interface RouteMeta {
    public?: boolean // 不需要登录
    noFamily?: boolean // 没有家庭也能访问
    tab?: boolean // 显示底部标签栏
  }
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('./views/LoginView.vue'), meta: { public: true } },
    { path: '/register', component: () => import('./views/RegisterView.vue'), meta: { public: true } },
    { path: '/onboarding', component: () => import('./views/OnboardingView.vue'), meta: { noFamily: true } },
    { path: '/join/:code', component: () => import('./views/JoinView.vue'), meta: { noFamily: true } },
    { path: '/', component: () => import('./views/SearchView.vue'), meta: { tab: true } },
    { path: '/scan', component: () => import('./views/ScanView.vue') },
    { path: '/locations', component: () => import('./views/LocationsView.vue'), meta: { tab: true } },
    { path: '/locations/new', component: () => import('./views/LocationEditView.vue') },
    { path: '/l/:id', component: () => import('./views/LocationView.vue') },
    { path: '/l/:id/edit', component: () => import('./views/LocationEditView.vue') },
    { path: '/items/new', component: () => import('./views/ItemEditView.vue') },
    { path: '/items/:id', component: () => import('./views/ItemView.vue') },
    { path: '/items/:id/edit', component: () => import('./views/ItemEditView.vue') },
    { path: '/family', component: () => import('./views/FamilyView.vue'), meta: { tab: true } },
    { path: '/print', component: () => import('./views/PrintView.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  if (!session.loaded) {
    try {
      await loadSession()
      session.loadError = false
    } catch (e) {
      // 网络或服务器错误：App.vue 显示重试页面，重试时再次导航到原来的页面
      toastError(e)
      session.loadError = true
      session.pendingPath = to.fullPath
      return false
    }
  }
  if (to.meta.public) return session.user ? safeRedirect(to.query.redirect) : true
  if (!session.user) return { path: '/login', query: { redirect: to.fullPath } }
  if (!to.meta.noFamily && session.families.length === 0) return '/onboarding'
  return true
})

export default router
