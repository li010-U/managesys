import { ref, watch } from "vue"

const isDark = ref(localStorage.getItem("theme") === "dark")

if (isDark.value) {
  document.documentElement.classList.add("dark")
} else {
  document.documentElement.classList.remove("dark")
}

export function useTheme() {
  function toggleTheme() {
    isDark.value = !isDark.value
    applyTheme()
  }

  function setTheme(dark: boolean) {
    isDark.value = dark
    applyTheme()
  }

  function applyTheme() {
    if (isDark.value) {
      document.documentElement.classList.add("dark")
    } else {
      document.documentElement.classList.remove("dark")
    }
    localStorage.setItem("theme", isDark.value ? "dark" : "light")
  }

  return { isDark, toggleTheme, setTheme }
}