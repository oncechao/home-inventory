import { showFailToast } from 'vant'
import type { Router } from 'vue-router'
import { ApiError } from './api'

export function toastError(e: unknown) {
  showFailToast(e instanceof ApiError ? e.message : '网络错误，请重试')
}

export function pathText(path: { name: string }[]): string {
  return path.map((p) => p.name).join(' › ')
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}

/** 只接受站内路径，防止 ?redirect= 被拿来跳到外站 */
export function safeRedirect(value: unknown): string {
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//') ? value : '/'
}

/** 有站内历史就返回上一页，否则去 fallback（例如扫码直接打开的页面） */
export function goBack(router: Router, fallback: string) {
  if (window.history.state?.back) router.back()
  else router.replace(fallback)
}
