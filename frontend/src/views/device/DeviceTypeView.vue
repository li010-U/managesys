<template>
  <div class="type-page">
    <div class="page-header">
      <h3 class="page-title">设备类型管理</h3>
      <p class="page-desc">定义设备类型分类、规格参数及监控阈值配置</p>
    </div>

    <el-card class="table-card">
      <template #header>
        <div class="flex-between">
          <el-input v-model="keyword" placeholder="搜索类型名称..." clearable style="width:260px" @input="debounceFetch" />
          <el-button type="primary" :icon="Plus" @click="openDialog()">新增类型</el-button>
        </div>
      </template>

      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column label="类型信息" min-width="180">
          <template #default="{ row }">
            <div class="type-info">
              <div class="type-icon" :style="{ background: categoryGradient(row.category) }">
                <el-icon><component :is="categoryIcon(row.category)" /></el-icon>
              </div>
              <div class="type-detail">
                <div class="type-name">{{ row.name }}</div>
                <div class="type-code">{{ row.code }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="分类" width="100">
          <template #default="{ row }">
            <el-tag :type="catTag(row.category)" size="small">{{ catLabel(row.category) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="manufacturer" label="厂商" width="120" />
        <el-table-column prop="model" label="型号" width="140" />
        <el-table-column label="尺寸" width="100">
          <template #default="{ row }">
            <span v-if="row.height_units">{{ row.height_units }}U</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="功耗" width="90" align="center">
          <template #default="{ row }">
            <span v-if="row.max_power">{{ row.max_power }}W</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="阈值" width="70" align="center">
          <template #default="{ row }">
            <el-badge :value="row.thresholds?.length || 0" :max="99" type="primary" v-if="row.thresholds?.length">
              <el-tag size="small" type="info">配置</el-tag>
            </el-badge>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="设备数" width="70" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="success">{{ row.device_count }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right" align="center">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="openDialog(row)">编辑</el-button>
            <el-button text type="warning" size="small" @click="openThresholdDialog(row)">阈值配置</el-button>
            <el-button text type="info" size="small" @click="cloneType(row)">复制</el-button>
            <el-button text type="danger" size="small" @click="deleteItem(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[10,20,50]" layout="total, sizes, prev, pager, next" @current-change="fetchData" @size-change="handleSizeChange" />
      </div>
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialog.visible" :title="dialog.isEdit ? '编辑类型' : '新增类型'" width="600px" :close-on-click-modal="false">
      <el-form :model="form" label-width="90px" :rules="formRules" ref="formRef">
        <el-divider content-position="left">基本信息</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="类型名称" prop="name">
              <el-input v-model="form.name" placeholder="如：IBM服务器" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="类型编码" prop="code">
              <el-input v-model="form.code" placeholder="如：ibm_server" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="设备分类" prop="category">
          <el-radio-group v-model="form.category">
            <el-radio-button value="server">服务器</el-radio-button>
            <el-radio-button value="network">网络设备</el-radio-button>
            <el-radio-button value="storage">存储设备</el-radio-button>
            <el-radio-button value="security">安全设备</el-radio-button>
            <el-radio-button value="power">电源设备</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="生产厂商">
              <el-input v-model="form.manufacturer" placeholder="如：IBM" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="产品型号">
              <el-input v-model="form.model" placeholder="如：System x3650" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">物理规格</el-divider>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="高度(U位)">
              <el-input-number v-model="form.height_units" :min="1" :max="48" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="最大功耗(W)">
              <el-input-number v-model="form.max_power" :min="0" :max="10000" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="重量(kg)">
              <el-input-number v-model="form.weight" :min="0" :precision="1" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="机身深度(mm)">
              <el-input-number v-model="form.depth" :min="0" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="额定电流(A)">
              <el-input-number v-model="form.rated_current" :min="0" :precision="1" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="规格描述">
          <el-input v-model="form.spec_description" type="textarea" :rows="3" placeholder="描述设备的详细规格..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 阈值配置抽屉 -->
    <el-drawer v-model="thresholdDialog.visible" :title="`监控阈值配置 - ${currentType?.name}`" size="650px">
      <div class="threshold-content">
        <div class="threshold-tip">
          <el-icon><InfoFilled /></el-icon>
          <span>配置该类型设备的传感器监控阈值，超出范围将触发告警。点击指标名称可自动填充默认值。</span>
        </div>

        <div v-for="(threshold, index) in thresholdForm.thresholds" :key="index" class="threshold-card">
          <div class="threshold-header">
            <el-select v-model="threshold.metric" filterable placeholder="选择指标" style="width:180px" @change="onMetricChange(threshold)">
              <el-option v-for="m in metrics" :key="m.value" :label="m.label" :value="m.value" />
            </el-select>
            <el-input v-model="threshold.label" placeholder="别名" style="width:120px" />
            <el-switch v-model="threshold.enabled" active-text="启用" inactive-text="禁用" />
            <el-button text type="danger" @click="removeThreshold(index)" :disabled="thresholdForm.thresholds.length <= 1">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
          <div class="threshold-body">
            <div class="threshold-field">
              <label>最小值</label>
              <el-input-number v-model="threshold.min_value" :precision="1" controls-position="right" />
            </div>
            <div class="threshold-range">
              <span class="range-dot min"></span>
              <el-slider v-model="thresholdRange[index]" range :min="-50" :max="100" :step="1" :format-tooltip="(v: number) => v + (threshold.unit || '')" style="flex:1" />
              <span class="range-dot max"></span>
            </div>
            <div class="threshold-field">
              <label>最大值</label>
              <el-input-number v-model="threshold.max_value" :precision="1" controls-position="right" />
            </div>
            <div class="threshold-field">
              <label>单位</label>
              <el-input v-model="threshold.unit" style="width:80px" />
            </div>
            <div class="threshold-field">
              <label>告警级别</label>
              <el-select v-model="threshold.alert_level" style="width:100px">
                <el-option value="general" label="一般" />
                <el-option value="serious" label="严重" />
                <el-option value="emergency" label="紧急" />
              </el-select>
            </div>
          </div>
        </div>

        <el-button type="primary" plain @click="addThreshold" class="add-threshold-btn">
          <el-icon><Plus /></el-icon>添加阈值
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
import { ref, onMounted } from "vue"
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus"
import { Plus, Edit, Delete, InfoFilled, Box, Monitor, Folder, Lock, Lightning } from "@element-plus/icons-vue"
import { getDeviceTypesApi, createDeviceTypeApi, updateDeviceTypeApi, deleteDeviceTypeApi, type DeviceTypeInfo } from "../../api/device"

const categories = [
  { value: "server", label: "服务器" },
  { value: "network", label: "网络设备" },
  { value: "storage", label: "存储设备" },
  { value: "security", label: "安全设备" },
  { value: "power", label: "电源设备" },
]

const metrics = [
  { value: "temperature", label: "温度", unit: "C" },
  { value: "humidity", label: "湿度", unit: "%" },
  { value: "cpu_usage", label: "CPU使用率", unit: "%" },
  { value: "memory_usage", label: "内存使用率", unit: "%" },
  { value: "disk_usage", label: "磁盘使用率", unit: "%" },
  { value: "power_usage", label: "功耗", unit: "W" },
  { value: "network_in", label: "网络流入", unit: "Mbps" },
  { value: "network_out", label: "网络流出", unit: "Mbps" },
]

const list = ref<DeviceTypeInfo[]>([])
const loading = ref(false)
const submitting = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const keyword = ref("")
const dialog = ref({ visible: false, isEdit: false, id: 0 })
const thresholdDialog = ref({ visible: false })
const thresholdLoading = ref(false)
const currentType = ref<DeviceTypeInfo | null>(null)
const thresholdForm = ref<{ thresholds: any[] }>({ thresholds: [] })
const thresholdRange = ref<[number, number][]>([])
const formRef = ref<FormInstance>()

const form = ref({
  name: "", code: "", category: "server", manufacturer: "", model: "",
  height_units: null as number, max_power: null as number, weight: null as number,
  depth: null as number, rated_current: null as number, spec_description: "",
})

const formRules: FormRules = {
  name: [{ required: true, message: "请输入类型名称", trigger: "blur" }],
  code: [{ required: true, message: "请输入类型编码", trigger: "blur" }],
  category: [{ required: true, message: "请选择分类", trigger: "change" }],
}

let debounceTimer: ReturnType<typeof setTimeout>
function debounceFetch() { clearTimeout(debounceTimer); debounceTimer = setTimeout(() => { page.value = 1; fetchData() }, 300) }

onMounted(() => fetchData())

async function fetchData() {
  loading.value = true
  try {
    const r = await getDeviceTypesApi({ page: page.value, page_size: pageSize.value, keyword: keyword.value || undefined })
    list.value = r.data.items; total.value = r.data.total
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

function handleSizeChange() { page.value = 1; fetchData() }

function catLabel(c: string) { return categories.find(x => x.value === c)?.label || c }
function catTag(c: string) { const map: Record<string, string> = { server: "", network: "info", storage: "warning", security: "danger", power: "success" }; return map[c] || "" }
function categoryIcon(c: string) { const map: Record<string, any> = { server: Box, network: Monitor, storage: Folder, security: Lock, power: Lightning }; return map[c] || Box }
function categoryGradient(c: string) { const map: Record<string, string> = { server: "linear-gradient(135deg, #4361ee 0%, #7289ff 100%)", network: "linear-gradient(135deg, #10b981 0%, #34d399 100%)", storage: "linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%)", security: "linear-gradient(135deg, #ef4444 0%, #f87171 100%)", power: "linear-gradient(135deg, #8b5cf6 0%, #a78bfa 100%)" }; return map[c] || "#4361ee" }

function openDialog(item?: DeviceTypeInfo) {
  dialog.value = { visible: true, isEdit: !!item, id: item?.id || 0 }
  form.value = item ? {
    name: item.name, code: item.code, category: item.category, manufacturer: item.manufacturer || "",
    model: item.model || "", height_units: item.height_units, max_power: item.max_power,
    weight: item.weight, depth: item.depth, rated_current: item.rated_current,
    spec_description: item.spec_description || "",
  } : { name: "", code: "", category: "server", manufacturer: "", model: "", height_units: null, max_power: null, weight: null, depth: null, rated_current: null, spec_description: "" }
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (dialog.value.isEdit) { await updateDeviceTypeApi(dialog.value.id, form.value); ElMessage.success("更新成功") }
    else { await createDeviceTypeApi(form.value); ElMessage.success("创建成功") }
    dialog.value.visible = false; fetchData()
  } catch (err: any) { ElMessage.error(err.response?.data?.detail || "操作失败") }
  finally { submitting.value = false }
}

async function deleteItem(item: DeviceTypeInfo) {
  try {
    await ElMessageBox.confirm(`确定删除类型 "${item.name}"？`, "确认删除", { type: "warning" })
    await deleteDeviceTypeApi(item.id); ElMessage.success("删除成功"); fetchData()
  } catch {}
}

function cloneType(item: DeviceTypeInfo) {
  form.value = {
    name: item.name + " (副本)", code: item.code + "_copy", category: item.category,
    manufacturer: item.manufacturer || "", model: item.model || "",
    height_units: item.height_units, max_power: item.max_power, weight: item.weight,
    depth: item.depth, rated_current: item.rated_current, spec_description: item.spec_description || "",
  }
  dialog.value = { visible: true, isEdit: false, id: 0 }
}

function openThresholdDialog(item: DeviceTypeInfo) {
  currentType.value = item; thresholdDialog.value.visible = true
  if (item.thresholds && item.thresholds.length > 0) {
    thresholdForm.value.thresholds = item.thresholds.map((t: any) => ({
      metric: t.metric || "", label: t.label || "", min_value: t.min_value ?? null,
      max_value: t.max_value ?? null, unit: t.unit || "%", alert_level: t.alert_level || "general", enabled: t.enabled !== false,
    }))
    thresholdRange.value = item.thresholds.map((t: any) => [t.min_value ?? 0, t.max_value ?? 100] as [number, number])
  } else {
    thresholdForm.value.thresholds = [{ metric: "temperature", label: "温度", min_value: 10, max_value: 40, unit: "C", alert_level: "general", enabled: true }]
    thresholdRange.value = [[10, 40]]
  }
}

function onMetricChange(threshold: any) {
  const m = metrics.find(x => x.value === threshold.metric)
  if (m) { threshold.unit = m.unit; if (!threshold.label) threshold.label = m.label }
  const rangeIdx = thresholdForm.value.thresholds.indexOf(threshold)
  if (rangeIdx >= 0 && threshold.min_value !== undefined && threshold.max_value !== undefined) {
    thresholdRange.value[rangeIdx] = [threshold.min_value, threshold.max_value]
  }
}

function addThreshold() {
  thresholdForm.value.thresholds.push({ metric: "cpu_usage", label: "CPU使用率", min_value: 0, max_value: 80, unit: "%", alert_level: "general", enabled: true })
  thresholdRange.value.push([0, 80])
}

function removeThreshold(index: number) { thresholdForm.value.thresholds.splice(index, 1); thresholdRange.value.splice(index, 1) }

async function saveThresholds() {
  if (!currentType.value) return
  thresholdLoading.value = true
  try {
    // Sync slider values to threshold values
    thresholdForm.value.thresholds.forEach((t, i) => {
      if (thresholdRange.value[i]) { t.min_value = thresholdRange.value[i][0]; t.max_value = thresholdRange.value[i][1] }
    })
    await updateDeviceTypeApi(currentType.value.id, { thresholds: thresholdForm.value.thresholds } as any)
    ElMessage.success("阈值配置已保存"); thresholdDialog.value.visible = false; fetchData()
  } catch (err: any) { ElMessage.error(err.response?.data?.detail || "保存失败") }
  finally { thresholdLoading.value = false }
}
</script>

<style scoped>
.type-page { padding: 0; }
.page-header { margin-bottom: 20px; }
.page-title { font-size: 20px; font-weight: 600; margin: 0; }
.page-desc { font-size: 14px; color: var(--app-text-muted); margin: 6px 0 0; }

.table-card { border-radius: 12px; }
.flex-between { display: flex; justify-content: space-between; align-items: center; }
.pagination-wrapper { display: flex; justify-content: flex-end; margin-top: 16px; }

.type-info { display: flex; align-items: center; gap: 12px; }
.type-icon { width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: #fff; }
.type-detail { display: flex; flex-direction: column; }
.type-name { font-weight: 600; }
.type-code { font-size: 12px; color: var(--app-text-muted); font-family: monospace; }

.text-muted { color: var(--app-text-muted); }

/* 阈值配置 */
.threshold-content { padding: 0 4px; }
.threshold-tip { display: flex; align-items: center; gap: 10px; padding: 14px 16px; background: linear-gradient(135deg, rgba(67,97,238,0.1) 0%, rgba(114,137,255,0.1) 100%); border-radius: 10px; margin-bottom: 20px; font-size: 13px; color: var(--app-text-secondary); }
.threshold-card { border: 1px solid var(--app-border); border-radius: 12px; padding: 16px; margin-bottom: 16px; transition: all 0.25s; }
.threshold-card:hover { border-color: var(--el-color-primary-light-5); box-shadow: var(--app-shadow); }
.threshold-header { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.threshold-body { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.threshold-field { display: flex; flex-direction: column; gap: 4px; }
.threshold-field label { font-size: 12px; color: var(--app-text-muted); }
.threshold-range { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 200px; }
.range-dot { width: 8px; height: 8px; border-radius: 50%; }
.range-dot.min { background: var(--el-color-success); }
.range-dot.max { background: var(--el-color-danger); }

.add-threshold-btn { width: 100%; border-style: dashed; }

:deep(.el-divider--horizontal) { margin: 16px 0; }
:deep(.el-slider) { --el-slider-main-bg-color: var(--el-color-primary); }
</style>