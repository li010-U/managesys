<template>
  <el-tooltip :content="theme.isDark.value ? '切换亮色模式' : '切换暗色模式'" placement="bottom">
    <el-icon :size="18" class="action-icon theme-toggle" @click="theme.toggleTheme()">
      <i :class="theme.isDark.value ? 'icon-sun' : 'icon-moon'" class="theme-icon">
        <svg v-if="theme.isDark.value" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="5"/>
          <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
          <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
        </svg>
        <svg v-else viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
      </i>
    </el-icon>
  </el-tooltip>
</template>

<script setup lang="ts">
import { useTheme } from "../composables/useTheme"
const theme = useTheme()
</script>

<style scoped>
.theme-toggle {
  transition: transform 0.5s;
}
.theme-toggle:hover {
  transform: rotate(30deg);
}
.theme-icon {
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>