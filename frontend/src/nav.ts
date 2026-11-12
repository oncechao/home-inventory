import { reactive } from 'vue'

/**
 * 记住「位置」标签里最后看到的层级，切到别的标签再回来时还停在那里。
 * 存在 sessionStorage：刷新页面后还在，关掉标签页就忘掉。
 */
const KEY = 'lastLocation'

type LastLocation = { familyId: string; path: string } | null

function read(): LastLocation {
  try {
    return JSON.parse(sessionStorage.getItem(KEY) ?? 'null') as LastLocation
  } catch {
    return null
  }
}

export const nav = reactive({ lastLocation: read() })

export function rememberLocation(familyId: string, path: string) {
  nav.lastLocation = { familyId, path }
  try {
    sessionStorage.setItem(KEY, JSON.stringify(nav.lastLocation))
  } catch {
    /* 隐私模式等情况下不可用，忽略 */
  }
}

/** 「位置」标签应该去哪：当前家庭里最后看过的位置，没有就去顶层 */
export function locationTabTarget(familyId: string | null): string {
  const last = nav.lastLocation
  return last && last.familyId === familyId ? last.path : '/locations'
}
