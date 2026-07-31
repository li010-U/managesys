<template>
  <div class="profile-page">
    <el-card class="profile-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">个人中心</span>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <!-- 个人信息 -->
        <el-tab-pane label="个人信息" name="info">
          <div class="profile-info">
            <div class="avatar-section">
              <el-avatar :size="80" class="profile-avatar">
                {{ userNameInitial }}
              </el-avatar>
              <div class="avatar-text">
                <div class="display-name">{{ authStore.user?.real_name || authStore.user?.username }}</div>
                <div class="display-role">{{ roleNames }}</div>
              </div>
            </div>

            <el-divider />

            <el-descriptions :column="1" border class="info-table">
              <el-descriptions-item label="用户名" width="120px">
                {{ authStore.user?.username }}
              </el-descriptions-item>
              <el-descriptions-item label="真实姓名">
                {{ authStore.user?.real_name || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="邮箱">
                {{ authStore.user?.email || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="手机号">
                {{ authStore.user?.phone || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="部门">
                {{ authStore.user?.department || '设计总院' }}
              </el-descriptions-item>
              <el-descriptions-item label="最后登录">
                {{ authStore.user?.last_login ? formatDate(authStore.user.last_login) : '-' }}
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </el-tab-pane>

        <!-- 修改密码 -->
        <el-tab-pane label="修改密码" name="password">
          <el-form
            ref="formRef"
            :model="pwdForm"
            :rules="pwdRules"
            label-width="100px"
            class="pwd-form"
            @keyup.enter="handleChangePassword"
          >
            <el-form-item label="原密码" prop="old_password">
              <el-input
                v-model="pwdForm.old_password"
                type="password"
                show-password
                placeholder="请输入原密码"
                style="max-width: 360px"
              />
            </el-form-item>

            <el-form-item label="新密码" prop="new_password">
              <el-input
                v-model="pwdForm.new_password"
                type="password"
                show-password
                placeholder="请输入新密码（至少8位，包含字母和数字）"
                style="max-width: 360px"
              />
            </el-form-item>

            <el-form-item label="确认新密码" prop="confirm_password">
              <el-input
                v-model="pwdForm.confirm_password"
                type="password"
                show-password
                placeholder="请再次输入新密码"
                style="max-width: 360px"
              />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :loading="pwdLoading" @click="handleChangePassword">
                确认修改
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../../stores/auth'
import { changePasswordApi } from '../../api/auth'
import type { FormInstance, FormRules } from 'element-plus'

const authStore = useAuthStore()
const activeTab = ref('info')
const formRef = ref<FormInstance>()
const pwdLoading = ref(false)

const userNameInitial = computed(() => {
  const name = authStore.user?.real_name || authStore.user?.username || 'U'
  return name.charAt(0).toUpperCase()
})

const roleNames = computed(() => {
  return authStore.user?.roles?.map(r => r.name).join('、') || '-'
})

const pwdForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const pwdRules: FormRules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, message: '密码长度不能少于8位', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    {
      validator: (_rule: any, value: string, callback: any) => {
        if (value !== pwdForm.new_password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

function formatDate(dateStr: string) {
  const d = new Date(dateStr)
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}

async function handleChangePassword() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  pwdLoading.value = true
  try {
    await changePasswordApi({
      old_password: pwdForm.old_password,
      new_password: pwdForm.new_password,
    })
    ElMessage.success('密码修改成功')
    pwdForm.old_password = ''
    pwdForm.new_password = ''
    pwdForm.confirm_password = ''
  } catch {
    // Error handled by interceptor
  } finally {
    pwdLoading.value = false
  }
}
</script>

<style scoped>
.profile-page {
  max-width: 800px;
  margin: 0;
}
.profile-card {
  border-radius: 10px;
}
.card-title {
  font-size: 16px;
  font-weight: 600;
}
.profile-info {
  padding: 8px 0;
}
.avatar-section {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 8px 0;
}
.profile-avatar {
  background: linear-gradient(135deg, #1a5276, #2980b9);
  color: #fff;
  font-size: 28px;
  font-weight: 600;
  flex-shrink: 0;
}
.display-name {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}
.display-role {
  font-size: 14px;
  color: #2980b9;
  margin-top: 4px;
}
.pwd-form {
  max-width: 460px;
  padding: 16px 0;
}
</style>
