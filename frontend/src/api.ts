export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

let unauthorizedHandler: (() => void) | null = null
let familyGoneHandler: ((path: string) => void) | null = null

/** 业务接口返回 401（登录失效）时调用；/auth/* 自己处理，不触发。 */
export function onUnauthorized(handler: () => void) {
  unauthorizedHandler = handler
}

/** 业务接口返回 404 时调用，由处理函数判断是不是当前家庭已经不存在了。 */
export function onFamilyGone(handler: (path: string) => void) {
  familyGoneHandler = handler
}

type Method = 'GET' | 'POST' | 'PATCH' | 'DELETE'

async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: 'same-origin',
  })
  if (res.status === 204) return undefined as T
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith('/auth/')) unauthorizedHandler?.()
    if (res.status === 404) familyGoneHandler?.(path)
    let message = '请求失败，请稍后再试'
    const detail = data?.detail
    if (typeof detail === 'string') message = detail
    else if (Array.isArray(detail) && detail[0]?.msg) message = `输入有误：${detail[0].msg}`
    throw new ApiError(res.status, message)
  }
  return data as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body: unknown = {}) => request<T>('POST', path, body),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body),
  del: (path: string) => request<void>('DELETE', path),
}
