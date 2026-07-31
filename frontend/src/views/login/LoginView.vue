<template>
  <div class="login-page">
    <div class="login-bg-decoration">
      <div class="circle c1"></div>
      <div class="circle c2"></div>
      <div class="circle c3"></div>
      <div class="grid-pattern"></div>
    </div>

    <div class="login-container">
      <!-- 左侧品牌区 -->
      <div class="login-brand">
        <div class="brand-content">
          <div class="brand-logo">
            <img src="/logo.png" alt="设计总院" class="logo-img" />
          </div>
          <h1 class="brand-title">设计总院</h1>
          <p class="brand-subtitle">数据中心资源智能管理系统</p>
          <div class="brand-divider"></div>
          <p class="brand-desc">智能化管理 · 可视化运维 · 全方位监控</p>
          <div class="brand-features">
            <div class="feature-item" style="animation-delay: 0.1s">
              <span class="feature-dot"></span>
              <span>机房平面可视化</span>
            </div>
            <div class="feature-item" style="animation-delay: 0.2s">
              <span class="feature-dot"></span>
              <span>设备全生命周期管理</span>
            </div>
            <div class="feature-item" style="animation-delay: 0.3s">
              <span class="feature-dot"></span>
              <span>智能监控与告警</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧登录区 -->
      <div class="login-form-section">
        <div class="form-wrapper">
          <div class="form-header">
            <h2 class="form-title">欢迎登录</h2>
            <p class="form-desc">请使用您的账号登录系统</p>
          </div>

          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            size="large"
            class="login-form"
            @keyup.enter="handleLogin"
          >
            <el-form-item prop="username">
              <el-input
                v-model="form.username"
                placeholder="用户名"
                :prefix-icon="User"
                class="custom-input"
              />
            </el-form-item>

            <el-form-item prop="password">
              <el-input
                v-model="form.password"
                type="password"
                placeholder="密码"
                show-password
                :prefix-icon="Lock"
                class="custom-input"
              />
            </el-form-item>

            <div class="form-options">
              <el-checkbox v-model="form.remember">记住用户名</el-checkbox>
            </div>

            <el-form-item>
              <el-button
                type="primary"
                :loading="loading"
                class="login-btn"
                @click="handleLogin"
              >
                <template v-if="loading">
                  <span class="loading-dots">
                    <span class="dot"></span>
                    <span class="dot"></span>
                    <span class="dot"></span>
                  </span>
                </template>
                <template v-else>登 录</template>
              </el-button>
            </el-form-item>
          </el-form>

          <div class="form-footer">
            <p class="copyright">&copy; 2026 设计总院</p>
            <p class="dev-hint">开发账号: admin / admin@123456</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useAuthStore } from '../../stores/auth'
import type { FormInstance, FormRules } from 'element-plus'

const router = useRouter()
const authStore = useAuthStore()
const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  username: 'admin',
  password: 'admin@123456',
  remember: true,
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

onMounted(() => {
  const saved = localStorage.getItem('remembered_username')
  if (saved) {
    form.username = saved
    form.remember = true
  }
})

async function handleLogin() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  if (form.remember) {
    localStorage.setItem('remembered_username', form.username)
  } else {
    localStorage.removeItem('remembered_username')
  }

  loading.value = true
  try {
    await authStore.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '登录失败，请检查用户名和密码')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0c2136 0%, #1a5276 30%, #1f6f8b 70%, #2c8c99 100%);
  position: relative;
  overflow: hidden;
}
.login-bg-decoration {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.circle {
  position: absolute;
  border-radius: 50%;
  opacity: 0.08;
  animation: float 20s ease-in-out infinite;
}
.c1 { width: 600px; height: 600px; background: radial-gradient(circle, #fff 0%, transparent 70%); top: -200px; right: -100px; animation-delay: 0s; }
.c2 { width: 400px; height: 400px; background: radial-gradient(circle, #64b5f6 0%, transparent 70%); bottom: -100px; left: -100px; animation-delay: -5s; }
.c3 { width: 300px; height: 300px; background: radial-gradient(circle, #4dd0e1 0%, transparent 70%); bottom: 30%; right: 10%; animation-delay: -10s; }
.grid-pattern {
  position: absolute;
  inset: 0;
  background-image: linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
  background-size: 60px 60px;
}
@keyframes float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  25% { transform: translate(30px, -30px) scale(1.05); }
  50% { transform: translate(-20px, 20px) scale(0.95); }
  75% { transform: translate(20px, 30px) scale(1.02); }
}

.login-container {
  display: flex;
  width: 1000px;
  max-width: 90vw;
  min-height: 580px;
  background: rgba(255,255,255,0.06);
  border-radius: 24px;
  backdrop-filter: blur(20px);
  box-shadow: 0 25px 80px rgba(0,0,0,0.4);
  overflow: hidden;
  position: relative;
  z-index: 1;
  animation: containerIn 0.6s cubic-bezier(0.25, 0.8, 0.25, 1);
}
@keyframes containerIn {
  from { opacity: 0; transform: scale(0.95) translateY(20px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

.login-brand {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
  background: linear-gradient(160deg, rgba(26,82,118,0.9) 0%, rgba(15,45,75,0.85) 100%);
  position: relative;
}
.login-brand::after {
  content: '';
  position: absolute;
  right: 0;
  top: 10%;
  height: 80%;
  width: 1px;
  background: linear-gradient(to bottom, transparent, rgba(255,255,255,0.2), transparent);
}
.brand-content { text-align: center; color: #fff; }
.brand-logo { margin-bottom: 16px; }
.logo-img { height: 56px; filter: brightness(0) invert(1); }
.brand-title {
  font-size: 22px; font-weight: 700; letter-spacing: 2px; margin: 0 0 8px;
  background: linear-gradient(90deg, #fff, #90caf9);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.brand-subtitle { font-size: 15px; opacity: 0.8; margin: 0 0 24px; letter-spacing: 4px; }
.brand-divider { width: 60px; height: 3px; background: linear-gradient(90deg, #64b5f6, #4dd0e1); border-radius: 2px; margin: 0 auto 24px; }
.brand-desc { font-size: 13px; opacity: 0.6; margin: 0 0 32px; letter-spacing: 2px; }
.brand-features { display: flex; flex-direction: column; gap: 14px; align-items: flex-start; max-width: 220px; margin: 0 auto; }
.feature-item {
  display: flex; align-items: center; gap: 10px; font-size: 13px; opacity: 0.75;
  animation: slideInLeft 0.5s ease both;
}
@keyframes slideInLeft {
  from { opacity: 0; transform: translateX(-20px); }
  to { opacity: 1; transform: translateX(0); }
}
.feature-dot { width: 6px; height: 6px; border-radius: 50%; background: #4dd0e1; flex-shrink: 0; animation: pulse-glow 2s ease-in-out infinite; }
@keyframes pulse-glow {
  0%, 100% { opacity: 0.6; box-shadow: 0 0 0 0 rgba(77,208,225,0.4); }
  50% { opacity: 1; box-shadow: 0 0 6px 2px rgba(77,208,225,0.2); }
}

.login-form-section { width: 440px; display: flex; align-items: center; justify-content: center; padding: 48px; background: rgba(255,255,255,0.95); }
.form-wrapper { width: 100%; max-width: 340px; }
.form-header { margin-bottom: 32px; }
.form-title { font-size: 26px; font-weight: 700; color: #1a5276; margin: 0 0 6px; }
.form-desc { font-size: 14px; color: #909399; margin: 0; }

.custom-input :deep(.el-input__wrapper) {
  border-radius: 10px;
  padding: 4px 16px;
  box-shadow: 0 0 0 1px #e4e7ed inset;
  transition: all 0.3s;
}
.custom-input :deep(.el-input__wrapper:hover) { box-shadow: 0 0 0 1px #1a5276 inset; }
.custom-input :deep(.el-input__wrapper.is-focus) { box-shadow: 0 0 0 2px #1a5276 inset; }

.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: -8px 0 16px;
}
.form-options :deep(.el-checkbox__label) { font-size: 13px; color: #909399; }

.login-btn {
  width: 100%;
  height: 46px;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 6px;
  background: linear-gradient(135deg, #1a5276, #2980b9);
  border: none;
  transition: all 0.3s;
  margin-top: 4px;
}
.login-btn:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(26,82,118,0.4); }
.login-btn:active { transform: translateY(0); }

/* Loading dots */
.loading-dots { display: flex; gap: 4px; align-items: center; }
.dot {
  width: 6px; height: 6px; background: #fff; border-radius: 50%;
  animation: bounce 1s ease-in-out infinite;
}
.dot:nth-child(2) { animation-delay: 0.15s; }
.dot:nth-child(3) { animation-delay: 0.3s; }
@keyframes bounce {
  0%, 80%, 100% { transform: translateY(0); }
  40% { transform: translateY(-6px); }
}

.form-footer { text-align: center; margin-top: 16px; }
.copyright { font-size: 12px; color: #c0c4cc; margin: 0 0 4px; }
.dev-hint { font-size: 11px; color: #dcdfe6; margin: 0; }
</style>