<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h3 class="page-title">设备类型管理</h3>
        <p class="page-desc">定义和管理设备类型分类及传感器阈值配置</p>
      </div>
    </div>

    <el-card class="table-card">
      <template #header>
        <div class="flex-between">
          <el-input v-model="keyword" placeholder="搜索类型..." clearable style="width:240px" @input="fetchData" />
          <el-button type="primary" :icon="Plus" @click="openDialog()">新增类型</el-button>
        </div>
      </template>
      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column prop="name" label="类型名称" min-width="140" />
        <el-table-column prop="code" label="编码" width="100" />
        <el-table-column label="分类" width="100">
          <template #default="{ row }">
            <el-tag :type="catTag(row.category)" size="small">{{ catLabel(row.category) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="manufacturer" label="厂商" width="120" />
        <el-table-column prop="model" label="型号" width="120" />
        <el-table-column label="阈值" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.thresholds?.length" type="success" size="small">{{ row.thresholds.length }}</el-tag>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="设备数" width="70" align="center">
          <template #default="{ row }">
            <el-tag size="small">{{ row.device_count }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right" align="center">
          <template #default="{ row }">
            <el-button text type="primary" size="small" :icon="Edit" @click="openDialog(row)">编辑</el-button>
            <el-button text type="warning" size="small" :icon="Setting" @click="openThresholdDialog(row)">阈值</el-button>
            <el-button text type="danger" size="small" :icon="Delete" @click="deleteItem(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-if="total > pageSize" v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, prev, pager, next" class="pagination" @current-change="fetchData" />
    </el-card>

    <el-dialog v-model="dialog.visible" :title="dialog.isEdit ? '编辑类型' : '新增类型'" width="500px">
      <el-form :model="form" label-width="80px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="名称" prop="name" :rules="[{required:true}]">
              <el-input v-model="form.name" placeholder="如：IBM服务器" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="编码" prop="code" :rules="[{required:true}]">
              <el-input v-model="form.code" placeholder="如：ibm_server" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="分类" prop="category" :rules="[{required:true}]">
          <el-select v-model="form.category" style="width:100%">
            <el-option v-for="c in categories" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="厂商">
              <el-input v-model="form.manufacturer" placeholder="如：IBM" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="型号">
              <el-input v-model="form.model" placeholder="如：System x3650" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="规格描述">
          <el-input v-model="form.spec_description" type="textarea" :rows="3" placeholder="描述设备的详细规格..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="submit">确定</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="thresholdDialog.visible" :title="`传感器阈值配置 - ${currentType?.name}`" size="600px">
      <div class="threshold-config">
        <div class="threshold-tip">
          <el-icon><InfoFilled /></el-icon>
          <span>配置此类型设备的传感器监控阈值，超出范围将触发告警</span>
        </div>

        <div v-for="(threshold, index) in thresholdForm.thresholds" :key="index" class="threshold-item">
          <div class="threshold-header">
            <el-select v-model="threshold.metric" placeholder="选择指标" style="width: 140px" @change="onMetricChange(threshold)">
              <el-option v-for="m in metrics" :key="m.value" :label="m.label" :value="m.value" />
            </el-select>
            <el-input v-model="threshold.label" placeholder="显示名称" style="width: 120px" />
            <el-switch v-model="threshold.enabled" active-text="启用" inactive-text="停用" />
            <el-button text type="danger" @click="removeThreshold(index)" :disabled="thresholdForm.thresholds.length <= 1">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
          <div class="threshold-body">
            <div class="threshold-field">
              <label>最小值</label>
              <el-input-number v-model="threshold.min_value" :precision="1" controls-position="right" placeholder="警告下限" />
            </div>
            <div class="threshold-field">
              <label>最大值</label>
              <el-input-number v-model="threshold.max_value" :precision="1" controls-position="right" placeholder="警告上限" />
            </div>
            <div class="threshold-field">
              <label>单位</label>
              <el-select v-model="threshold.unit" style="width: 80px">
                <el-option label="%" value="%" />
                <el-option label="℃" value="℃" />
                <el-option label="V" value="V" />
                <el-option label="W" value="W" />
              </el-select>
            </div>
            <div class="threshold-field">
              <label>告警级别</label>
              <el-select v-model="threshold.alert_level" style="width: 100px">
                <el-option label="一般" value="general" />
                <el-option label="严重" value="serious" />
                <el-option label="紧急" value="emergency" />
              </el-select>
            </div>
          </div>
        </div>

        <el-button type="primary" plain @click="addThreshold" style="margin-top: 12px">
          <el-icon><Plus /></el-icon>添加指标
        </el-button>
      </div>
      <template #footer>
        <el-button @click="thresholdDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="thresholdLoading" @click="saveThresholds">保存配置</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, Setting, InfoFilled } from '@element-plus/icons-vue'
import { getDeviceTypesApi, createDeviceTypeApi, updateDeviceTypeApi, deleteDeviceTypeApi } from '../../api/device'
import type { DeviceTypeInfo } from '../../api/device'

interface ThresholdConfig {
  metric: string
  label: string
  min_value: number | null
  max_value: number | null
  unit: string
  alert_level: string
  enabled: boolean
}

const loading = ref(false)
const list = ref<DeviceTypeInfo[]>([])
const keyword = ref('')
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)

const categories = [
  { value: 'server', label: '服务器' },
  { value: 'network', label: '网络设备' },
  { value: 'storage', label: '存储设备' },
  { value: 'security', label: '安全设备' },
  { value: 'power', label: '电源设备' },
]

const metrics = [
  { value: 'temperature', label: '温度', unit: '℃' },
  { value: 'humidity', label: '湿度', unit: '%' },
  { value: 'cpu_usage', label: 'CPU使用率', unit: '%' },
  { value: 'memory_usage', label: '内存使用率', unit: '%' },
  { value: 'disk_usage', label: '磁盘使用率', unit: '%' },
  { value: 'power_voltage', label: '电压', unit: 'V' },
]

const dialog = ref({ visible: false, isEdit: false, id: 0 })
const form = ref({ name: '', code: '', category: 'server', manufacturer: '', model: '', spec_description: '' })

const thresholdDialog = ref({ visible: false })
const thresholdLoading = ref(false)
const currentType = ref<DeviceTypeInfo | null>(null)
const thresholdForm = ref<{ thresholds: ThresholdConfig[] }>({ thresholds: [] })

function catLabel(c: string) {
  return categories.find(x => x.value === c)?.label || c
}

function catTag(c: string) {
  const map: Record<string, string> = { server: '', network: 'info', storage: 'warning', security: 'danger', power: 'success' }
  return map[c] || ''
}

onMounted(() => fetchData())

async function fetchData() {
  loading.value = true
  try {
    const r = await getDeviceTypesApi({ page: page.value, page_size: pageSize.value, keyword: keyword.value || undefined })
    list.value = r.data.items
    total.value = r.data.total
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

function openDialog(item?: DeviceTypeInfo) {
  dialog.value = { visible: true, isEdit: !!item, id: item?.id || 0 }
  form.value = item
    ? { name: item.name, code: item.code, category: item.category, manufacturer: item.manufacturer || '', model: item.model || '', spec_description: item.spec_description || '' }
    : { name: '', code: '', category: 'server', manufacturer: '', model: '', spec_description: '' }
}

async function submit() {
  loading.value = true
  try {
    if (dialog.value.isEdit) {
      await updateDeviceTypeApi(dialog.value.id, form.value)
      ElMessage.success('已更新')
    } else {
      await createDeviceTypeApi(form.value)
      ElMessage.success('已创建')
    }
    dialog.value.visible = false
    fetchData()
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '操作失败')
  } finally {
    loading.value = false
  }
}

async function deleteItem(item: DeviceTypeInfo) {
  try {
    await ElMessageBox.confirm(`删除 "${item.name}"？`, '确认')
    await deleteDeviceTypeApi(item.id)
    ElMessage.success('已删除')
    fetchData()
  } catch {}
}

function openThresholdDialog(item: DeviceTypeInfo) {
  currentType.value = item
  thresholdDialog.value.visible = true
  if (item.thresholds && item.thresholds.length > 0) {
    thresholdForm.value.thresholds = item.thresholds.map((t: any) => ({
      metric: t.metric || '',
      label: t.label || '',
      min_value: t.min_value ?? null,
      max_value: t.max_value ?? null,
      unit: t.unit || '%',
      alert_level: t.alert_level || 'general',
      enabled: t.enabled !== false,
    }))
  } else {
    thresholdForm.value.thresholds = [
      { metric: 'temperature', label: '温度', min_value: 10, max_value: 40, unit: '℃', alert_level: 'general', enabled: true },
    ]
  }
}

function onMetricChange(threshold: ThresholdConfig) {
  const m = metrics.find(x => x.value === threshold.metric)
  if (m) {
    threshold.unit = m.unit
    if (!threshold.label) threshold.label = m.label
  }
}

function addThreshold() {
  thresholdForm.value.thresholds.push({
    metric: 'cpu_usage',
    label: 'CPU使用率',
    min_value: null,
    max_value: 80,
    unit: '%',
    alert_level: 'general',
    enabled: true,
  })
}

function removeThreshold(index: number) {
  thresholdForm.value.thresholds.splice(index, 1)
}

async function saveThresholds() {
  if (!currentType.value) return
  thresholdLoading.value = true
  try {
    await updateDeviceTypeApi(currentType.value.id, { thresholds: thresholdForm.value.thresholds } as any, true)
    ElMessage.success('阈值配置已保存')
    thresholdDialog.value.visible = false
    fetchData()
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '保存失败')
  } finally {
    thresholdLoading.value = false
  }
}
</script>

<style scoped>
.page-header { margin-bottom: 16px; }
.page-title { font-size: 18px; font-weight: 600; margin: 0; }
.page-desc { font-size: 13px; color: #909399; margin: 4px 0 0; }
.table-card { border-radius: 10px; }
.pagination { display: flex; justify-content: flex-end; margin-top: 12px; }
.flex-between { display: flex; justify-content: space-between; align-items: center; }
.text-muted { color: #c0c4cc; }

.threshold-config { padding: 0 4px; }
.threshold-tip { display: flex; align-items: center; gap: 8px; padding: 12px; background: #f4f4f5; border-radius: 6px; margin-bottom: 16px; font-size: 13px; color: #606266; }
.threshold-item { border: 1px solid #ebeef5; border-radius: 8px; padding: 12px; margin-bottom: 12px; }
.threshold-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.threshold-body { display: flex; gap: 12px; flex-wrap: wrap; }
.threshold-field { display: flex; flex-direction: column; gap: 4px; }
.threshold-field label { font-size: 12px; color: #909399; }
</style>
