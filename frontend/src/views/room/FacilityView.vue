<template>
  <div class="facility-page">
    <div class="page-header">
      <div>
        <h3 class="page-title">机房管理</h3>
        <p class="page-desc">管理数据中心、机房及机柜设施信息</p>
      </div>
    </div>

    <!-- 数据中心 & 机房选择 -->
    <el-card shadow="never" class="selector-card">
      <el-row :gutter="24">
        <el-col :span="8">
          <div class="selector-label">选择数据中心</div>
          <el-select v-model="selectedDataCenterId" placeholder="请选择数据中心" size="large" style="width: 100%" @change="onDataCenterChange">
            <el-option v-for="dc in dataCenterList" :key="dc.id" :label="dc.name" :value="dc.id">
              <span>{{ dc.name }}</span>
              <span class="dc-info"> ({{ dc.code }})</span>
            </el-option>
          </el-select>
        </el-col>
        <el-col :span="8">
          <div class="selector-label">选择机房</div>
          <el-select v-model="selectedRoomId" placeholder="请选择机房" size="large" style="width: 100%" @change="onRoomChange">
            <el-option v-for="r in roomList" :key="r.id" :label="r.name" :value="r.id">
              <span>{{ r.name }}</span>
              <span class="room-info"> ({{ r.tier_level || '未设置' }})</span>
            </el-option>
          </el-select>
        </el-col>
        <el-col :span="8">
          <div class="selector-label">快速操作</div>
          <div class="quick-actions">
            <el-button type="primary" :icon="Plus" @click="openDataCenterDialog()">新建数据中心</el-button>
            <el-button :disabled="!selectedDataCenterId" :icon="Plus" @click="openRoomDialog()">新建机房</el-button>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 统计信息 -->
    <el-row :gutter="16" class="stats-row" v-if="selectedRoomId">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-item">
            <div class="stat-icon-box" style="background: #e8f5e9">
              <el-icon :size="22" color="#27ae60"><Odometer /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-num">{{ currentRoom?.rack_count || 0 }}</span>
              <span class="stat-label">机柜数量</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-item">
            <div class="stat-icon-box" style="background: #e3f2fd">
              <el-icon :size="22" color="#1976d2"><Cpu /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-num">{{ totalRackDevices }}</span>
              <span class="stat-label">设备总数</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-item">
            <div class="stat-icon-box" style="background: #fef3e2">
              <el-icon :size="22" color="#e67e22"><Coin /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-num">{{ totalRatedPower }} kW</span>
              <span class="stat-label">额定功率</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card" @click="openRoomDetailDialog()" style="cursor: pointer">
          <div class="stat-item">
            <div class="stat-icon-box" style="background: #fce4ec">
              <el-icon :size="22" color="#e74c3c"><InfoFilled /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-num" style="font-size: 14px; color: var(--app-text-secondary)">查看详情</span>
              <span class="stat-label">机房信息</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 机柜列表 -->
    <el-card shadow="never" class="table-card" v-if="selectedRoomId">
      <template #header>
        <div class="table-header">
          <span>机柜列表</span>
          <div class="header-actions">
            <el-input v-model="rackSearch" placeholder="搜索机柜..." prefix-icon="Search" clearable size="small" style="width: 200px" @input="fetchRacks" />
            <el-button :icon="Refresh" @click="fetchRacks()">刷新</el-button>
            <el-button type="primary" :icon="Plus" @click="openRackDialog()">新增机柜</el-button>
          </div>
        </div>
      </template>
      <el-table :data="filteredRacks" v-loading="loading" stripe>
        <el-table-column prop="code" label="机柜编号" width="120">
          <template #default="{ row }">
            <span class="rack-code">{{ row.code }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="机柜名称" min-width="120" />
        <el-table-column label="U位使用" width="180">
          <template #default="{ row }">
            <el-progress :percentage="rackUtilPercent(row)" :color="rackUtilColor(row)" :stroke-width="10">
              <span>{{ row.total_units - row.available_units }}/{{ row.total_units }}U</span>
            </el-progress>
          </template>
        </el-table-column>
        <el-table-column prop="device_count" label="设备数" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.device_count }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="rated_power" label="额定功率" width="100">
          <template #default="{ row }">
            {{ row.rated_power ? row.rated_power + ' kW' : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="row_pos" label="位置" width="100">
          <template #default="{ row }">
            {{ row.row_pos ? '行' + row.row_pos : '' }}{{ row.col_pos ? ' 列' + row.col_pos : '' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '正常' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right" align="center">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="openRackDialog(row)">编辑</el-button>
            <el-button text type="danger" size="small" @click="deleteRack(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 空状态提示 -->
    <el-empty v-if="!selectedRoomId" description="请先选择数据中心和机房" />

    <!-- 数据中心对话框 -->
    <el-dialog v-model="dcDialog.visible" :title="dcDialog.isEdit ? '编辑数据中心' : '新建数据中心'" width="500px">
      <el-form :model="dcForm" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="dcForm.name" placeholder="如：北京数据中心" />
        </el-form-item>
        <el-form-item label="编码" required>
          <el-input v-model="dcForm.code" placeholder="如：DC-BJ-01" />
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="dcForm.address" placeholder="详细地址" />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="dcForm.contact_person" placeholder="联系人姓名" />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="dcForm.contact_phone" placeholder="联系电话" />
        </el-form-item>
        <el-form-item label="联系邮箱">
          <el-input v-model="dcForm.contact_email" placeholder="联系邮箱" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="dcForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dcDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitDataCenter">确定</el-button>
      </template>
    </el-dialog>

    <!-- 机房对话框 -->
    <el-dialog v-model="roomDialog.visible" :title="roomDialog.isEdit ? '编辑机房' : '新建机房'" width="600px">
      <el-form :model="roomForm" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="机房名称" required>
              <el-input v-model="roomForm.name" placeholder="如：主机房A区" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="机房编号" required>
              <el-input v-model="roomForm.code" placeholder="如：RM-001" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="楼层">
              <el-input v-model="roomForm.floor" placeholder="如：3楼/地下一层" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="面积(㎡)">
              <el-input-number v-model="roomForm.area" :min="0" :precision="1" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="承重等级">
          <el-input v-model="roomForm.load_rating" placeholder="如：800kg/㎡" />
        </el-form-item>
        <el-form-item label="Tier等级">
          <el-select v-model="roomForm.tier_level" style="width: 100%">
            <el-option label="未评定" value="" />
            <el-option label="Tier I" value="Tier I" />
            <el-option label="Tier II" value="Tier II" />
            <el-option label="Tier III" value="Tier III" />
            <el-option label="Tier IV" value="Tier IV" />
          </el-select>
        </el-form-item>
        <el-divider content-position="left">管理员信息</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="管理员">
              <el-input v-model="roomForm.admin_name" placeholder="管理员姓名" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="电话">
              <el-input v-model="roomForm.admin_phone" placeholder="联系电话" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="邮箱">
          <el-input v-model="roomForm.admin_email" placeholder="管理员邮箱" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="roomForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="roomDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitRoom">确定</el-button>
      </template>
    </el-dialog>

    <!-- 机房详情对话框 -->
    <el-dialog v-model="roomDetailDialog.visible" :title="`机房详情 - ${currentRoom?.name}`" width="700px">
      <el-descriptions :column="2" border v-if="currentRoom">
        <el-descriptions-item label="机房编号">{{ currentRoom.code }}</el-descriptions-item>
        <el-descriptions-item label="所属数据中心">{{ currentRoom.data_center_name }}</el-descriptions-item>
        <el-descriptions-item label="楼层">{{ currentRoom.floor || '-' }}</el-descriptions-item>
        <el-descriptions-item label="面积">{{ currentRoom.area ? currentRoom.area + ' ㎡' : '-' }}</el-descriptions-item>
        <el-descriptions-item label="承重等级">{{ currentRoom.load_rating || '-' }}</el-descriptions-item>
        <el-descriptions-item label="Tier等级">
          <el-tag v-if="currentRoom.tier_level" type="warning">{{ currentRoom.tier_level }}</el-tag>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="管理员">{{ currentRoom.admin_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="联系电话">{{ currentRoom.admin_phone || '-' }}</el-descriptions-item>
        <el-descriptions-item label="管理员邮箱" :span="2">{{ currentRoom.admin_email || '-' }}</el-descriptions-item>
        <el-descriptions-item label="描述" :span="2">{{ currentRoom.description || '-' }}</el-descriptions-item>
        <el-descriptions-item label="机柜数量">{{ currentRoom.rack_count }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="currentRoom.status === 'active' ? 'success' : 'info'">
            {{ currentRoom.status === 'active' ? '正常' : '停用' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDate(currentRoom.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ formatDate(currentRoom.updated_at) }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="openRoomDialog(currentRoom!)">编辑机房</el-button>
        <el-button @click="roomDetailDialog.visible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 机柜对话框 -->
    <el-dialog v-model="rackDialog.visible" :title="rackDialog.isEdit ? '编辑机柜' : '新增机柜'" width="500px">
      <el-form ref="rackFormRef" :model="rackForm" label-width="100px" :rules="rackRules">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="机柜编号" prop="code">
              <el-input v-model="rackForm.code" placeholder="如：A01" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="机柜名称" prop="name">
              <el-input v-model="rackForm.name" placeholder="如：主网络机柜" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="总U位数">
              <el-input-number v-model="rackForm.total_units" :min="1" :max="52" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="额定功率">
              <el-input-number v-model="rackForm.rated_power" :min="0" :precision="1" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="所在行">
              <el-input-number v-model="rackForm.row_pos" :min="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所在列">
              <el-input-number v-model="rackForm.col_pos" :min="1" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="描述">
          <el-input v-model="rackForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rackDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitRack">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue"
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus"
import { Plus, Refresh } from "@element-plus/icons-vue"
import {
  getAllDataCentersApi, getDataCentersApi, createDataCenterApi, updateDataCenterApi, deleteDataCenterApi,
  getAllRoomsApi, getRoomsApi, createRoomApi, updateRoomApi, deleteRoomApi,
  getAllRacksApi, getRacksApi, createRackApi, updateRackApi, deleteRackApi,
  type DataCenterInfo, type RoomInfo, type RackInfo
} from "@/api/facility"

const loading = ref(false)
const submitting = ref(false)

// 数据中心相关
const dataCenterList = ref<DataCenterInfo[]>([])
const selectedDataCenterId = ref<number | null>(null)

// 机房相关
const roomList = ref<RoomInfo[]>([])
const selectedRoomId = ref<number | null>(null)
const currentRoom = ref<RoomInfo | null>(null)

// 机柜相关
const rackList = ref<RackInfo[]>([])
const rackSearch = ref("")

// 对话框状态
const dcDialog = ref({ visible: false, isEdit: false, id: 0 })
const roomDialog = ref({ visible: false, isEdit: false, id: 0 })
const roomDetailDialog = ref({ visible: false })
const rackDialog = ref({ visible: false, isEdit: false, id: 0 })
const rackFormRef = ref<FormInstance>()

// 表单数据
const dcForm = ref({ status: "active", name: "", code: "", address: "", contact_person: "", contact_phone: "", contact_email: "", description: ""
})

const roomForm = ref({
  name: "", code: "", floor: "", area: undefined as number | undefined,
  load_rating: "", admin_name: "", admin_phone: "", admin_email: "",
  tier_level: "", description: ""
})

const rackForm = ref({
  code: "", name: "", total_units: 42, rated_power: undefined as number | undefined,
  row_pos: undefined as number | undefined, col_pos: undefined as number | undefined,
  description: ""
})

const rackRules: FormRules = {
  code: [{ required: true, message: "请输入机柜编号", trigger: "blur" }],
  name: [{ required: true, message: "请输入机柜名称", trigger: "blur" }]
}

// 计算属性
const filteredRacks = computed(() => {
  if (!rackSearch.value) return rackList.value
  const kw = rackSearch.value.toLowerCase()
  return rackList.value.filter(r =>
    r.code.toLowerCase().includes(kw) || r.name.toLowerCase().includes(kw)
  )
})

const totalRackDevices = computed(() => {
  return rackList.value.reduce((sum, r) => sum + r.device_count, 0)
})

const totalRatedPower = computed(() => {
  return rackList.value.reduce((sum, r) => sum + (r.rated_power || 0), 0).toFixed(1)
})

function rackUtilPercent(rack: RackInfo): number {
  if (!rack.total_units) return 0
  return Math.round((rack.total_units - rack.available_units) / rack.total_units * 100)
}

function rackUtilColor(rack: RackInfo): string {
  const p = rackUtilPercent(rack)
  if (p >= 80) return "#e74c3c"
  if (p >= 50) return "#e67e22"
  return "#27ae60"
}

function formatDate(dateStr: string): string {
  if (!dateStr) return "-"
  return new Date(dateStr).toLocaleString("zh-CN")
}

// 生命周期
onMounted(async () => {
  await fetchDataCenters()
})

// 数据获取
async function fetchDataCenters() {
  try {
    const r = await getAllDataCentersApi()
    dataCenterList.value = r.data
    if (dataCenterList.value.length > 0 && !selectedDataCenterId.value) {
      selectedDataCenterId.value = dataCenterList.value[0].id
      await fetchRooms()
    }
  } catch (err) {
    console.error(err)
  }
}

async function fetchRooms() {
  if (!selectedDataCenterId.value) {
    roomList.value = []
    return
  }
  try {
    const r = await getAllRoomsApi(selectedDataCenterId.value)
    roomList.value = r.data
    // 选中第一个或保持之前选中的
    if (roomList.value.length > 0 && !selectedRoomId.value) {
      selectedRoomId.value = roomList.value[0].id
      await fetchRacks()
    } else if (selectedRoomId.value) {
      await fetchRacks()
    }
  } catch (err) {
    console.error(err)
  }
}

async function fetchRacks() {
  if (!selectedRoomId.value) {
    rackList.value = []
    return
  }
  loading.value = true
  try {
    const r = await getAllRacksApi(selectedRoomId.value)
    rackList.value = r.data
    // 获取机房详情
    const room = roomList.value.find(r => r.id === selectedRoomId.value)
    if (room) {
      currentRoom.value = room
    }
  } catch (err) {
    console.error(err)
    rackList.value = []
  } finally {
    loading.value = false
  }
}

function onDataCenterChange() {
  selectedRoomId.value = null
  rackList.value = []
  currentRoom.value = null
  fetchRooms()
}

function onRoomChange() {
  fetchRacks()
}

// 数据中心操作
function openDataCenterDialog(dc?: DataCenterInfo) {
  dcDialog.value = { visible: true, isEdit: !!dc, id: dc?.id || 0 }
  if (dc) {
    dcForm.value = { status: dc.status || "active", name: dc.name, code: dc.code, address: dc.address || "",
      contact_person: dc.contact_person || "", contact_phone: dc.contact_phone || "",
      contact_email: dc.contact_email || "", description: dc.description || ""
    }
  } else { dcForm.value = { status: "active", name: "", code: "", address: "", contact_person: "", contact_phone: "", contact_email: "", description: "" }
  }
}

async function submitDataCenter() {
  if (!dcForm.value.name || !dcForm.value.code) {
    ElMessage.warning("请填写名称和编码")
    return
  }
  submitting.value = true
  try {
    if (dcDialog.value.isEdit) {
      await updateDataCenterApi(dcDialog.value.id, dcForm.value)
      ElMessage.success("已更新")
    } else {
      await createDataCenterApi({ ...dcForm.value })
      ElMessage.success("已创建")
    }
    dcDialog.value.visible = false
    await fetchDataCenters()
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || "操作失败")
  } finally {
    submitting.value = false
  }
}

// 机房操作
function openRoomDialog(room?: RoomInfo) {
  roomDetailDialog.value.visible = false
  roomDialog.value = { visible: true, isEdit: !!room, id: room?.id || 0 }
  if (room) {
    roomForm.value = {
      name: room.name, code: room.code, floor: room.floor || "",
      area: room.area, load_rating: room.load_rating || "",
      admin_name: room.admin_name || "", admin_phone: room.admin_phone || "",
      admin_email: room.admin_email || "", tier_level: room.tier_level || "",
      description: room.description || ""
    }
  } else {
    roomForm.value = {
      name: "", code: "", floor: "", area: undefined,
      load_rating: "", admin_name: "", admin_phone: "", admin_email: "",
      tier_level: "", description: ""
    }
  }
}

function openRoomDetailDialog() {
  if (currentRoom.value) {
    roomDetailDialog.value.visible = true
  }
}

async function submitRoom() {
  if (!roomForm.value.name || !roomForm.value.code) {
    ElMessage.warning("请填写名称和编码")
    return
  }
  submitting.value = true
  try {
    const data = { ...roomForm.value, data_center_id: selectedDataCenterId.value }
    if (data.area === undefined) delete data.area
    if (roomDialog.value.isEdit) {
      await updateRoomApi(roomDialog.value.id, data)
      ElMessage.success("已更新")
    } else {
      await createRoomApi(data)
      ElMessage.success("已创建")
    }
    roomDialog.value.visible = false
    await fetchRooms()
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || "操作失败")
  } finally {
    submitting.value = false
  }
}

// 机柜操作
function openRackDialog(rack?: RackInfo) {
  rackDialog.value = { visible: true, isEdit: !!rack, id: rack?.id || 0 }
  if (rack) {
    rackForm.value = {
      code: rack.code, name: rack.name,
      total_units: rack.total_units,
      rated_power: rack.rated_power ?? undefined,
      row_pos: rack.row_pos ?? undefined,
      col_pos: rack.col_pos ?? undefined,
      description: rack.description || ""
    }
  } else {
    rackForm.value = {
      code: "", name: "", total_units: 42,
      rated_power: undefined, row_pos: undefined, col_pos: undefined, description: ""
    }
  }
  setTimeout(() => rackFormRef.value?.clearValidate(), 0)
}

async function submitRack() {
  const valid = await rackFormRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    const data: any = {
      code: rackForm.value.code,
      name: rackForm.value.name,
      total_units: rackForm.value.total_units,
      room_id: selectedRoomId.value
    }
    if (rackForm.value.rated_power !== undefined) data.rated_power = rackForm.value.rated_power
    if (rackForm.value.row_pos !== undefined) data.row_pos = rackForm.value.row_pos
    if (rackForm.value.col_pos !== undefined) data.col_pos = rackForm.value.col_pos
    if (rackForm.value.description) data.description = rackForm.value.description

    if (rackDialog.value.isEdit) {
      await updateRackApi(rackDialog.value.id, data)
      ElMessage.success("已更新")
    } else {
      await createRackApi(data)
      ElMessage.success("已创建")
    }
    rackDialog.value.visible = false
    await fetchRacks()
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || "操作失败")
  } finally {
    submitting.value = false
  }
}

async function deleteRack(rack: RackInfo) {
  try {
    await ElMessageBox.confirm(`确定删除机柜 "${rack.code} - ${rack.name}"？`, "确认删除", { type: "warning" })
    await deleteRackApi(rack.id)
    ElMessage.success("已删除")
    await fetchRacks()
  } catch {}
}
</script>

<style scoped>
.facility-page { padding: 0; }

.page-header { margin-bottom: 16px; }
.page-title { font-size: 18px; font-weight: 600; margin: 0; }
.page-desc { font-size: 13px; color: #909399; margin: 4px 0 0; }

.selector-card { margin-bottom: 16px; border-radius: 10px; }
.selector-label { font-size: 13px; color: #606266; margin-bottom: 8px; font-weight: 500; }
.quick-actions { display: flex; gap: 8px; }
.dc-info, .room-info { font-size: 12px; color: #909399; }

.stats-row { margin-bottom: 16px; }
.stat-card { border-radius: 10px; cursor: pointer; transition: all 0.2s; }
.stat-card:hover { transform: translateY(-2px); }
.stat-item { display: flex; align-items: center; gap: 12px; }
.stat-icon-box { width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; }
.stat-info { display: flex; flex-direction: column; }
.stat-num { font-size: 20px; font-weight: 700; line-height: 1.2; }
.stat-label { font-size: 12px; color: #909399; }

.table-card { border-radius: 10px; }
.table-header { display: flex; justify-content: space-between; align-items: center; }
.header-actions { display: flex; gap: 8px; }

.rack-code { font-weight: 600; color: var(--app-primary); font-family: monospace; }
</style>
