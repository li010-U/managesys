<template>
  <div class="error-page">
    <div class="error-content">
      <div class="error-code">403</div>
      <div class="error-divider"></div>
      <h2 class="error-title">权限不足</h2>
      <p class="error-desc">您没有访问此页面的权限，请联系管理员</p>
      <div class="error-actions">
        <el-button type="primary" size="large" @click="router.push('/dashboard')">
          返回工作台
        </el-button>
      </div>
    </div>
    <div class="error-bg-shape"></div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from "vue-router"
const router = useRouter()
</script>

<style scoped>
.error-page {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}
.error-content {
  text-align: center;
  z-index: 1;
  animation: fadeInUp 0.6s ease;
}
.error-code {
  font-size: 120px;
  font-weight: 800;
  background: linear-gradient(135deg, #e67e22, #f39c12, #f1c40f);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  line-height: 1;
  margin-bottom: 8px;
}
.error-divider {
  width: 60px;
  height: 3px;
  background: linear-gradient(90deg, #e67e22, #f1c40f);
  border-radius: 2px;
  margin: 0 auto 24px;
}
.error-title {
  font-size: 24px;
  color: var(--app-text-primary);
  margin: 0 0 8px;
}
.error-desc {
  font-size: 14px;
  color: var(--app-text-muted);
  margin: 0 0 32px;
}
.error-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}
.error-bg-shape {
  position: absolute;
  width: 600px;
  height: 600px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(243,156,18,0.05) 0%, transparent 70%);
  top: -200px;
  right: -100px;
  pointer-events: none;
}
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(30px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>