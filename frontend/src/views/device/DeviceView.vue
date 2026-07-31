<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h3 class="page-title">设备台账</h3>
        <p class="page-desc">管理所有设备的资产信息与生命周期</p>
      </div>
    </div>

    <el-card class="table-card">
      <template #header>
        <div class="flex-wrap">
          <el-input v-model="keyword" placeholder="名称/资产号..." clearable style="width:240px" @input="fetchData" />
          <el-select v-model="filterStatus" clearable placeholder="状态" style="width:120px" @change="fetchData">
            <el-option v-for="s in statuses" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
          <el-select v-model="filterType" clearable placeholder="类型" style="width:140px" @change="fetchData">
            <el-option v-for="t in deviceTypes" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
          <div style="flex:1"></div>
          <el-button type="primary" :icon="Plus" @click="openDialog()">新增设备</el-button>
        </div>
      </template>
      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column prop="name" label="名称" min-width="140" />
        <el-table-column prop="asset_number" label="资产号" width="120" />
        <el-table-column prop="device_type_name" label="类型" width="100" />
        <el-table-column prop="brand" label="品牌" width="90" />
        <el-table-column prop="model" label="型号" width="100" />
        <el-table-column prop="rack_name" label="机柜" width="90" />
        <el-table-column label="U位" width="70" align="center">
          <template #default="{ row }">{{ row.start_u || "-" }}-{{ row.end_u || "-" }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right" align="center">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="showDetail(row)">详情</el-button>
            <el-button text type="primary" size="small" :icon="Edit" @click="openDialog(row)">编辑</el-button>
            <el-button v-if="row.rack_id" text size="small" type="warning" @click="unmountDevice(row)">下架</el-button>
            <el-button text type="danger" size="small" :icon="Delete" @click="deleteItem(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-if="total > pageSize" v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, prev, pager, next" class="pagination" @current-change="fetchData" />
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialog.visible" :title="dialog.isEdit ? '编辑设备' : '新增设备'" width="720px">
      <el-form :model="form" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="设备名称" prop="name" :rules="[{required:true}]">
              <el-input v-model="form.name" placeholder="请输入设备名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="资产编号" prop="asset_number" :rules="[{required:true}]">
              <el-input v-model="form.asset_number" placeholder="请输入资产编号" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="设备类型">
              <el-select v-model="form.device_type_id" filterable style="width:100%">
                <el-option v-for="t in deviceTypes" :key="t.id" :label="t.name" :value="t.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="品牌">
              <el-input v-model="form.brand" placeholder="如：华为" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="型号">
              <el-input v-model="form.model" placeholder="如：RH2288H" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="序列号">
              <el-input v-model="form.serial_number" placeholder="序列号" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="管理IP">
              <el-input v-model="form.management_ip" placeholder="管理IP" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="MAC地址">
              <el-input v-model="form.mac_address" placeholder="MAC地址" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-collapse>
          <el-collapse-item title="上架信息" name="mount">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="机柜">
                  <el-select v-model="form.rack_id" filterable clearable placeholder="选择机柜" style="width:100%">
                    <el-option v-for="r in rackList" :key="r.id" :label="r.code + ' - ' + r.name" :value="r.id" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="起始U位">
                  <el-input-number v-model="form.start_u" :min="1" :step="1" style="width:100%" />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="结束U位">
                  <el-input-number v-model="form.end_u" :min="1" :step="1" style="width:100%" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-collapse-item>
          <el-collapse-item title="维保信息" name="warranty">
            <el-row :gutter="16">
              <el-col :span="8">
                <el-form-item label="采购日期">
                  <el-date-picker v-model="form.purchase_date" type="date" value-format="YYYY-MM-DD" style="width:100%" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="保修开始">
                  <el-date-picker v-model="form.warranty_start" type="date" value-format="YYYY-MM-DD" style="width:100%" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="保修结束">
                  <el-date-picker v-model="form.warranty_end" type="date" value-format="YYYY-MM-DD" style="width:100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="供应商">
                  <el-input v-model="form.vendor" placeholder="供应商" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="采购订单">
                  <el-input v-model="form.purchase_order" placeholder="采购订单号" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-collapse-item>
        </el-collapse>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="submit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 设备详情对话框 -->
    <el-dialog v-model="detailDialog.visible" :title="`设备详情 - ${currentDevice?.name}`" width="800px">
      <el-tabs v-model="detailTab">
        <el-tab-pane label="基本信息" name="info">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="资产编号">{{ currentDevice?.asset_number }}</el-descriptions-item>
            <el-descriptions-item label="设备类型">{{ currentDevice?.device_type_name }}</el-descriptions-item>
            <el-descriptions-item label="品牌">{{ currentDevice?.brand || "-" }}</el-descriptions-item>
            <el-descriptions-item label="型号">{{ currentDevice?.model || "-" }}</el-descriptions-item>
            <el-descriptions-item label="序列号">{{ currentDevice?.serial_number || "-" }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="statusTag(currentDevice?.status || '')" size="small">{{ statusLabel(currentDevice?.status || '') }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="管理IP">{{ currentDevice?.management_ip || "-" }}</el-descriptions-item>
            <el-descriptions-item label="MAC地址">{{ currentDevice?.mac_address || "-" }}</el-descriptions-item>
            <el-descriptions-item label="位置" :span="2">
              {{ currentDevice?.room_name || "-" }} / {{ currentDevice?.rack_name || "-" }}
              <span v-if="currentDevice?.start_u"> (U{{ currentDevice?.start_u }}-{{ currentDevice?.end_u }})</span>
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ currentDevice?.created_at }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ currentDevice?.updated_at }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>

        <el-tab-pane label="生命周期历史" name="lifecycle">
          <el-table :data="lifecycleList" stripe size="small" max-height="400">
            <el-table-column prop="created_at" label="时间" width="160">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column prop="action" label="操作" width="80">
              <template #default="{ row }">
                <el-tag size="small" :type="lifecycleActionTag(row.action)">{{ lifecycleActionLabel(row.action) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态变更" width="160">
              <template #default="{ row }">
                <span v-if="row.from_status">{{ row.from_status }} -> {{ row.to_status }}</span>
                <span v-else>{{ row.to_status }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="operator" label="操作人" width="100" />
            <el-table-column prop="remark" label="备注" min-width="150" show-overflow-tooltip />
          </el-table>
          <el-empty v-if="!lifecycleList.length" description="暂无生命周期记录" />
        </el-tab-pane>

        <el-tab-pane label="阈值配置" name="thresholds">
          <div v-if="deviceTypeThresholds.length" class="threshold-list">
            <div v-for="(t, i) in deviceTypeThresholds" :key="i" class="threshold-item">
              <div class="threshold-label">{{ t.label || t.metric }}</div>
              <div class="threshold-value">
                <span v-if="t.min_value !== null">下限: {{ t.min_value }}{{ t.unit }}</span>
                <span v-if="t.min_value !== null && t.max_value !== null"> / </span>
                <span v-if="t.max_value !== null">上限: {{ t.max_value }}{{ t.unit }}</span>
              </div>
              <el-tag :type="alertLevelTag(t.alert_level)" size="small">{{ alertLevelLabel(t.alert_level) }}</el-tag>
              <el-tag :type="t.enabled ? 'success' : 'info'" size="small">{{ t.enabled ? '已启用' : '已停用' }}</el-tag>
            </div>
          </div>
          <el-empty v-else description="该设备类型未配置阈值" />
        </el-tab-pane>
      </el-tabs>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Plus, Edit, Delete } from "@element-plus/icons-vue";
import { getDevicesApi, createDeviceApi, updateDeviceApi, deleteDeviceApi, getDeviceLifecyclesApi, getAllDeviceTypesApi } from "../../api/device";
import type { DeviceInfo, DeviceTypeInfo, ThresholdConfig } from "../../api/device";
import { getRacksApi } from "../../api/facility";
import type { RackInfo } from "../../api/facility";

interface LifecycleRecord {
  id: number;
  device_id: number;
  action: string;
  from_status: string | null;
  to_status: string;
  operator: string | null;
  remark: string | null;
  created_at: string;
}

const loading = ref(false);
const list = ref<DeviceInfo[]>([]);
const keyword = ref("");
const page = ref(1);
const pageSize = ref(10);
const total = ref(0);
const filterStatus = ref("");
const filterType = ref("");
const deviceTypes = ref<DeviceTypeInfo[]>([]);
const rackList = ref<RackInfo[]>([]);

const statuses = [
  { value: "in_stock", label: "在库" },
  { value: "mounted", label: "已上架" },
  { value: "running", label: "运行中" },
  { value: "offline", label: "已下线" },
  { value: "scrapped", label: "已报废" },
];

function statusLabel(s: string) { return statuses.find(x => x.value === s)?.label || s; }
function statusTag(s: string) {
  const map: Record<string, string> = { in_stock: "info", mounted: "", running: "success", offline: "warning", scrapped: "danger" };
  return map[s] || "";
}

const dialog = ref({ visible: false, isEdit: false, id: 0 });
const form = ref<any>({
  name: "", asset_number: "", device_type_id: undefined, brand: "", model: "", serial_number: "", management_ip: "", mac_address: "",
  cpu_info: "", memory_info: "", disk_info: "", vendor: "", purchase_date: null, warranty_start: null, warranty_end: null,
  rack_id: null, start_u: null, end_u: null, purchase_order: ""
});

const detailDialog = ref({ visible: false });
const detailTab = ref("info");
const currentDevice = ref<DeviceInfo | null>(null);
const lifecycleList = ref<LifecycleRecord[]>([]);
const deviceTypeThresholds = ref<ThresholdConfig[]>([]);

onMounted(async () => {
  await fetchDeviceTypes();
  await fetchRacks();
  fetchData();
});

async function fetchRacks() {
  try {
    const r = await getRacksApi({ page: 1, page_size: 200 });
    rackList.value = r.data.items;
  } catch {}
}

async function fetchDeviceTypes() {
  try {
    const r = await getAllDeviceTypesApi();
    deviceTypes.value = r.data as any;
  } catch {}
}

async function fetchData() {
  loading.value = true;
  try {
    const r = await getDevicesApi({
      page: page.value, page_size: pageSize.value,
      keyword: keyword.value || undefined,
      status: filterStatus.value || undefined,
      device_type_id: filterType.value || undefined,
    });
    list.value = r.data.items;
    total.value = r.data.total;
  } finally {
    loading.value = false;
  }
}

function openDialog(item?: DeviceInfo) {
  dialog.value = { visible: true, isEdit: !!item, id: item?.id || 0 };
  form.value = item
    ? {
        name: item.name, asset_number: item.asset_number, device_type_id: item.device_type_id,
        brand: item.brand || "", model: item.model || "", serial_number: item.serial_number || "", management_ip: item.management_ip || "", mac_address: item.mac_address || "",
        cpu_info: item.cpu_info || "", memory_info: item.memory_info || "", disk_info: item.disk_info || "", vendor: item.vendor || "", purchase_date: item.purchase_date || null,
        warranty_start: item.warranty_start || null, warranty_end: item.warranty_end || null, rack_id: item.rack_id ?? null, start_u: item.start_u ?? null, end_u: item.end_u ?? null,
        purchase_order: item.purchase_order || ""
      }
    : {
        name: "", asset_number: "", device_type_id: undefined, brand: "", model: "", serial_number: "", management_ip: "", mac_address: "",
        cpu_info: "", memory_info: "", disk_info: "", vendor: "", purchase_date: null, warranty_start: null, warranty_end: null,
        rack_id: null, start_u: null, end_u: null, purchase_order: ""
      };
}

async function submit() {
  loading.value = true;
  try {
    const data = { ...form.value };
    if (!data.rack_id) { data.rack_id = undefined; data.start_u = undefined; data.end_u = undefined; }
    if (dialog.value.isEdit) {
      await updateDeviceApi(dialog.value.id, data);
      ElMessage.success("已更新");
    } else {
      await createDeviceApi(data);
      ElMessage.success("已创建");
    }
    dialog.value.visible = false;
    fetchData();
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || "操作失败");
  } finally {
    loading.value = false;
  }
}

async function deleteItem(item: DeviceInfo) {
  try {
    await ElMessageBox.confirm("删除设备 \"" + item.name + "\"？", "确认");
    await deleteDeviceApi(item.id);
    ElMessage.success("已删除");
    fetchData();
  } catch {}
}

async function showDetail(item: DeviceInfo) {
  currentDevice.value = item;
  detailTab.value = "info";
  detailDialog.value.visible = true;
  lifecycleList.value = [];

  try {
    const r = await getDeviceLifecyclesApi(item.id);
    lifecycleList.value = r.data || [];
  } catch {}

  const dt = deviceTypes.value.find(t => t.id === item.device_type_id);
  deviceTypeThresholds.value = dt?.thresholds || [];
}

async function unmountDevice(item: DeviceInfo) {
  try {
    await ElMessageBox.confirm("确定将设备 \"" + item.name + "\" 从机柜下架？", "确认下架", { type: "warning" });
    await updateDeviceApi(item.id, { rack_id: undefined, start_u: undefined, end_u: undefined, status: "in_stock" });
    ElMessage.success("已下架");
    fetchData();
  } catch {}
}

function formatDate(dateStr: string): string {
  if (!dateStr) return "-";
  return new Date(dateStr).toLocaleString("zh-CN");
}

function lifecycleActionLabel(a: string) {
  const map: Record<string, string> = { create: "创建", change: "变更", repair: "维修" };
  return map[a] || a;
}

function lifecycleActionTag(a: string) {
  const map: Record<string, string> = { create: "success", change: "warning", repair: "info" };
  return map[a] || "";
}

function alertLevelLabel(l: string) {
  const map: Record<string, string> = { general: "一般", serious: "严重", emergency: "紧急" };
  return map[l] || l;
}

function alertLevelTag(l: string) {
  const map: Record<string, string> = { general: "", serious: "warning", emergency: "danger" };
  return map[l] || "";
}
</script>

<style scoped>
.page-header { margin-bottom: 16px; }
.page-title { font-size: 18px; font-weight: 600; margin: 0; }
.page-desc { font-size: 13px; color: #909399; margin: 4px 0 0; }
.table-card { border-radius: 10px; }
.pagination { display: flex; justify-content: flex-end; margin-top: 12px; }
.flex-wrap { display: flex; flex-wrap: wrap; gap: 8px; }

.threshold-list { display: flex; flex-direction: column; gap: 8px; }
.threshold-item { display: flex; align-items: center; gap: 12px; padding: 8px 12px; background: #f5f7fa; border-radius: 6px; }
.threshold-label { font-weight: 500; min-width: 100px; }
.threshold-value { flex: 1; color: #606266; font-size: 13px; }
</style>
