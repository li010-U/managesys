<template>
  <router-view v-slot="{ Component, route }">
    <transition name="page-fade">
      <component :is="Component" :key="route.path" />
    </transition>
  </router-view>
</template>

<script setup lang="ts">
// 路由进度条由 router/index.ts 统一管理，保证快速连续切换时 start/done 配对
</script>


