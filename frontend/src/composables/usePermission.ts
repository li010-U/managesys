import { useAuthStore } from '../stores/auth'

export function usePermission() {
  const authStore = useAuthStore()

  function hasPermission(code: string): boolean {
    return authStore.hasPermission(code)
  }

  function hasAnyPermission(codes: string[]): boolean {
    return codes.some(code => authStore.hasPermission(code))
  }

  function hasAllPermissions(codes: string[]): boolean {
    return codes.every(code => authStore.hasPermission(code))
  }

  return { hasPermission, hasAnyPermission, hasAllPermissions }
}
