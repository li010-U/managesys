import type { Directive } from 'vue'
import { useAuthStore } from '../stores/auth'

export const vPermission: Directive<HTMLElement, string | string[]> = {
  mounted(el, binding) {
    const authStore = useAuthStore()
    const value = binding.value
    let hasAccess = false

    if (typeof value === 'string') {
      hasAccess = authStore.hasPermission(value)
    } else if (Array.isArray(value)) {
      hasAccess = value.some(code => authStore.hasPermission(code))
    }

    if (!hasAccess) {
      el.parentNode?.removeChild(el)
    }
  },
}
