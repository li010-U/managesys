<template>
  <router-view v-slot="{ Component, route }">
    <transition name="page-fade" mode="out-in">
      <component :is="Component" :key="route.path" />
    </transition>
  </router-view>
</template>

<script setup lang="ts">
import { watch } from 'vue'
import { useRoute } from 'vue-router'
import NProgress from 'nprogress'

const route = useRoute()

// 路由切换时自动关闭 NProgress
watch(() => route.path, () => {
  NProgress.done()
})
</script>