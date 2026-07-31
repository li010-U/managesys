import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { loginApi, getCurrentUserApi } from '../api/auth'
import type { UserInfo } from '../api/user'
import router from '../router'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('access_token') || '')
  const user = ref<UserInfo | null>(null)
  const isAuthenticated = ref(!!token.value)

  // 合并所有角色中的权限编码
  const userPermissions = computed(() => {
    if (!user.value) return []
    const codes = new Set<string>()
    for (const role of user.value.roles) {
      for (const code of role.permission_codes || []) {
        codes.add(code)
      }
    }
    return Array.from(codes)
  })

  function hasPermission(code: string): boolean {
    if (!user.value) return false
    if (user.value.is_super_admin) return true
    return userPermissions.value.includes(code)
  }

  async function login(username: string, password: string) {
    const res = await loginApi({ username, password })
    token.value = res.data.access_token
    localStorage.setItem('access_token', token.value)
    isAuthenticated.value = true
    try {
      await fetchUserInfo()
    } catch {
      user.value = null
    }
  }

  async function fetchUserInfo() {
    const res = await getCurrentUserApi()
    user.value = res.data
  }

  function logout() {
    token.value = ''
    user.value = null
    isAuthenticated.value = false
    localStorage.removeItem('access_token')
    router.push('/login')
  }

  return {
    token, user, isAuthenticated,
    userPermissions, hasPermission,
    login, fetchUserInfo, logout,
  }
})
