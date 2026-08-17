import { defineStore } from "pinia"
import { ref } from "vue"

const STORAGE_KEY = "assistant_visible"

export const useUiStore = defineStore("ui", () => {
  const assistantVisible = ref(localStorage.getItem(STORAGE_KEY) !== "0")

  function setAssistantVisible(val: boolean) {
    assistantVisible.value = val
    localStorage.setItem(STORAGE_KEY, val ? "1" : "0")
  }

  function toggleAssistant() {
    setAssistantVisible(!assistantVisible.value)
  }

  return { assistantVisible, setAssistantVisible, toggleAssistant }
})
