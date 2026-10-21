import { reactive } from 'vue'

export interface CurrentUser {
  id: string; username: string; personId: string; displayName: string
  role: 'admin' | 'user'; systemAdmin: boolean; labIds: string[]
  mustChangePassword: boolean; csrfToken: string
}

export const auth = reactive<{ user: CurrentUser | null; ready: boolean }>({ user: null, ready: false })

/** Central fetch boundary also protects legacy API/SSE clients. No token is persisted. */
const nativeFetch = window.fetch.bind(window)
window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = new URL(input instanceof Request ? input.url : String(input), window.location.origin)
  if (url.origin !== window.location.origin || !url.pathname.startsWith('/api/')) return nativeFetch(input, init)
  const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined))
  const method = (init?.method ?? (input instanceof Request ? input.method : 'GET')).toUpperCase()
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && auth.user) headers.set('X-CSRF-Token', auth.user.csrfToken)
  const response = await nativeFetch(input, { ...init, headers, credentials: 'same-origin' })
  if (response.status === 401 && !url.pathname.startsWith('/api/auth/')) {
    clearPrivateStorage()
    auth.user = null
    window.location.replace('/login?expired=1')
  }
  return response
}

export function clearPrivateStorage() {
  for (const key of Object.keys(localStorage)) {
    if (key.startsWith('nexus-workspace') || key === 'nexus-chat') localStorage.removeItem(key)
  }
}

export async function api<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { detail?: string | { message?: string } | { msg: string }[] }
    const detail = body.detail
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(v => v.msg).join('；') : detail?.message ?? `请求失败（${response.status}）`)
  }
  return response.json() as Promise<T>
}

export async function loadUser() {
  try { auth.user = await api<CurrentUser>('/api/auth/me') }
  catch { auth.user = null }
  auth.ready = true
}

export async function login(username: string, password: string) {
  clearPrivateStorage()
  await api('/api/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) })
  await loadUser()
  if (!auth.user) throw new Error('无法取得登录身份，请检查浏览器是否允许会话 Cookie')
}

export async function logout() {
  await api('/api/auth/logout', { method: 'POST' })
  auth.user = null
  clearPrivateStorage()
  window.location.replace('/login')
}
