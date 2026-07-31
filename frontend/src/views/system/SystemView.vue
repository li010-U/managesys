<template>
  <div class="biz-page">
    <div class="page-header">
      <div>
        <h3 class="page-title">系统台账</h3>
        <p class="page-desc">业务系统信息管理、系统与设备部署关联</p>
      </div>
    </div>
    <el-card shadow="never" class="toolbar-card">
      <div class="toolbar-bar">
        <div class="toolbar-left">
          <el-input v-model="search" placeholder="搜索系统名称/编码..." :prefix-icon="Search" clearable size="small" style="width:220px" @input="loadData" />
          <el-select v-model="filterCategory" placeholder="系统分类" clearable size="small" style="width:130px" @change="loadData">
            <el-option label="OA系统" value="OA" /><el-option label="ERP系统" value="ERP" /><el-option label="CRM系统" value="CRM" /><el-option label="数据库" value="DB" /><el-option label="中间件" value="Middleware" /><el-option label="其他" value="other" />
          </el-select>
          <el-select v-model="filterStatus" placeholder="状态" clearable size="small" style="width:120px" @change="loadData">
            <el-option label="正常" value="active" /><el-option label="维护中" value="maintenance" /><el-option label="已下线" value="offline" />
          </el-select>
        </div>
        <div class="toolbar-right">
          <el-button type="primary" :icon="Plus" size="small" @click="openDialog()">新增系统</el-button>
        </div>
      </div>
    </el-card>
    <el-card shadow="never" class="table-card">
      <el-table :data="list" stripe border size="small" v-loading="loading">
        <el-table-column prop="name" label="系统名称" min-width="150" />
        <el-table-column prop="code" label="系统编码" width="140" />
        <el-table-column prop="category" label="分类" width="100">
          <template #default="{ row }"><el-tag size="small" type="info">{{ categoryLabel(row.category) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="access_url" label="访问URL" min-width="160" show-overflow-tooltip>
          <template #default="{ row }"><a v-if="row.access_url" :href="row.access_url" target="_blank" style="color:#1a73e8">{{ row.access_url }}</a><span v-else style="color:#999">-</span></template>
        </el-table-column>
        <el-table-column prop="admin_name" label="管理员" width="100" />
        <el-table-column prop="admin_phone" label="联系电话" width="130" />
        <el-table-column prop="status" label="状态" width="80" align="center">
          <template #default="{ row }"><el-tag size="small" :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="关联设备" width="90" align="center"><template #default="{ row }"><el-badge :value="row.device_count" :max="99" /></template></el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button :icon="Link" size="small" text @click="openDeployDialog(row)">关联</el-button>
            <el-button :icon="Edit" size="small" text @click="openDialog(row)">编辑</el-button>
            <el-button :icon="Delete" size="small" text type="danger" @click="deleteRow(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[10,20,50]" layout="total, sizes, prev, pager, next" small style="margin-top:12px;justify-content:center" />
    </el-card>
    <el-dialog v-model="dialog.visible" :title="dialog.isEdit?'编辑系统':'新增系统'" width="560px" :close-on-click-modal="false" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" size="small">
        <el-form-item label="系统名称" prop="name"><el-input v-model="form.name" placeholder="如：财务管理系统" /></el-form-item>
        <el-form-item label="系统编码" prop="code"><el-input v-model="form.code" placeholder="如：FIN-SYS-001" /></el-form-item>
        <el-row :gutter="12">
          <el-col :span="12"><el-form-item label="系统分类" prop="category"><el-select v-model="form.category" style="width:100%"><el-option label="OA系统" value="OA" /><el-option label="ERP系统" value="ERP" /><el-option label="CRM系统" value="CRM" /><el-option label="数据库" value="DB" /><el-option label="中间件" value="Middleware" /><el-option label="其他" value="other" /></el-select></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="状态" prop="status"><el-select v-model="form.status" style="width:100%"><el-option label="正常" value="active" /><el-option label="维护中" value="maintenance" /><el-option label="已下线" value="offline" /></el-select></el-form-item></el-col>
        </el-row>
        <el-form-item label="访问URL"><el-input v-model="form.access_url" placeholder="https://oa.company.com" /></el-form-item>
        <el-row :gutter="12">
          <el-col :span="12"><el-form-item label="管理员"><el-input v-model="form.admin_name" placeholder="管理员姓名" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="联系电话"><el-input v-model="form.admin_phone" placeholder="手机号" /></el-form-item></el-col>
        </el-row>
        <el-form-item label="管理员邮箱"><el-input v-model="form.admin_email" placeholder="admin@company.com" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="2" placeholder="可选备注" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialog.visible=false">取消</el-button><el-button type="primary" :loading="submitting" @click="submit">{{ dialog.isEdit?'保存':'创建' }}</el-button></template>
    </el-dialog>
    <el-dialog v-model="deployDialog.visible" :title="deployDialog.system?.name + ' - 设备关联'" width="650px" :close-on-click-modal="false">
      <el-alert :title="'关联设备数量：' + (deployments.length)" type="info" :closable="false" show-icon style="margin-bottom:16px" />
      <div style="margin-bottom:12px"><el-button type="primary" size="small" :icon="Plus" @click="openAddDeviceDialog">添加关联</el-button></div>
      <el-table :data="deployments" stripe border size="small" max-height="300">
        <el-table-column prop="device_name" label="设备名称" min-width="150" />
        <el-table-column prop="service_port" label="服务端口" width="100" />
        <el-table-column prop="process_name" label="进程名" width="120" />
        <el-table-column prop="system_version" label="系统版本" width="100" />
        <el-table-column prop="middleware_version" label="中间件版本" width="110" />
        <el-table-column label="操作" width="80"><template #default="{ row }"><el-button icon="Delete" size="small" text type="danger" @click="removeDeploy(row)" /></template></el-table-column>
      </el-table>
    </el-dialog>
    <el-dialog v-model="addDeviceDialog.visible" title="添加设备关联" width="500px" :close-on-click-modal="false">
      <el-form :model="addDeviceForm" label-width="100px" size="small">
        <el-form-item label="选择设备" required>
          <el-select v-model="addDeviceForm.device_id" filterable placeholder="搜索设备..." style="width:100%">
            <el-option v-for="d in availableDevices" :key="d.id" :label="d.name + ' (' + d.asset_number + ')'" :value="d.id">
              <span>{{ d.name }}</span><span style="color:#999;font-size:11px;margin-left:8px">{{ d.device_type_name }}</span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12"><el-form-item label="服务端口"><el-input v-model="addDeviceForm.service_port" placeholder="如：8080" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="进程名"><el-input v-model="addDeviceForm.process_name" placeholder="如：java" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12"><el-form-item label="系统版本"><el-input v-model="addDeviceForm.system_version" placeholder="如：v2.1.0" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="中间件版本"><el-input v-model="addDeviceForm.middleware_version" placeholder="如：Tomcat9" /></el-form-item></el-col>
        </el-row>
      </el-form>
      <template #footer><el-button @click="addDeviceDialog.visible=false">取消</el-button><el-button type="primary" @click="addDeploy">确认添加</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, Search, Link } from '@element-plus/icons-vue'
import { getBizSystemsApi, createBizSystemApi, updateBizSystemApi, deleteBizSystemApi, getDeploymentsApi, createDeploymentApi, deleteDeploymentApi } from '../../api/alert'
import { getDevicesApi } from '../../api/device'

const list = ref<any[]>([]); const loading = ref(false); const search = ref(''); const filterCategory = ref(''); const filterStatus = ref(''); const page = ref(1); const pageSize = ref(10); const total = ref(0); const submitting = ref(false); const formRef = ref<any>(null)
const dialog = reactive({ visible: false, isEdit: false, id: 0 })
const form = ref<any>({ name: '', code: '', category: 'OA', access_url: '', admin_name: '', admin_phone: '', admin_email: '', remark: '', status: 'active' })
const rules = { name: [{ required: true, message: '请输入系统名称', trigger: 'blur' }], code: [{ required: true, message: '请输入系统编码', trigger: 'blur' }] }
const deployDialog = reactive({ visible: false, system: null as any }); const deployments = ref<any[]>([]); const addDeviceDialog = reactive({ visible: false }); const addDeviceForm = ref<any>({ device_id: null, service_port: '', process_name: '', system_version: '', middleware_version: '' }); const availableDevices = ref<any[]>([])

async function loadData() { loading.value = true; try { const r = await getBizSystemsApi({ page: page.value, page_size: pageSize.value, keyword: search.value || undefined, category: filterCategory.value || undefined, status: filterStatus.value || undefined }); list.value = r.data.items; total.value = r.data.total } catch { list.value = [] } finally { loading.value = false } }
function openDialog(sys?: any) { dialog.visible = true; dialog.isEdit = !!sys; dialog.id = sys?.id || 0; if (sys) { form.value = { name: sys.name, code: sys.code, category: sys.category, access_url: sys.access_url || '', admin_name: sys.admin_name || '', admin_phone: sys.admin_phone || '', admin_email: sys.admin_email || '', remark: sys.remark || '', status: sys.status } } else { form.value = { name: '', code: '', category: 'OA', access_url: '', admin_name: '', admin_phone: '', admin_email: '', remark: '', status: 'active' } } setTimeout(() => formRef.value?.clearValidate(), 0) }
async function submit() { const valid = await formRef.value?.validate().catch(() => false); if (!valid) return; submitting.value = true; try { if (dialog.isEdit) { await updateBizSystemApi(dialog.id, form.value); ElMessage.success('已更新') } else { await createBizSystemApi(form.value); ElMessage.success('已创建') } dialog.visible = false; await loadData() } catch { /* interceptor */ } finally { submitting.value = false } }
async function deleteRow(sys: any) { try { await ElMessageBox.confirm('确定删除系统「' + sys.name + '」？', '确认删除', { type: 'warning' }); await deleteBizSystemApi(sys.id); ElMessage.success('已删除'); await loadData() } catch { /* cancelled */ } }
async function openDeployDialog(sys: any) { deployDialog.visible = true; deployDialog.system = sys; try { const r = await getDeploymentsApi(sys.id); deployments.value = r.data } catch { deployments.value = [] } }
async function openAddDeviceDialog() { addDeviceDialog.visible = true; addDeviceForm.value = { device_id: null, service_port: '', process_name: '', system_version: '', middleware_version: '' }; try { const r = await getDevicesApi({ page: 1, page_size: 999 }); availableDevices.value = r.data.items } catch { availableDevices.value = [] } }
async function addDeploy() { if (!addDeviceForm.value.device_id) { ElMessage.warning('请选择设备'); return } try { await createDeploymentApi(deployDialog.system.id, addDeviceForm.value); ElMessage.success('关联成功'); addDeviceDialog.visible = false; const r = await getDeploymentsApi(deployDialog.system.id); deployments.value = r.data } catch { /* interceptor */ } }
async function removeDeploy(row: any) { try { await deleteDeploymentApi(deployDialog.system.id, row.id); ElMessage.success('已移除'); const r = await getDeploymentsApi(deployDialog.system.id); deployments.value = r.data } catch { /* interceptor */ } }
function categoryLabel(c: string) { const map: Record<string,string> = { OA:'OA系统', ERP:'ERP系统', CRM:'CRM系统', DB:'数据库', Middleware:'中间件', other:'其他' }; return map[c] || c }
function statusLabel(s: string) { const map: Record<string,string> = { active:'正常', maintenance:'维护中', offline:'已下线' }; return map[s] || s }
function statusType(s: string) { const map: Record<string,string> = { active:'success', maintenance:'warning', offline:'info' }; return map[s] || 'info' }
watch([page, pageSize], loadData); onMounted(loadData)
</script>

<style scoped>
.page-header { margin-bottom: 16px; }
.page-title { font-size: 20px; font-weight: 700; margin: 0; background: linear-gradient(135deg, #6a1b9a, #4a148c); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.page-desc { font-size: 13px; color: var(--app-text-muted); margin: 4px 0 0; }
.toolbar-card { margin-bottom: 12px; border-radius: 12px; }
.toolbar-bar { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.toolbar-left, .toolbar-right { display: flex; align-items: center; gap: 8px; }
.table-card { border-radius: 12px; }
</style>
