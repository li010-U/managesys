<template>
  <div class="role-management">
    <div class="page-header">
      <div>
        <h3 class="page-title">角色管理</h3>
        <p class="page-desc">管理系统角色与权限分配，内置角色不可删除</p>
      </div>
    </div>

    <el-card :body-style="{ padding: 0 }" class="table-card">
      <div class="table-header">
        <span class="table-title">角色列表</span>
        <el-button type="primary" :icon="Plus" @click="handleAdd">新增角色</el-button>
      </div>

      <el-table :data="roles" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" align="center" />
        <el-table-column prop="name" label="角色名称" width="140" />
        <el-table-column prop="code" label="角色编码" width="140" />
        <el-table-column prop="description" label="描述" min-width="200" />
        <el-table-column label="权限数" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.permissions?.length || 0 }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_builtin ? 'warning' : 'info'" size="small" effect="light">
              {{ row.is_builtin ? '内置' : '自定义' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" align="center">
          <template #default="{ row }">
            <el-button text type="primary" :icon="Edit" @click="handleEdit(row)">编辑</el-button>
            <el-button text type="danger" :icon="Delete" :disabled="row.is_builtin" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 角色编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑角色' : '新增角色'"
      width="720px"
      :close-on-click-modal="false"
      class="role-dialog"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="85px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="角色名称" prop="name">
              <el-input v-model="form.name" placeholder="请输入角色名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="角色编码" prop="code">
              <el-input v-model="form.code" :disabled="isEdit" placeholder="如：device_admin" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="请输入角色描述" />
        </el-form-item>
        <el-form-item label="权限分配">
          <div class="perm-tree-container">
            <el-tree
              ref="treeRef"
              :data="permissionTree"
              :props="{ label: 'name', children: 'children' }"
              show-checkbox
              node-key="id"
              default-expand-all
              :default-checked-keys="checkedKeys"
              check-strictly
            />
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确认{{ isEdit ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete } from '@element-plus/icons-vue'
import { getRolesApi, createRoleApi, updateRoleApi, deleteRoleApi, getPermissionsApi } from '../../api/role'
import type { RoleInfo, PermissionInfo } from '../../api/role'
import type { FormInstance, FormRules } from 'element-plus'
import type { ElTree } from 'element-plus'

const loading = ref(false)
const roles = ref<RoleInfo[]>([])
const permissions = ref<PermissionInfo[]>([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitLoading = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const treeRef = ref<InstanceType<typeof ElTree>>()
const checkedKeys = ref<number[]>([])

const form = ref({
  name: '',
  code: '',
  description: '',
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入角色编码', trigger: 'blur' }],
}

const permissionTree = computed(() => {
  const moduleMap = new Map<string, PermissionInfo[]>()
  for (const p of permissions.value) {
    if (!moduleMap.has(p.module)) {
      moduleMap.set(p.module, [])
    }
    moduleMap.get(p.module)!.push(p)
  }
  return Array.from(moduleMap.entries()).map(([module, perms]) => ({
    id: module,
    name: module,
    children: perms.map(p => ({ ...p })),
  }))
})

onMounted(() => {
  fetchRoles()
  fetchPermissions()
})

async function fetchRoles() {
  loading.value = true
  try {
    const res = await getRolesApi()
    roles.value = res.data
  } finally {
    loading.value = false
  }
}

async function fetchPermissions() {
  try {
    const res = await getPermissionsApi()
    permissions.value = res.data
  } catch { /* ignore */ }
}

function handleAdd() {
  isEdit.value = false
  editingId.value = null
  form.value = { name: '', code: '', description: '' }
  checkedKeys.value = []
  dialogVisible.value = true
}

function handleEdit(row: RoleInfo) {
  isEdit.value = true
  editingId.value = row.id
  form.value = {
    name: row.name,
    code: row.code,
    description: row.description || '',
  }
  checkedKeys.value = row.permissions?.map(p => p.id) || []
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitLoading.value = true
  try {
    const permIds = treeRef.value?.getCheckedKeys().filter(k => typeof k === 'number') as number[] || []

    if (isEdit.value && editingId.value) {
      await updateRoleApi(editingId.value, {
        name: form.value.name,
        description: form.value.description || undefined,
        permissions: permIds,
      })
      ElMessage.success('角色信息已更新')
    } else {
      await createRoleApi({
        name: form.value.name,
        code: form.value.code,
        description: form.value.description || undefined,
        permissions: permIds,
      })
      ElMessage.success('角色创建成功')
    }
    dialogVisible.value = false
    fetchRoles()
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '操作失败')
  } finally {
    submitLoading.value = false
  }
}

async function handleDelete(row: RoleInfo) {
  try {
      await ElMessageBox.confirm(`确定要删除角色 "${row.name}" 吗？删除后相关用户将失去该角色的权限。`, '确认操作', {
      type: 'warning',
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
    })
    await deleteRoleApi(row.id)
    ElMessage.success('角色已删除')
    fetchRoles()
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
.table-card {
  border-radius: 10px;
}
.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #f0f2f5;
}
.table-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}
.perm-tree-container {
  max-height: 360px;
  overflow-y: auto;
  padding: 8px 0;
}
</style>
