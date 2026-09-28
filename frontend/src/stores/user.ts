import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { auth as authApi, system } from '@/api'
import { sessionKey } from '@/config/runtime'

export interface UserInfo {
  id: number
  username: string
  email: string
  role: string
  full_name: string
  student_no: string
  avatar: string
  is_active: boolean
}

export const useUserStore = defineStore('user', () => {
  function readCachedUser(): UserInfo | null {
    const raw = localStorage.getItem(sessionKey('user'))
    if (!raw) return null
    try {
      const parsed = JSON.parse(raw)
      if (!parsed || typeof parsed !== 'object' || !parsed.id || !parsed.role) throw new Error('invalid user cache')
      return parsed as UserInfo
    } catch {
      localStorage.removeItem(sessionKey('user'))
      localStorage.removeItem(sessionKey('token'))
      return null
    }
  }

  const cachedUser = readCachedUser()
  const token = ref(cachedUser ? (localStorage.getItem(sessionKey('token')) || '') : '')
  const user = ref<UserInfo | null>(cachedUser)
  const demoMode = ref(false)
  const engineInfo = ref<Record<string, any>>({})

  const isLogin = computed(() => !!token.value)
  const role = computed(() => user.value?.role || '')

  function setToken(t: string) {
    token.value = t
    localStorage.setItem(sessionKey('token'), t)
  }
  function setUser(u: UserInfo) {
    user.value = u
    localStorage.setItem(sessionKey('user'), JSON.stringify(u))
  }
  async function login(username: string, password: string) {
    const data: any = await authApi.login({ username, password })
    setToken(data.access_token)
    setUser(data.user)
    return data
  }
  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem(sessionKey('token'))
    localStorage.removeItem(sessionKey('user'))
  }
  async function fetchMe() {
    try {
      const u: any = await authApi.me()
      setUser(u)
      return true
    } catch {
      logout()
      return false
    }
  }
  async function checkDemo() {
    try {
      const info: any = await system.info()
      engineInfo.value = info || {}
      demoMode.value = !!((info.demo_mode ?? info.is_mock_llm) || info.degraded)
    } catch {
      engineInfo.value = {}
      demoMode.value = true
    }
  }
  return { token, user, demoMode, engineInfo, isLogin, role, setToken, setUser, login, logout, fetchMe, checkDemo }
})
