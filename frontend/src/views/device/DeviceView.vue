<template>
  <div class="device-page">
    <div class="page-header">
      <h3 class="page-title">设备台账</h3>
      <p class="page-desc">管理所有设备的资产信息与生命周期</p>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-item">
            <div class="stat-icon-box gradient-primary">
              <el-icon :size="22"><Box /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-num">{{ stats.total }}</span>
              <span class="stat-label">设备总数</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-item">
            <div class="stat-icon-box gradient-success">
              <el-icon :size="22"><CircleCheck /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-num">{{ stats.online }}</span>
              <span class="stat-label">在线设备</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-item">
            <div class="stat-icon-box gradient-warning">
              <el-icon :size="22"><Warning /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-num">{{ stats.offline }}</span>
              <span class="stat-label">离线设备</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-item">
            <div class="stat-icon-box gradient-danger">
              <el-icon :size="22"><Bell /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-num">{{ stats.alert }}</span>
              <span class="stat-label">告警设备</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="table-card">
      <template #header>
        <div class="table-toolbar">
          <div class="toolbar-left">
            <el-input v-model="keyword" placeholder="名称/资产号/序列号..." clearable style="width:260px" @input="debounceFetch" />
            <el-select v-model="filterStatus" clearable placeholder="状态" style="width:120px" @change="fetchData">
              <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
            <el-select v-model="filterType" clearable placeholder="类型" style="width:140px" filterable @change="fetchData">
              <el-option v-for="t in deviceTypes" :key="t.id" :label="t.name" :value="t.id" />
            </el-select>
            <el-select v-model="filterRack" clearable placeholder="机柜" style="width:140px" filterable @change="fetchData">
              <el-option v-for="r in racks" :key="r.id" :label="r.code + ' - ' + r.name" :value="r.id" />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-button :icon="Refresh" @click="fetchData">刷新</el-button>
            <el-button :icon="Download" @click="exportDevices">导出</el-button>
            <el-button type="primary" :icon="Plus" @click="openDialog()">新增设备</el-button>
          </div>
        </div>
      </template>

      <div v-if="selectedIds.length > 0" class="batch-bar">
        <span class="batch-tip">已选择 {{ selectedIds.length }} 项</span>
        <el-button size="small" type="warning" @click="batchExport">批量导出</el-button>
        <el-button size="small" type="danger" @click="batchDelete">批量删除</el-button>
        <el-button size="small" text @click="selectedIds = []">取消</el-button>
      </div>

      <el-table :data="list" v-loading="loading" stripe @selection-change="handleSelection" :row-class-name="rowClassName">
        <el-table-column type="selection" width="50" />
        <el-table-column prop="name" label="设备名称" min-width="160" sortable>
          <template #default="{ row }">
            <div class="device-name">
              <el-icon><Box /></el-icon>
              <span>{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="asset_number" label="资产编号" width="130" sortable>
          <template #default="{ row }"><el-tag size="small" type="info">{{ row.asset_number }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="device_type_name" label="类型" width="110" />
        <el-table-column prop="brand" label="品牌" width="90" />
        <el-table-column prop="model" label="型号" width="100" />
        <el-table-column prop="rack_name" label="机柜" width="100">
          <template #default="{ row }">
            <span v-if="row.rack_name" class="rack-link">{{ row.rack_name }}</span>
            <span v-else class="text-muted">未上机</span>
          </template>
        </el-table-column>
        <el-table-column label="U位" width="70" align="center">
          <template #default="{ row }">{{ row.start_u ? row.start_u + 'U-' + row.end_u + 'U' : '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center" sortable prop="status">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="showDetail(row)">详情</el-button>
            <el-button text type="primary" size="small" @click="openDialog(row)">编辑</el-button>
            <el-dropdown trigger="click" @command="(cmd) => handleCommand(cmd, row)">
              <el-button text type="primary" size="small"><el-icon><MoreFilled /></el-icon></el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="mount" v-if="!row.rack_id"><el-icon><Top /></el-icon>上机</el-dropdown-item>
                  <el-dropdown-item command="unmount" v-if="row.rack_id"><el-icon><Bottom /></el-icon>下架</el-dropdown-item>
                  <el-dropdown-item command="lifecycle"><el-icon><Timer /></el-icon>生命周期</el-dropdown-item>
                  <el-dropdown-item command="delete" divided><el-icon><Delete /></el-icon>删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[10,20,50,100]" layout="total, sizes, prev, pager, next" @current-change="fetchData" @size-change="handleSizeChange" />
      </div>
    </el-card>

    <!-- 新增/编辑 -->
    <el-dialog v-model="dialog.visible" :title="dialog.isEdit ? '编辑设备' : '新增设备'" width="780px" :close-on-click-modal="false">
      <el-form :model="form" label-width="100px" :rules="formRules" ref="formRef">
        <el-divider content-position="left">基本信息</el-divider>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="设备名称" prop="name"><el-input v-model="form.name" placeholder="请输入设备名称" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="资产编号" prop="asset_number"><el-input v-model="form.asset_number" placeholder="请输入资产编号" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="设备类型"><el-select v-model="form.device_type_id" filterable style="width:100%"><el-option v-for="t in deviceTypes" :key="t.id" :label="t.name" :value="t.id" /></el-select></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="品牌"><el-input v-model="form.brand" placeholder="如：华为" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="型号"><el-input v-model="form.model" placeholder="如：RH2288H" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="序列号"><el-input v-model="form.serial_number" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="供应商"><el-input v-model="form.vendor" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="采购单号"><el-input v-model="form.purchase_order" /></el-form-item></el-col>
        </el-row>
        <el-divider content-position="left">网络信息</el-divider>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="管理IP"><el-input v-model="form.management_ip" placeholder="如：192.168.1.100" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="MAC地址"><el-input v-model="form.mac_address" placeholder="如：00:1A:2B:3C:4D:5E" /></el-form-item></el-col>
        </el-row>
        <el-divider content-position="left">硬件配置</el-divider>
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="CPU"><el-input v-model="form.cpu_info" placeholder="如：2xIntel Xeon" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="内存"><el-input v-model="form.memory_info" placeholder="如：64GB DDR4" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="硬盘"><el-input v-model="form.disk_info" placeholder="如：2TB RAID" /></el-form-item></el-col>
        </el-row>
        <el-divider content-position="left">位置信息</el-divider>
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="机柜"><el-select v-model="form.rack_id" clearable filterable style="width:100%" @change="onRackChange"><el-option v-for="r in racks" :key="r.id" :label="r.code + ' - ' + r.name" :value="r.id" /></el-select></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="起始U位"><el-input-number v-model="form.start_u" :min="1" :max="42" style="width:100%" :disabled="!form.rack_id" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="结束U位"><el-input-number v-model="form.end_u" :min="1" :max="42" style="width:100%" :disabled="!form.rack_id" /></el-form-item></el-col>
        </el-row>
        <el-divider content-position="left">维保信息</el-divider>
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="采购日期"><el-date-picker v-model="form.purchase_date" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="保修开始"><el-date-picker v-model="form.warranty_start" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="保修结束"><el-date-picker v-model="form.warranty_end" type="date" value-format="YYYY-MM-DD" style="width:100%" /></el-form-item></el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>

    <!-- 详情 -->
    <el-dialog v-model="detailDialog.visible" :title="currentDevice?.name" width="800px">
      <el-tabs v-model="detailTab">
        <el-tab-pane label="基本信息" name="info">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="资产编号">{{ currentDevice?.asset_number }}</el-descriptions-item>
            <el-descriptions-item label="设备类型">{{ currentDevice?.device_type_name }}</el-descriptions-item>
            <el-descriptions-item label="品牌">{{ currentDevice?.brand || '-' }}</el-descriptions-item>
            <el-descriptions-item label="型号">{{ currentDevice?.model || '-' }}</el-descriptions-item>
            <el-descriptions-item label="序列号">{{ currentDevice?.serial_number || '-' }}</el-descriptions-item>
            <el-descriptions-item label="供应商">{{ currentDevice?.vendor || '-' }}</el-descriptions-item>
            <el-descriptions-item label="管理IP">{{ currentDevice?.management_ip || '-' }}</el-descriptions-item>
            <el-descriptions-item label="MAC地址">{{ currentDevice?.mac_address || '-' }}</el-descriptions-item>
            <el-descriptions-item label="CPU">{{ currentDevice?.cpu_info || '-' }}</el-descriptions-item>
            <el-descriptions-item label="内存">{{ currentDevice?.memory_info || '-' }}</el-descriptions-item>
            <el-descriptions-item label="硬盘">{{ currentDevice?.disk_info || '-' }}</el-descriptions-item>
            <el-descriptions-item label="采购单号">{{ currentDevice?.purchase_order || '-' }}</el-descriptions-item>
            <el-descriptions-item label="采购日期">{{ currentDevice?.purchase_date || '-' }}</el-descriptions-item>
            <el-descriptions-item label="保修期">{{ currentDevice?.warranty_start && currentDevice?.warranty_end ? currentDevice.warranty_start + ' 至 ' + currentDevice.warranty_end : '-' }}</el-descriptions-item>
            <el-descriptions-item label="机柜">{{ currentDevice?.rack_name || '未上机' }}</el-descriptions-item>
            <el-descriptions-item label="U位">{{ currentDevice?.start_u ? currentDevice.start_u + 'U - ' + currentDevice.end_u + 'U' : '-' }}</el-descriptions-item>
            <el-descriptions-item label="状态"><el-tag :type="statusTag(currentDevice?.status || '')" size="small">{{ statusLabel(currentDevice?.status || '') }}</el-tag></el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatDate(currentDevice?.created_at || '') }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>
        <el-tab-pane label="生命周期" name="lifecycle">
          <el-Timerline v-if="lifecycleList.length">
            <el-Timerline-item v-for="item in lifecycleList" :key="item.id" :type="lifecycleActionTag(item.action)" :Timerstamp="formatDate(item.created_at)">
              <el-card shadow="never">
                <p><strong>{{ lifecycleActionLabel(item.action) }}</strong></p>
                <p class="text-muted">{{ item.description || '无描述' }}</p>
                <p class="text-muted">操作人：{{ item.operator }}</p>
              </el-card>
            </el-Timerline-item>
          </el-Timerline>
          <el-empty v-else description="暂无生命周期记录" />
        </el-tab-pane>
        <el-tab-pane label="监控阈值" name="threshold">
          <div v-if="deviceTypeThresholds.length" class="threshold-list">
            <div v-for="t in deviceTypeThresholds" :key="t.metric" class="threshold-item">
              <div class="threshold-label">{{ t.label || t.metric }}</div>
              <div class="threshold-value"><el-tag size="small" type="info">{{ t.min_value }} ~ {{ t.max_value }} {{ t.unit }}</el-tag></div>
              <el-tag size="small" :type="alertLevelTag(t.alert_level)">{{ alertLevelLabel(t.alert_level) }}</el-tag>
            </div>
          </div>
          <el-empty v-else description="该设备类型未配置阈值" />
        </el-tab-pane>
      </el-tabs>
    </el-dialog>

    <!-- 上机 -->
    <el-dialog v-model="mountDialog.visible" title="设备上机" width="500px">
      <el-form :model="mountForm" label-width="100px">
        <el-form-item label="选择机柜"><el-select v-model="mountForm.rack_id" filterable style="width:100%"><el-option v-for="r in racks" :key="r.id" :label="r.code + ' - ' + r.name" :value="r.id" /></el-select></el-form-item>
        <el-form-item label="起始U位"><el-input-number v-model="mountForm.start_u" :min="1" :max="42" style="width:100%" /></el-form-item>
        <el-form-item label="结束U位"><el-input-number v-model="mountForm.end_u" :min="mountForm.start_u" :max="42" style="width:100%" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="mountDialog.visible = false">取消</el-button><el-button type="primary" @click="confirmMount">确定上机</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue"
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus"
import { Plus, Edit, Delete, Refresh, Download, Box, CircleCheck, Warning, Bell, MoreFilled, Top, Bottom, Timer } from "@element-plus/icons-vue"
import { getDevicesApi, createDeviceApi, updateDeviceApi, deleteDeviceApi, getAllDeviceTypesApi, getAllRacksApi, getDeviceLifecyclesApi, type DeviceInfo, type DeviceTypeInfo, type RackInfo } from "../../api/device"

const statusOptions = [{ value: "online", label: "在线" }, { value: "offline", label: "离线" }, { value: "in_stock", label: "库存" }, { value: "maintenance", label: "维护中" }, { value: "retired", label: "已退役" }]

const deviceTypes = ref<DeviceTypeInfo[]>([])
const racks = ref<RackInfo[]>([])
const list = ref<DeviceInfo[]>([])
const loading = ref(false)
const submitting = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const keyword = ref("")
const filterStatus = ref("")
const filterType = ref<number>()
const filterRack = ref<number>()
const selectedIds = ref<number[]>([])

const stats = computed(() => ({ total: total.value, online: list.value.filter(d => d.status === "online").length, offline: list.value.filter(d => d.status === "offline").length, alert: list.value.filter(d => d.status === "alert").length }))

const dialog = ref({ visible: false, isEdit: false, id: 0 })
const detailDialog = ref({ visible: false })
const mountDialog = ref({ visible: false })
const currentDevice = ref<DeviceInfo | null>(null)
const detailTab = ref("info")
const lifecycleList = ref<any[]>([])
const deviceTypeThresholds = ref<any[]>([])
const mountForm = ref({ rack_id: null as number, start_u: 1, end_u: 1 })
const formRef = ref<FormInstance>()

const form = ref({ name: "", asset_number: "", device_type_id: undefined as number, brand: "", model: "", serial_number: "", management_ip: "", mac_address: "", cpu_info: "", memory_info: "", disk_info: "", vendor: "", purchase_date: null, warranty_start: null, warranty_end: null, rack_id: null as number, start_u: null as number, end_u: null as number, purchase_order: "" })

const formRules: FormRules = { name: [{ required: true, message: "请输入设备名称", trigger: "blur" }], asset_number: [{ required: true, message: "请输入资产编号", trigger: "blur" }] }

let debounceTimerr: ReturnType<typeof setTimerout>
function debounceFetch() { clearTimerout(debounceTimerr); debounceTimerr = setTimerout(() => { page.value = 1; fetchData() }, 300) }

onMounted(async () => { await Promise.all([fetchDeviceTypes(), fetchRacks()]); fetchData() })

async function fetchDeviceTypes() { try { deviceTypes.value = (await getAllDeviceTypesApi()).data } catch {} }
async function fetchRacks() { try { racks.value = (await getAllRacksApi()).data } catch {} }

async function fetchData() {
  loading.value = true
  try {
    const r = await getDevicesApi({ page: page.value, page_size: pageSize.value, keyword: keyword.value || undefined, status: filterStatus.value || undefined, device_type_id: filterType.value || undefined, rack_id: filterRack.value || undefined })
    list.value = r.data.items; total.value = r.data.total
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || "加载失败") }
  finally { loading.value = false }
}

function handleSizeChange() { page.value = 1; fetchData() }
function handleSelection(selection: DeviceInfo[]) { selectedIds.value = selection.map(s => s.id) }
function rowClassName({ row }: { row: DeviceInfo }) { if (row.status === "alert") return "row-alert"; if (row.status === "offline") return "row-offline"; return "" }

function openDialog(item?: DeviceInfo) {
  dialog.value = { visible: true, isEdit: !!item, id: item?.id || 0 }
  form.value = item ? { name: item.name, asset_number: item.asset_number, device_type_id: item.device_type_id, brand: item.brand || "", model: item.model || "", serial_number: item.serial_number || "", management_ip: item.management_ip || "", mac_address: item.mac_address || "", cpu_info: item.cpu_info || "", memory_info: item.memory_info || "", disk_info: item.disk_info || "", vendor: item.vendor || "", purchase_date: item.purchase_date || null, warranty_start: item.warranty_start || null, warranty_end: item.warranty_end || null, rack_id: item.rack_id, start_u: item.start_u, end_u: item.end_u, purchase_order: item.purchase_order || "" } : { name: "", asset_number: "", device_type_id: undefined, brand: "", model: "", serial_number: "", management_ip: "", mac_address: "", cpu_info: "", memory_info: "", disk_info: "", vendor: "", purchase_date: null, warranty_start: null, warranty_end: null, rack_id: null, start_u: null, end_u: null, purchase_order: "" }
}

async function submitForm() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    const data = { ...form.value }
    if (!data.rack_id) { data.rack_id = undefined as any; data.start_u = undefined; data.end_u = undefined }
    if (dialog.value.isEdit) { await updateDeviceApi(dialog.value.id, data); ElMessage.success("更新成功") }
    else { await createDeviceApi(data); ElMessage.success("创建成功") }
    dialog.value.visible = false; fetchData()
  } catch (err: any) { ElMessage.error(err.response?.data?.detail || "操作失败") }
  finally { submitting.value = false }
}

async function deleteItem(item: DeviceInfo) {
  try { await ElMessageBox.confirm(`确定删除设备 "${item.name}"？`, "确认删除", { type: "warning" }); await deleteDeviceApi(item.id); ElMessage.success("删除成功"); fetchData() } catch {}
}

function handleCommand(cmd: any, row: DeviceInfo) {
  if (cmd === "unmount") unmountDevice(row)
  else if (cmd === "mount") { mountForm.value = { rack_id: null, start_u: 1, end_u: 1 }; currentDevice.value = row; mountDialog.value.visible = true }
  else if (cmd === "lifecycle") showDetail(row)
  else if (cmd === "delete") deleteItem(row)
}

async function unmountDevice(item: DeviceInfo) {
  try { await ElMessageBox.confirm(`确定将设备 "${item.name}" 下架？`, "确认下架", { type: "warning" }); await updateDeviceApi(item.id, { rack_id: null, start_u: null, end_u: null, status: "in_stock" }); ElMessage.success("已下架"); fetchData() } catch {}
}

async function confirmMount() {
  if (!mountForm.value.rack_id) { ElMessage.warning("请选择机柜"); return }
  if (!currentDevice.value) return
  try { await updateDeviceApi(currentDevice.value.id, { rack_id: mountForm.value.rack_id, start_u: mountForm.value.start_u, end_u: mountForm.value.end_u, status: "online" }); ElMessage.success("上机成功"); mountDialog.value.visible = false; fetchData() } catch (e: any) { ElMessage.error(e.response?.data?.detail || "上机失败") }
}

function onRackChange() { if (!form.value.rack_id) { form.value.start_u = undefined; form.value.end_u = undefined } }

async function showDetail(item: DeviceInfo) {
  currentDevice.value = item; detailTab.value = "info"; detailDialog.value.visible = true; lifecycleList.value = []
  try { const r = await getDeviceLifecyclesApi(item.id); lifecycleList.value = r.data || [] } catch {}
  const dt = deviceTypes.value.find(t => t.id === item.device_type_id); deviceTypeThresholds.value = dt?.thresholds || []
}

async function batchDelete() {
  try { await ElMessageBox.confirm(`确定删除选中的 ${selectedIds.value.length} 台设备？`, "批量删除", { type: "warning" }); for (const id of selectedIds.value) await deleteDeviceApi(id); ElMessage.success("批量删除成功"); selectedIds.value = []; fetchData() } catch {}
}

function batchExport() {
  const data = list.value.filter(d => selectedIds.value.includes(d.id))
  const csv = [["名称", "资产编号", "类型", "品牌", "型号", "机柜", "状态"].join(","), ...data.map(d => [d.name, d.asset_number, d.device_type_name, d.brand, d.model, d.rack_name || "未上机", statusLabel(d.status)].join(","))].join("\n")
  downloadFile(csv, "设备导出.csv")
}

function exportDevices() {
  const csv = [["名称", "资产编号", "类型", "品牌", "型号", "序列号", "管理IP", "机柜", "状态", "采购日期"].join(","), ...list.value.map(d => [d.name, d.asset_number, d.device_type_name, d.brand, d.model, d.serial_number || "", d.management_ip || "", d.rack_name || "未上机", statusLabel(d.status), d.purchase_date || ""].join(","))].join("\n")
  downloadFile(csv, "设备台账.csv")
}

function downloadFile(content: string, filename: string) { const blob = new Blob(["\ufeff" + content], { type: "text/csv;charset=utf-8" }); const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = filename; a.click(); URL.revokeObjectURL(url) }

function formatDate(dateStr: string) { if (!dateStr) return "-"; return new Date(dateStr).toLocaleString("zh-CN") }
function statusLabel(s: string) { const map: Record<string, string> = { online: "在线", offline: "离线", in_stock: "库存", maintenance: "维护中", retired: "已退役", alert: "告警" }; return map[s] || s }
function statusTag(s: string) { const map: Record<string, string> = { online: "success", offline: "warning", in_stock: "info", maintenance: "warning", retired: "danger", alert: "danger" }; return map[s] || "" }
function lifecycleActionLabel(a: string) { const map: Record<string, string> = { create: "创建", change: "变更", repair: "维修", mount: "上机", unmount: "下架" }; return map[a] || a }
function lifecycleActionTag(a: string) { const map: Record<string, string> = { create: "success", change: "warning", repair: "info", mount: "primary", unmount: "danger" }; return map[a] || "" }
function alertLevelLabel(l: string) { const map: Record<string, string> = { general: "一般", serious: "严重", emergency: "紧急" }; return map[l] || l }
function alertLevelTag(l: string) { const map: Record<string, string> = { general: "", serious: "warning", emergency: "danger" }; return map[l] || "" }
</script>

<style scoped>
.device-page { padding: 0; }
.page-header { margin-bottom: 20px; }
.page-title { font-size: 20px; font-weight: 600; margin: 0; }
.page-desc { font-size: 14px; color: var(--app-text-muted); margin: 6px 0 0; }

.stats-row { margin-bottom: 20px; }
.stat-card { border-radius: 12px; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); }
.stat-card:hover { transform: translateY(-2px); box-shadow: var(--app-shadow-hover); }
.stat-item { display: flex; align-items: center; gap: 16px; }
.stat-icon-box { width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; color: #fff; }
.gradient-primary { background: linear-gradient(135deg, #4361ee 0%, #7289ff 100%); }
.gradient-success { background: linear-gradient(135deg, #10b981 0%, #34d399 100%); }
.gradient-warning { background: linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%); }
.gradient-danger { background: linear-gradient(135deg, #ef4444 0%, #f87171 100%); }
.stat-info { display: flex; flex-direction: column; }
.stat-num { font-size: 24px; font-weight: 700; line-height: 1.2; }
.stat-label { font-size: 13px; color: var(--app-text-muted); }

.table-card { border-radius: 12px; }
.table-toolbar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
.toolbar-left { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.toolbar-right { display: flex; gap: 8px; }

.batch-bar { display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: var(--el-color-primary-light-9); border-radius: 8px; margin-bottom: 12px; }
.batch-tip { font-weight: 500; color: var(--el-color-primary); }

.device-name { display: flex; align-items: center; gap: 8px; color: var(--el-color-primary); }
.rack-link { color: var(--el-color-primary); cursor: pointer; }
.rack-link:hover { text-decoration: underline; }

.pagination-wrapper { display: flex; justify-content: flex-end; margin-top: 16px; }

.threshold-list { display: flex; flex-direction: column; gap: 12px; }
.threshold-item { display: flex; align-items: center; gap: 16px; padding: 12px 16px; background: var(--el-fill-color-light); border-radius: 8px; }
.threshold-label { font-weight: 500; min-width: 100px; }
.threshold-value { flex: 1; }

:deep(.row-alert) { background-color: var(--el-color-danger-light-9) !important; }
:deep(.row-offline) { background-color: var(--el-color-warning-light-9) !important; }

.text-muted { color: var(--app-text-muted); font-size: 13px; }
:deep(.el-divider--horizontal) { margin: 16px 0; }
</style>