<template>
  <div class="user-management">
    <div class="page-header">
      <div>
        <h3 class="page-title">用户管理</h3>
        <p class="page-desc">管理平台所有用户的账号信息与角色分配</p>
      </div>
    </div>

    <!-- 工具栏 -->
    <el-card class="search-card" :body-style="{ padding: '16px 20px' }">
      <el-row :gutter="16" align="middle">
        <el-col :span="6">
          <el-input v-model="keyword" placeholder="搜索用户名..." clearable @clear="handleSearch" @keyup.enter="handleSearch">
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
        <el-col :span="18" style="text-align: right">
          <el-button type="primary" @click="handleAdd">
            <el-icon><Plus /></el-icon>新增用户
          </el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 用户列表 -->
    <el-card :body-style="{ padding: 0 }" class="table-card">
      <el-table :data="users" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" align="center" />
        <el-table-column prop="username" label="用户名" width="130" />
        <el-table-column prop="real_name" label="真实姓名" width="110" />
        <el-table-column prop="email" label="邮箱" min-width="180" />
        <el-table-column prop="phone" label="手机号" width="125" />
        <el-table-column prop="department" label="部门" width="130" />
        <el-table-column label="角色" width="200">
          <template #default="{ row }">
            <el-tag v-for="role in row.roles" :key="role.id" size="small" style="margin: 1px 3px 1px 0">
              {{ role.name }}
            </el-tag>
            <span v-if="!row.roles?.length" class="empty-tag">-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-switch
              :model-value="row.is_active"
              :loading="row._loading"
              @click.prevent="toggleUserStatus(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right" align="center">
          <template #default="{ row }">
            <el-button text type="primary" :icon="Edit" @click="handleEdit(row)">编辑</el-button>
            <el-button text type="danger" :icon="Delete" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchUsers"
          @current-change="fetchUsers"
        />
      </div>
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑用户' : '新增用户'"
      width="600px"
      :close-on-click-modal="false"
      class="user-dialog"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="85px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="用户名" prop="username">
              <el-input v-model="form.username" :disabled="isEdit" placeholder="请输入用户名" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="密码" :prop="isEdit ? undefined : 'password'">
              <el-input v-model="form.password" type="password" show-password
                :placeholder="isEdit ? '留空则不修改' : '至少8位密码'" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="真实姓名" prop="real_name">
              <el-input v-model="form.real_name" placeholder="请输入真实姓名" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="邮箱" prop="email">
              <el-input v-model="form.email" placeholder="请输入邮箱" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="手机号" prop="phone">
              <el-input v-model="form.phone" placeholder="请输入手机号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="部门" prop="department">
              <el-input v-model="form.department" placeholder="请输入部门" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="岗位" prop="position">
              <el-input v-model="form.position" placeholder="请输入岗位" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-switch v-model="form.is_active" active-text="启用" inactive-text="停用" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="角色">
          <el-select v-model="form.roles" multiple placeholder="请选择角色" style="width: 100%">
            <el-option v-for="role in roles" :key="role.id" :label="role.name" :value="role.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确认 {{ isEdit ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, Edit, Delete } from '@element-plus/icons-vue'
import { getUsersApi, createUserApi, updateUserApi, deleteUserApi } from '../../api/user'
import { getRolesApi } from '../../api/role'
import type { UserInfo } from '../../api/user'
import type { RoleInfo } from '../../api/role'
import type { FormInstance, FormRules } from 'element-plus'

const loading = ref(false)
const users = ref<UserInfo[]>([])
const roles = ref<RoleInfo[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const keyword = ref('')
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitLoading = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()

const form = ref({
  username: '',
  password: '',
  real_name: '',
  email: '',
  phone: '',
  department: '',
  position: '',
  is_active: true,
  roles: [] as number[],
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码至少8位', trigger: 'blur' },
  ],
}

onMounted(() => {
  fetchUsers()
  fetchRoles()
})

async function fetchUsers() {
  loading.value = true
  try {
    const res = await getUsersApi({ page: page.value, page_size: pageSize.value, keyword: keyword.value || undefined })
    users.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

async function fetchRoles() {
  try {
    const res = await getRolesApi()
    roles.value = res.data
  } catch { /* ignore */ }
}

function handleSearch() {
  page.value = 1
  fetchUsers()
}

function resetForm() {
  form.value = {
    username: '',
    password: '',
    real_name: '',
    email: '',
    phone: '',
    department: '',
    position: '',
    is_active: true,
    roles: [],
  }
}

function handleAdd() {
  isEdit.value = false
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function handleEdit(row: UserInfo) {
  isEdit.value = true
  editingId.value = row.id
  form.value = {
    username: row.username,
    password: '',
    real_name: row.real_name || '',
    email: row.email || '',
    phone: row.phone || '',
    department: row.department || '',
    position: row.position || '',
    is_active: row.is_active,
    roles: row.roles?.map(r => r.id) || [],
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitLoading.value = true
  try {
    if (isEdit.value && editingId.value) {
      const data: any = { ...form.value }
      delete data.username
      if (!data.password) delete data.password
      await updateUserApi(editingId.value, data)
      ElMessage.success('用户信息已更新')
    } else {
      await createUserApi({ ...form.value })
      ElMessage.success('用户创建成功')
    }
    dialogVisible.value = false
    fetchUsers()
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '操作失败')
  } finally {
    submitLoading.value = false
  }
}

function toggleUserStatus(row: UserInfo) {
  row._loading = true
  const newStatus = !row.is_active
  updateUserApi(row.id, { is_active: newStatus })
    .then(() => {
      ElMessage.success(newStatus ? '用户已启用' : '用户已停用')
      fetchUsers()
    })
    .catch(() => {})
    .finally(() => { row._loading = false })
}

async function handleDelete(row: UserInfo) {
  try {
      await ElMessageBox.confirm(`确定要停用用户 "${row.username}" 吗？停用后该用户将无法登录系统。`, '确认操作', {
      type: 'warning',
      confirmButtonText: '确定停用',
      cancelButtonText: '取消',
    })
    await deleteUserApi(row.id)
    ElMessage.success('用户已停用')
    fetchUsers()
  } catch { /* cancelled */ }
}
</script>

<style scoped>
.page-header {
  margin-bottom: 16px;
}
.page-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin: 0;
}
.page-desc {
  font-size: 13px;
  color: #909399;
  margin: 4px 0 0;
}
.search-card {
  margin-bottom: 16px;
  border-radius: 10px;
}
.table-card {
  border-radius: 10px;
}
.pagination-wrap {
  padding: 16px 20px;
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid #f0f2f5;
}
.empty-tag {
  color: #c0c4cc;
}
.user-dialog :deep(.el-dialog__body) {
  padding: 16px 24px;
}
</style>
