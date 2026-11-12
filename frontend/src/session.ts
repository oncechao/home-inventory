import { reactive } from 'vue'
import { api, ApiError } from './api'
import type { Family, User } from './types'

const KEY = 'currentFamilyId'

function readSaved(): string | null {
  try {
    return localStorage.getItem(KEY)
  } catch {
    return null
  }
}

function save(id: string | null) {
  try {
    if (id) localStorage.setItem(KEY, id)
    else localStorage.removeItem(KEY)
  } catch {
    /* 隐私模式等情况下 localStorage 不可用，忽略 */
  }
}

export const session = reactive({
  loaded: false,
  user: null as User | null,
  families: [] as Family[],
  currentFamilyId: null as string | null,
})

export function currentFamily(): Family | null {
  return session.families.find((f) => f.id === session.currentFamilyId) ?? null
}

export function setCurrentFamily(id: string) {
  session.currentFamilyId = id
  save(id)
}

export async function refreshFamilies() {
  session.families = await api.get<Family[]>('/families')
  const preferred = session.currentFamilyId ?? readSaved()
  const pick = session.families.find((f) => f.id === preferred) ?? session.families[0] ?? null
  session.currentFamilyId = pick?.id ?? null
  save(session.currentFamilyId)
}

export function clearSession() {
  session.user = null
  session.families = []
  session.currentFamilyId = null
}

export async function loadSession() {
  try {
    session.user = await api.get<User>('/auth/me')
    await refreshFamilies()
  } catch (e) {
    if (!(e instanceof ApiError && e.status === 401)) throw e
    clearSession()
  }
  session.loaded = true
}
