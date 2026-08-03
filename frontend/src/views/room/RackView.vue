<template>
  <div class="rack-page">
    <div class="page-header">
      <div>
        <h3 class="page-title">机房视图</h3>
        <p class="page-desc">机房平面图与机柜U位可视化 — 直观展示设备布局与空间利用率</p>
      </div>
    </div>
    <el-card shadow="never" class="toolbar-card">
      <div class="toolbar-bar">
        <div class="toolbar-left">
          <span class="label-text" v-if="showRoomSelector">当前机房：</span>
          <el-select v-if="showRoomSelector" v-model="selectedRoomId" placeholder="选择机房" @change="onRoomChange" style="width:200px">
            <el-option v-for="r in roomList" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
          <span v-else class="room-badge">{{ roomList[0]?.name }}</span>
          <div class="stat-badge"><span class="stat-label">机柜总数</span><span class="stat-value">{{ rackList.length }}</span></div>
          <div class="stat-badge"><span class="stat-label">平均U位利用率</span><span class="stat-value" :style="{color:avgUtilColor}">{{ avgUtilization }}%</span></div>
          <div class="util-legend">
            <span class="legend-item"><span class="dot dot-green"></span>&lt;50%</span>
            <span class="legend-item"><span class="dot dot-yellow"></span>50-80%</span>
            <span class="legend-item"><span class="dot dot-red"></span>&gt;80%</span>
          </div>
        </div>
        <div class="toolbar-right">
          <el-button type="primary" :icon="Plus" @click="openDialog()">新增机柜</el-button>
          <el-button :icon="Refresh" @click="fetchRacks">刷新</el-button>
        </div>
      </div>
    </el-card>
    <el-row :gutter="12" class="stats-row" v-if="rackList.length > 0 && !viewRack">
      <el-col :span="6">
        <div class="mini-stat">
          <div class="mini-stat-icon" style="background:linear-gradient(135deg,#e8f5e9,#c8e6c9)">
            <el-icon :size="20" color="#27ae60"><Monitor /></el-icon>
          </div>
          <div class="mini-stat-body">
            <span class="mini-stat-val">{{ rackList.length }}</span>
            <span class="mini-stat-lbl">机柜总数</span>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="mini-stat">
          <div class="mini-stat-icon" style="background:linear-gradient(135deg,#e3f2fd,#bbdefb)">
            <el-icon :size="20" color="#1976d2"><DataLine /></el-icon>
          </div>
          <div class="mini-stat-body">
            <span class="mini-stat-val" :style="{color:avgUtilColor}">{{ avgUtilization }}%</span>
            <span class="mini-stat-lbl">平均利用率</span>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="mini-stat">
          <div class="mini-stat-icon" style="background:linear-gradient(135deg,#fef3e2,#ffe0b2)">
            <el-icon :size="20" color="#e67e22"><Coin /></el-icon>
          </div>
          <div class="mini-stat-body">
            <span class="mini-stat-val">{{ totalRatedPower }} kW</span>
            <span class="mini-stat-lbl">额定功率合计</span>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="mini-stat">
          <div class="mini-stat-icon" style="background:linear-gradient(135deg,#fce4ec,#f8bbd0)">
            <el-icon :size="20" color="#e74c3c"><WarningFilled /></el-icon>
          </div>
          <div class="mini-stat-body">
            <span class="mini-stat-val">{{ highUtilCount }}</span>
            <span class="mini-stat-lbl">高利用率(&gt;80%)</span>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 平面图视图 - 行列网格 -->
    <el-card v-if="!viewRack" shadow="never" class="floorplan-card">
      <div v-if="loading" class="loading-overlay"><el-icon class="is-loading" :size="32"><Loading /></el-icon></div>
      <div v-if="rackList.length===0 && !loading" class="empty-plan">
        <el-empty description="暂无机柜，请点击「新增机柜」添加" :image-size="80" />
      </div>
      <div v-else class="floorplan-wrapper">
        <!-- 行列控制栏 -->
        <div class="grid-controls">
          <div class="grid-controls-left">
            <el-input-number v-model="gridRows" :min="1" :max="20" size="small" controls-position="right" style="width:120px" />
            <span class="ctrl-label">行</span>
            <el-input-number v-model="gridCols" :min="1" :max="20" size="small" controls-position="right" style="width:120px" />
            <span class="ctrl-label">列</span>
            <el-button size="small" type="primary" plain @click="applyGridSize">应用</el-button>
          </div>
          <div class="grid-controls-right">
            <span class="rack-count-hint">{{ filteredRacks.length }} 个机柜</span>
            <el-input v-model="rackSearch" placeholder="搜索..." :prefix-icon="Search" clearable size="small" style="width:160px" />
          </div>
        </div>
        <!-- 机柜网格 -->
        <div class="rack-grid-container">
          <!-- 列标签行 -->
          <div class="grid-header">
            <div class="grid-corner-cell">排\列</div>
            <div v-for="c in gridCols" :key="'ch'+c" class="grid-col-header">
              第{{ c }}列
            </div>
          </div>
          <!-- 行数据 -->
          <div v-for="r in gridRows" :key="'row'+r" class="grid-row">
            <div class="grid-row-label">{{ toChineseOrdinal(r) }}排</div>
            <div
              v-for="c in gridCols"
              :key="'cell'+r+'-'+c"
              class="grid-cell"
            >
              <div v-if="getRackAt(r, c)!" class="rack-mini-card" :class="utilClass(getRackAt(r, c)!)" @click="showDetail(getRackAt(r, c)!)">
                <div class="rack-mini-status" :style="{background: rackUtilColor(getRackAt(r, c)!)}"></div>
                <div class="rack-mini-body">
                  <div class="rack-mini-code">{{ getRackAt(r, c)!.code }}</div>
                  <div class="rack-mini-name">{{ getRackAt(r, c)!.name }}</div>
                  <div class="rack-mini-bar"><div class="rack-mini-fill" :style="{width:rackUtilPercent(getRackAt(r, c)!)+'%',background:rackUtilColor(getRackAt(r, c)!)}"></div></div>
                  <div class="rack-mini-info">
                    <span>{{ getRackUnitText(getRackAt(r, c)!) }}</span>
                    <span v-if="getRackAt(r, c)!.rated_power">{{ getRackAt(r, c)!.rated_power }}kW</span>
                  </div>
                  <div class="rack-mini-tags">
                    <el-tag size="small" :color="rackUtilColor(getRackAt(r, c)!)" style="color:#fff;border:none" effect="dark">{{ rackUtilPercent(getRackAt(r, c)!) }}%</el-tag>
                    <el-tag size="small" type="info" effect="plain">{{ getRackAt(r, c)!.total_units }}U</el-tag>
                  </div>
                  <div class="rack-mini-actions" @click.stop>
                    <el-button :icon="Edit" size="small" text circle @click.stop="editRack(getRackAt(r, c)!)" />
                    <el-button :icon="Delete" size="small" text circle type="danger" @click.stop="deleteRack(getRackAt(r, c)!)" />
                  </div>
                </div>
              </div>
              <div v-else class="cell-empty" @click="openDialogAt(r, c)">
                <el-icon :size="22"><Plus /></el-icon>
                <span>添加机柜</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 机柜U位详情视图 -->
    <el-card v-else shadow="never" class="uview-card">
      <div class="uview-topbar">
        <el-button size="small" @click="backToFloorplan"><el-icon :size="14"><ArrowLeft /></el-icon> 返回</el-button>
        <div class="uview-title">
          <strong>{{ viewRack!.code }}</strong>
          <span class="uview-subtitle">{{ viewRack!.name }}</span>
          <el-tag size="small" class="uview-room-tag">{{ viewRack!.room_name }}</el-tag>
          <el-tag size="small" type="info" v-if="viewRack!.row_pos">第{{ viewRack!.row_pos }}排</el-tag>
          <el-tag size="small" type="info" v-if="viewRack!.col_pos">第{{ viewRack!.col_pos }}列</el-tag>
        </div>
        <div class="uview-rack-nav">
          <el-button :icon="ArrowLeft" size="small" text :disabled="currentRackIndex <= 0" @click="navRack('prev')" />
          <span class="rack-nav-info">{{ currentRackIndex + 1 }} / {{ roomRacks.length }}</span>
          <el-button :icon="ArrowRight" size="small" text :disabled="currentRackIndex >= roomRacks.length - 1" @click="navRack('next')" />
        </div>
        <div class="uview-actions">
          <el-input v-model="deviceSearch" placeholder="搜索设备..." :prefix-icon="Search" clearable size="small" style="width:160px" />
          <el-button size="small" :icon="Plus" @click="showMountDialog()">上架</el-button>
          <el-button size="small" :icon="Edit" @click="editRack(viewRack)">编辑</el-button>
          <el-button size="small" :icon="Delete" type="danger" @click="deleteRack(viewRack)">删除</el-button>
        </div>
      </div>
      <div class="uview-summary">
        <div class="us-item"><span class="us-label">总U位数</span><span class="us-value">{{ viewRack!.total_units }}</span></div>
        <div class="us-item"><span class="us-label">已使用</span><span class="us-value" style="color:#1976d2">{{ viewRack!.total_units - viewRack!.available_units }}</span></div>
        <div class="us-item"><span class="us-label">空闲</span><span class="us-value" style="color:#27ae60">{{ viewRack!.available_units }}</span></div>
        <div class="us-item"><span class="us-label">利用率</span><span class="us-value" :style="{color:rackUtilColor(viewRack)}">{{ rackUtilPercent(viewRack) }}%</span></div>
        <div class="us-item" v-if="viewRack!.rated_power"><span class="us-label">额定功率</span><span class="us-value" style="color:#e67e22">{{ viewRack.rated_power }} kW</span></div>
        <div class="us-item" v-if="totalPower"><span class="us-label">估算功率</span><span class="us-value" style="color:#e67e22">{{ totalPower }} kW</span></div>
        <div class="us-item"><span class="us-label">设备数</span><span class="us-value" style="color:#7b1fa2">{{ filteredDevices.length }}</span></div>
      </div>
      <div class="uview-main">
        <div class="uview-container">
          <div class="uview-rack-face">
            <div class="rack-face-top"><div class="rack-face-logo">{{ viewRack!.code }}</div></div>
            <div class="uview-columns">
              <div v-for="(col,ci) in uSlots" :key="'ucol'+ci" class="uview-col">
                <div class="uview-col-header">列 {{ ci+1 }}</div>
                <div class="uview-col-body">
                  <div v-for="(slot) in col" :key="'uslot'+slot.number" class="u-slot" :class="slot.occupied ? 'occupied' : 'empty'" :style="{minHeight: slotHeight+'px'}" @click="slot.occupied ? showDeviceDetail(slot.device) : null">
                    <div class="u-number">{{ slot.number }}</div>
                    <div v-if="slot.occupied" class="u-device" :style="{background: deviceColor(slot.device)}">
                      <span class="u-device-status-dot" :class="'status-'+slot.device.status"></span>
                      <div class="u-device-info">
                        <span class="u-device-name">{{ slot.device.name }}</span>
                        <span class="u-device-type">{{ slot.device.device_type_name }}</span>
                      </div>
                      <el-tooltip :content="'资产编号: '+slot.device.asset_number" placement="right">
                        <span class="u-device-asset">{{ slot.device.asset_number.slice(-8) }}</span>
                      </el-tooltip>
                    </div>
                    <div v-else class="u-empty" @click="promptAddDevice(slot.number)"><span class="u-empty-text">空</span></div>
                  </div>
                </div>
              </div>
            </div>
            <div class="rack-face-bottom"><div class="rack-face-base"><el-icon :size="16"><Bottom /></el-icon> BASE</div></div>
          </div>
        </div>
        <div class="uview-legend">
          <div class="legend-title">设备图例</div>
          <div class="legend-list">
            <div class="legend-row" v-for="cat in deviceCategories" :key="cat.key"><span class="legend-color" :style="{background:cat.color}"></span><span class="legend-cat">{{ cat.label }}</span></div>
          </div>
          <el-divider style="margin:8px 0" />
          <div class="legend-title">状态指示</div>
          <div class="legend-list">
            <div class="legend-row"><span class="legend-dot dot-running"></span><span class="legend-cat">运行中</span></div>
            <div class="legend-row"><span class="legend-dot dot-mounted"></span><span class="legend-cat">已上架</span></div>
            <div class="legend-row"><span class="legend-dot dot-offline"></span><span class="legend-cat">离线</span></div>
          </div>
          <el-divider style="margin:8px 0" />
          <div class="legend-title">操作</div>
          <div class="legend-list">
            <div class="legend-row legend-action" @click="promptAddDevice()"><el-icon :size="14"><Plus /></el-icon> 添加设备</div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 新增/编辑机柜弹窗 -->
    <el-dialog v-model="dialog.visible" :title="dialog.isEdit?'编辑机柜':'新增机柜'" width="480px" :close-on-click-modal="false" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" size="small">
        <el-form-item label="机柜代号" prop="code"><el-input v-model="form.code" placeholder="如 A01" /></el-form-item>
        <el-form-item label="机柜名称" prop="name"><el-input v-model="form.name" placeholder="如 网络机柜01" /></el-form-item>
        <el-row :gutter="12">
          <el-col :span="12"><el-form-item label="所在行" prop="row_pos"><el-input-number v-model="form.row_pos" :min="1" :max="100" style="width:100%" controls-position="right" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="所在列" prop="col_pos"><el-input-number v-model="form.col_pos" :min="1" :max="100" style="width:100%" controls-position="right" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12"><el-form-item label="总U位数" prop="total_units"><el-input-number v-model="form.total_units" :min="1" :max="100" style="width:100%" controls-position="right" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="额定功率(kW)"><el-input-number v-model="form.rated_power" :min="0" :max="100" :step="0.5" :precision="1" style="width:100%" controls-position="right" /></el-form-item></el-col>
        </el-row>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="2" placeholder="可选备注" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible=false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">{{ dialog.isEdit?'保存':'创建' }}</el-button>
      </template>
    </el-dialog>

    <!-- 设备详情弹窗 -->
    <el-dialog v-model="deviceDialog.visible" title="设备详情" width="420px" :close-on-click-modal="false">
      <div class="device-detail-card" v-if="deviceDialog.device">
        <div class="dd-header"><span class="dd-device-name">{{ deviceDialog.device.name }}</span><el-tag :type="deviceStatusType(deviceDialog.device.status)" size="small">{{ deviceStatusLabel(deviceDialog.device.status) }}</el-tag></div>
        <el-descriptions :column="2" size="small" border>
          <el-descriptions-item label="资产编号">{{ deviceDialog.device.asset_number }}</el-descriptions-item>
          <el-descriptions-item label="设备类型">{{ deviceDialog.device.device_type_name }}</el-descriptions-item>
          <el-descriptions-item label="品牌">{{ deviceDialog.device.brand || '-' }}</el-descriptions-item>
          <el-descriptions-item label="型号">{{ deviceDialog.device.model || '-' }}</el-descriptions-item>
          <el-descriptions-item label="U位">{{ deviceDialog.device.start_u }}U - {{ deviceDialog.device.end_u }}U</el-descriptions-item>
          <el-descriptions-item label="管理IP">{{ deviceDialog.device.management_ip || '-' }}</el-descriptions-item>
        </el-descriptions>
      </div>
      <template #footer><el-button @click="deviceDialog.visible=false">关闭</el-button></template>
    </el-dialog>

    <!-- 设备操作弹窗 -->
    <el-dialog v-model="deviceActionDialog.visible" title="设备操作" width="420px" :close-on-click-modal="false">
      <div class="device-detail-card" v-if="deviceActionDialog.device">
        <div class="dd-header">
          <span class="dd-device-name">{{ deviceActionDialog.device.name }}</span>
          <el-tag :type="deviceStatusType(deviceActionDialog.device.status)" size="small">{{ deviceStatusLabel(deviceActionDialog.device.status) }}</el-tag>
        </div>
        <el-descriptions :column="2" size="small" border>
          <el-descriptions-item label="资产编号">{{ deviceActionDialog.device.asset_number }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ deviceActionDialog.device.device_type_name }}</el-descriptions-item>
          <el-descriptions-item label="品牌">{{ deviceActionDialog.device.brand || '-' }}</el-descriptions-item>
          <el-descriptions-item label="型号">{{ deviceActionDialog.device.model || '-' }}</el-descriptions-item>
          <el-descriptions-item label="U位">{{ deviceActionDialog.device.start_u }}U - {{ deviceActionDialog.device.end_u }}U</el-descriptions-item>
          <el-descriptions-item label="管理IP">{{ deviceActionDialog.device.management_ip || '-' }}</el-descriptions-item>
        </el-descriptions>
        <el-divider />
        <div class="dd-actions">
          <el-button type="primary" :icon="Edit" size="small" @click="goEditDevice(deviceActionDialog.device)">编辑设备</el-button>
          <el-button type="warning" :icon="Bottom" size="small" :loading="unmounting" @click="unmountDevice(deviceActionDialog.device)">下架设备</el-button>
        </div>
      </div>
      <template #footer><el-button @click="deviceActionDialog.visible=false">关闭</el-button></template>
    </el-dialog>

    <!-- 上架设备对话框 -->
    <el-dialog v-model="mountDialog.visible" title="上架设备到机柜" width="550px" :close-on-click-modal="false">
      <div v-if="mountDialog.visible">
        <el-alert :title="'目标位置：' + (viewRack?.code || '') + ' 机柜'" type="info" :closable="false" show-icon style="margin-bottom:16px" />
        <el-form :model="mountForm" label-width="100px" size="small">
          <el-form-item label="选择设备">
            <el-select v-model="mountForm.deviceId" filterable placeholder="选择在库设备" style="width:100%">
              <el-option v-for="d in availableDevices" :key="d.id" :label="d.name+' ('+d.asset_number+')'" :value="d.id">
                <span>{{ d.name }}</span>
                <span style="color:var(--app-text-muted);font-size:11px;margin-left:8px">{{ d.device_type_name }}</span>
              </el-option>
            </el-select>
          </el-form-item>
          <el-row :gutter="12">
            <el-col :span="12"><el-form-item label="起始U位"><el-input-number v-model="mountForm.startU" :min="1" :max="viewRack?.total_units||42" style="width:100%" controls-position="right" /></el-form-item></el-col>
            <el-col :span="12"><el-form-item label="占用U数"><el-input-number v-model="mountForm.uHeight" :min="1" :max="viewRack?.total_units||42" style="width:100%" controls-position="right" /></el-form-item></el-col>
          </el-row>
          <el-form-item label="上架备注"><el-input v-model="mountForm.remark" placeholder="可选" /></el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="mountDialog.visible=false">取消</el-button>
        <el-button type="primary" :loading="mounting" @click="confirmMount">确认上架</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Edit, Delete, Loading, Monitor, DataLine, Coin, WarningFilled, Cpu, Lightning, Bottom, ArrowLeft, ArrowRight, Search } from '@element-plus/icons-vue'
import { getRoomsApi, getRacksApi, createRackApi, updateRackApi, deleteRackApi } from '../../api/facility'
import { getDevicesApi, updateDeviceApi } from '../../api/device'
import type { RackInfo } from '../../api/facility'
import type { DeviceInfo } from '../../api/device'

const selectedRoomId = ref<number>(0)
const roomList = ref<any[]>([])
const rackList = ref<RackInfo[]>([])
const loading = ref(false)
const viewRack = ref<RackInfo | null>(null)
const rackDevices = ref<DeviceInfo[]>([])
const submitting = ref(false)
const formRef = ref<any>(null)
const dialog = ref({ visible: false, isEdit: false, id: 0 })
const form = ref<any>({ code: '', name: '', total_units: 42, rated_power: undefined, row_pos: undefined, col_pos: undefined, description: '' })
const deviceDialog = ref({ visible: false, device: null as DeviceInfo | null })
const showRoomSelector = ref(true)
const rackSearch = ref('')
const deviceSearch = ref('')
const deviceActionDialog = ref({ visible: false, device: null as DeviceInfo | null })
const unmounting = ref(false)
const mountDialog = ref({ visible: false, rackId: 0, targetU: 1 })
const mountForm = ref({ deviceId: null as number | null, startU: 1, uHeight: 1, remark: '' })
const mounting = ref(false)
const availableDevices = ref<DeviceInfo[]>([])

// 网格行列数（用户可调）
const gridRows = ref(2)
const gridCols = ref(4)

const categoryColors: Record<string, string> = {
  server: '#2196F3', network: '#4CAF50', storage: '#9C27B0', security: '#FF9800', power: '#F44336',
}
const deviceCategories = [
  { key: 'server', label: '服务器', color: '#2196F3' },
  { key: 'network', label: '网络设备', color: '#4CAF50' },
  { key: 'storage', label: '存储设备', color: '#9C27B0' },
  { key: 'security', label: '安全设备', color: '#FF9800' },
  { key: 'power', label: '电源设备', color: '#F44336' },
]

function deviceColor(d: DeviceInfo): string {
  return categoryColors[(d as any).device_type_category || d.device_type_name] || '#607D8B'
}
function deviceStatusType(s: string): string {
  if (s === 'running') return 'success'
  if (s === 'mounted' || s === 'in_stock') return 'info'
  return 'danger'
}
function deviceStatusLabel(s: string): string {
  const map: Record<string, string> = { running: '运行中', mounted: '已上架', in_stock: '在库', offline: '离线', scrapped: '已报废' }
  return map[s] || s
}

const slotHeight = 36
const uSlots = computed(() => {
  const rack = viewRack.value
  if (!rack) return []
  const totalU = rack.total_units || 42
  const devices = rackDevices.value || []
  const columnsPerFace = 2
  const colSize = Math.ceil(totalU / columnsPerFace)
  const columns: any[][] = []
  for (let ci = 0; ci < columnsPerFace; ci++) {
    const colSlots: any[] = []
    const startU = Math.min(totalU, totalU - ci * colSize)
    const endU = Math.max(1, totalU - (ci + 1) * colSize + 1)
    for (let u = startU; u >= endU; u--) {
      const dev = devices.find(d => {
        if (d.start_u === undefined || d.end_u === undefined) return false
        return u >= Math.min(d.start_u, d.end_u) && u <= Math.max(d.start_u, d.end_u)
      })
      if (dev) {
                const devLo = Math.min(dev.start_u!, dev.end_u!)
        const devHi = Math.max(dev.start_u!, dev.end_u!)
        const isFirst = u === devLo
        colSlots.push({ number: u, displayNumber: isFirst ? String(u) : '', occupied: true, device: dev, merged: !isFirst, firstOfMulti: isFirst, deviceHeight: devHi - devLo + 1 })
      } else {
        colSlots.push({ number: u, displayNumber: String(u), occupied: false, device: null, merged: false, firstOfMulti: true, deviceHeight: 1 })
      }
    }
    columns.push(colSlots)
  }
  return columns
})

const avgUtilization = computed(() => {
  if (rackList.value.length === 0) return 0
  const sum = rackList.value.reduce((a, r) => a + (r.total_units - r.available_units) / r.total_units * 100, 0)
  return Math.round(sum / rackList.value.length)
})
const avgUtilColor = computed(() => { const v = avgUtilization.value; return v >= 80 ? '#e74c3c' : v >= 50 ? '#e67e22' : '#27ae60' })
const totalRatedPower = computed(() => rackList.value.reduce((a, r) => a + (r.rated_power || 0), 0).toFixed(1))
const highUtilCount = computed(() => rackList.value.filter(r => { const u = r.total_units > 0 ? (r.total_units - r.available_units) / r.total_units * 100 : 0; return u >= 80 }).length)

function rackUtilPercent(rack: RackInfo): number {
  if (!rack.total_units) return 0
  return Math.round((rack.total_units - rack.available_units) / rack.total_units * 100)
}
function rackUtilColor(rack: RackInfo): string { const u = rackUtilPercent(rack); return u >= 80 ? '#e74c3c' : u >= 50 ? '#e67e22' : '#27ae60' }
function utilClass(rack: RackInfo): string { const u = rackUtilPercent(rack); return u >= 80 ? 'rack-util-high' : u >= 50 ? 'rack-util-mid' : 'rack-util-low' }
function getRackUnitText(rack: RackInfo): string { return (rack.total_units - rack.available_units) + '/' + rack.total_units + 'U' }

const filteredDevices = computed(() => {
  if (!deviceSearch.value) return rackDevices.value
  const q = deviceSearch.value.toLowerCase()
  return rackDevices.value.filter(d => d.name.toLowerCase().includes(q) || d.asset_number.toLowerCase().includes(q))
})

const filteredRacks = computed(() => {
  if (!rackSearch.value) return rackList.value
  const q = rackSearch.value.toLowerCase()
  return rackList.value.filter(r => r.code.toLowerCase().includes(q) || r.name.toLowerCase().includes(q))
})

const roomRacks = computed(() => {
  return [...rackList.value].sort((a, b) => (a.row_pos || 0) - (b.row_pos || 0) || (a.col_pos || 0) - (b.col_pos || 0))
})

const currentRackIndex = computed(() => {
  return roomRacks.value.findIndex(r => r.id === viewRack.value!.id)
})

function navRack(dir: 'prev' | 'next') {
  const idx = currentRackIndex.value
  const target = dir === 'prev' ? roomRacks.value[idx - 1] : roomRacks.value[idx + 1]
  if (target) showDetail(target)
}

const totalPower = computed(() => {
  let total = 0
  for (const _d of rackDevices.value) { total += 0.3 }
  return total.toFixed(1)
})

// 根据已有机柜自动计算网格大小
function autoFitGrid() {
  const maxR = Math.max(1, ...rackList.value.map(r => r.row_pos || 1))
  const maxC = Math.max(1, ...rackList.value.map(r => r.col_pos || 1))
  // 留一点余量
  gridRows.value = Math.max(maxR, 2)
  gridCols.value = Math.max(maxC, 4)
}

function getRackAt(row: number, col: number): RackInfo | null {
  return rackList.value.find(r => r.row_pos === row && r.col_pos === col) || null
}

function applyGridSize() {
  // just let user control it
}

function toChineseOrdinal(n: number): string {
  const cn = ['〇','一','二','三','四','五','六','七','八','九','十','十一','十二','十三','十四','十五','十六','十七','十八','十九','二十']
  return cn[n] || String(n)
}

const route = useRoute()
const router = useRouter()

onMounted(async () => { await fetchRooms() })

async function fetchRooms() {
  try {
    const r = await getRoomsApi({ page: 1, page_size: 100 })
    roomList.value = r.data.items
    if (roomList.value.length > 0) {
      const qRoomId = Number(route.query.room_id)
      if (qRoomId && roomList.value.some(rm => rm.id === qRoomId)) {
        selectedRoomId.value = qRoomId
      } else {
        selectedRoomId.value = roomList.value[0].id
      }
      showRoomSelector.value = roomList.value.length > 1
    }
    await fetchRacks()
  } catch (e) {
    console.error('Failed to fetch rooms:', e)
  }
}

async function fetchRacks() {
  if (!selectedRoomId.value) return
  loading.value = true
  try {
    const r = await getRacksApi({ page: 1, page_size: 100, room_id: selectedRoomId.value })
    rackList.value = r.data.items
    autoFitGrid()
  } catch (e) {
    console.error('Failed to fetch racks:', e)
    rackList.value = []
  } finally {
    loading.value = false
  }
}

function onRoomChange() { fetchRacks() }

function openDialog(rack?: RackInfo) {
  dialog.value = { visible: true, isEdit: !!rack, id: rack?.id || 0 }
  if (rack) {
    form.value = { code: rack.code, name: rack.name, total_units: rack.total_units, rated_power: rack.rated_power ?? undefined, row_pos: rack.row_pos ?? undefined, col_pos: rack.col_pos ?? undefined, description: rack.description || '' }
  } else {
    form.value = { code: '', name: '', total_units: 42, rated_power: undefined, row_pos: undefined, col_pos: undefined, description: '' }
  }
  setTimeout(() => formRef.value?.clearValidate(), 0)
}

function openDialogAt(row: number, col: number) {
  dialog.value = { visible: true, isEdit: false, id: 0 }
  form.value = { code: '', name: '', total_units: 42, rated_power: undefined, row_pos: row, col_pos: col, description: '' }
  setTimeout(() => formRef.value?.clearValidate(), 0)
}

function editRack(rack: RackInfo) { openDialog(rack) }

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  if (!selectedRoomId.value) { ElMessage.warning('请先选择机房'); return }
  submitting.value = true
  try {
    const raw = { ...form.value, room_id: selectedRoomId.value }
    const numFields = ['row_pos', 'col_pos', 'total_units']
    const data: any = {}
    for (const [k, v] of Object.entries(raw)) {
      if (k === 'rated_power') { data[k] = (v === '' || v === undefined || v === null) ? null : Number(v); continue }
      if (v === '' || v === undefined || v === null) { data[k] = null }
      else if (numFields.includes(k)) { data[k] = Number(v) }
      else { data[k] = v }
    }
    if (dialog.value.isEdit) {
      await updateRackApi(dialog.value.id, data)
      ElMessage.success('已更新')
    } else {
      await createRackApi(data)
      ElMessage.success('已创建')
    }
    dialog.value.visible = false
    await fetchRacks()
  } catch {
    // error handled by interceptor
  } finally {
    submitting.value = false
  }
}

async function deleteRack(rack: RackInfo) {
  try {
    await ElMessageBox.confirm('确定删除机柜「' + rack.code + ' - ' + rack.name + '」？', '确认删除', { type: 'warning' })
    await deleteRackApi(rack.id)
    ElMessage.success('已删除')
    if (viewRack.value?.id === rack.id) backToFloorplan()
    await fetchRacks()
  } catch {
    // cancelled or error
  }
}

async function showDetail(rack: RackInfo) {
  viewRack.value = rack
  await fetchRackDevices(rack.id)
}

async function fetchRackDevices(rackId: number) {
  try {
    const r = await getDevicesApi({ page: 1, page_size: 100, rack_id: rackId })
    rackDevices.value = r.data.items || []
  } catch {
    rackDevices.value = []
  }
}

function backToFloorplan() { viewRack.value = null; rackDevices.value = [] }
function showDeviceDetail(device: DeviceInfo) { deviceDialog.value = { visible: true, device } }
function promptAddDevice(uPosition?: number) { ElMessage.info(uPosition ? '请前往「设备台账」在 U' + uPosition + ' 位置添加设备' : '请前往「设备台账」添加设备') }

async function showMountDialog() {
  mountDialog.value.visible = true
  mountDialog.value.rackId = viewRack.value?.id || 0
  try {
    const r = await getDevicesApi({ page: 1, page_size: 100, status: 'in_stock' })
    availableDevices.value = r.data.items || []
  } catch { availableDevices.value = [] }
}

async function confirmMount() {
  if (!mountForm.value.deviceId || !mountForm.value.startU || !mountForm.value.uHeight || !viewRack.value) { ElMessage.warning('请完整填写上架信息'); return }
  mounting.value = true
  try {
    await updateDeviceApi(mountForm.value.deviceId, { rack_id: viewRack.value.id, start_u: mountForm.value.startU, end_u: mountForm.value.startU + mountForm.value.uHeight - 1, status: 'mounted' })
    ElMessage.success('设备上架成功')
    mountDialog.value.visible = false
    if (viewRack.value) await fetchRackDevices(viewRack.value.id)
  } catch { /* handled by interceptor */ } finally { mounting.value = false }
}

function goEditDevice(device: DeviceInfo) {
  deviceActionDialog.value.visible = false
  router.push({ name: 'DeviceList', query: { edit_id: String(device.id) } })
}

async function unmountDevice(device: DeviceInfo) {
  unmounting.value = true
  try {
    await updateDeviceApi(device.id, { rack_id: null, start_u: null, end_u: null, status: 'in_stock' })
    ElMessage.success('设备已下架')
    deviceActionDialog.value.visible = false
    if (viewRack.value) await fetchRackDevices(viewRack.value.id)
  } catch { /* handled by interceptor */ } finally { unmounting.value = false }
}

const rules: Record<string, any> = {
  code: [{ required: true, message: '请输入机柜代号（如 A01）', trigger: 'blur' }],
  name: [{ required: true, message: '请输入机柜名称', trigger: 'blur' }],
}
</script>

<style scoped>
.page-header { margin-bottom: 16px; }
.page-title { font-size: 20px; font-weight: 700; margin: 0; background: linear-gradient(135deg, #1a73e8, #0d47a1); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.page-desc { font-size: 13px; color: var(--app-text-muted); margin: 4px 0 0; }
.toolbar-card { margin-bottom: 12px; border-radius: 12px; }
.toolbar-bar { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
.toolbar-left, .toolbar-right { display: flex; align-items: center; gap: 8px; }
.label-text { font-size: 14px; color: var(--app-text-secondary); white-space: nowrap; }
.room-badge { font-size: 14px; font-weight: 600; color: var(--app-primary); padding: 0 8px; }
.stat-badge { display: flex; flex-direction: column; align-items: center; padding: 0 12px; border-right: 1px solid var(--app-border); }
.stat-badge:last-child { border-right: none; }
.stat-label { font-size: 11px; color: var(--app-text-muted); line-height: 1; }
.stat-value { font-size: 16px; font-weight: 700; line-height: 1.4; font-family: 'SFMono-Regular', Consolas, monospace; }
.util-legend { display: flex; gap: 10px; margin-left: 8px; font-size: 11px; color: var(--app-text-muted); }
.legend-item { display: flex; align-items: center; gap: 3px; }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dot-green { background: #27ae60; }
.dot-yellow { background: #e67e22; }
.dot-red { background: #e74c3c; }
.stats-row { margin-bottom: 12px; }
.mini-stat { display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: var(--el-bg-color); border-radius: 10px; border: 1px solid var(--app-border); transition: all 0.3s; }
.mini-stat:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,0.06); }
.mini-stat-icon { width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.mini-stat-body { display: flex; flex-direction: column; }
.mini-stat-val { font-size: 18px; font-weight: 700; line-height: 1.2; font-family: 'SFMono-Regular', Consolas, monospace; }
.mini-stat-lbl { font-size: 11px; color: var(--app-text-muted); }
.floorplan-card { border-radius: 12px; min-height: 300px; position: relative; }
.loading-overlay { display: flex; align-items: center; justify-content: center; min-height: 200px; }
.empty-plan { display: flex; align-items: center; justify-content: center; min-height: 200px; }

.floorplan-wrapper { display: flex; flex-direction: column; gap: 12px; }

/* 行列控制栏 */
.grid-controls {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; background: var(--app-bg-secondary,#f5f7fa); border-radius: 8px;
}
.grid-controls-left { display: flex; align-items: center; gap: 8px; }
.grid-controls-right { display: flex; align-items: center; gap: 10px; }
.ctrl-label { font-size: 13px; color: var(--app-text-secondary); }
.rack-count-hint { font-size: 13px; color: var(--app-text-muted); white-space: nowrap; }

/* 机柜网格 */
.rack-grid-container { overflow-x: auto; }
.grid-header { display: flex; border-bottom: 2px solid var(--app-border); background: var(--app-bg-secondary,#f5f7fa); }
.grid-corner-cell { width: 80px; min-width: 80px; padding: 8px 4px; text-align: center; font-size: 12px; font-weight: 600; color: var(--app-text-muted); border-right: 1px solid var(--app-border); }
.grid-col-header { flex: 1; min-width: 160px; padding: 8px 4px; text-align: center; font-size: 12px; font-weight: 600; color: var(--app-text-secondary); border-right: 1px solid var(--app-border); }
.grid-col-header:last-child { border-right: none; }

.grid-row { display: flex; border-bottom: 1px solid var(--app-border); }
.grid-row:last-child { border-bottom: none; }
.grid-row-label { width: 80px; min-width: 80px; padding: 12px 4px; display: flex; align-items: flex-start; justify-content: center; font-size: 13px; font-weight: 600; color: var(--app-text-secondary); border-right: 1px solid var(--app-border); }

.grid-cell { flex: 1; min-width: 160px; border-right: 1px solid var(--app-border); transition: background 0.15s; }
.grid-cell:last-child { border-right: none; }
.grid-cell:hover { background: rgba(26,115,232,0.03); }

.rack-mini-card {
  border-radius: 0; cursor: pointer; position: relative; overflow: hidden; border-left: 3px solid;
  transition: all 0.25s;
}
.rack-mini-card:hover { background: var(--el-fill-color-light); }
.rack-mini-card.rack-util-low { border-left-color: #81c784; }
.rack-mini-card.rack-util-mid { border-left-color: #ffb74d; }
.rack-mini-card.rack-util-high { border-left-color: #ef5350; }

.rack-mini-status { height: 3px; width: 100%; }
.rack-mini-body { padding: 8px 10px; }
.rack-mini-code { font-weight: 700; font-size: 14px; color: #303133; font-family: 'SFMono-Regular', Consolas, monospace; margin-bottom: 2px; }
.rack-mini-name { font-size: 11px; color: #909399; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 6px; }
.rack-mini-bar { height: 4px; background: #f0f2f5; border-radius: 2px; overflow: hidden; margin-bottom: 4px; }
.rack-mini-fill { height: 100%; border-radius: 2px; transition: width 0.5s; }
.rack-mini-info { display: flex; gap: 8px; font-size: 11px; color: #909399; margin-bottom: 6px; }
.rack-mini-tags { display: flex; gap: 4px; flex-wrap: wrap; }
.rack-mini-actions { display: flex; gap: 2px; margin-top: 6px; opacity: 0; transition: opacity 0.2s; }
.rack-mini-card:hover .rack-mini-actions { opacity: 1; }

.cell-empty {
  cursor: pointer; display: flex; flex-direction: column; align-items: center;
  justify-content: center; min-height: 120px; color: var(--el-text-color-placeholder);
  gap: 4px; font-size: 11px; transition: all 0.2s;
}
.cell-empty:hover { color: var(--app-primary); background: rgba(26,115,232,0.04); }

/* 机柜U位视图 */
.uview-card { border-radius: 12px; }
.uview-topbar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.uview-title { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.uview-title strong { font-size: 18px; font-family: 'SFMono-Regular', Consolas, monospace; }
.uview-subtitle { font-size: 14px; color: var(--app-text-muted); }
.uview-room-tag { font-size: 12px; }
.uview-rack-nav { display: flex; align-items: center; gap: 4px; }
.rack-nav-info { font-size: 12px; color: var(--app-text-muted); font-family: 'SFMono-Regular', Consolas, monospace; white-space: nowrap; }
.uview-actions { display: flex; align-items: center; gap: 8px; margin-left: auto; }
.uview-summary { display: flex; flex-wrap: wrap; gap: 16px; padding: 12px 16px; background: var(--app-bg-secondary,#f5f7fa); border-radius: 10px; margin-bottom: 16px; }
.us-item { display: flex; flex-direction: column; gap: 2px; }
.us-label { font-size: 11px; color: var(--app-text-muted); }
.us-value { font-size: 16px; font-weight: 700; font-family: 'SFMono-Regular', Consolas, monospace; }
.uview-main { display: flex; gap: 16px; }
.uview-container { flex: 1; overflow-x: auto; }
.uview-rack-face { display: flex; flex-direction: column; max-width: 500px; border: 2px solid #37474f; border-radius: 6px; overflow: hidden; }
.rack-face-top { background: #37474f; padding: 6px 16px; text-align: center; }
.rack-face-logo { color: #90a4ae; font-size: 12px; font-weight: 700; font-family: 'SFMono-Regular', Consolas, monospace; }
.uview-columns { display: flex; gap: 0; }
.uview-col { flex: 1; min-width: 150px; border-right: 2px solid #b0bec5; }
.uview-col:last-child { border-right: none; }
.uview-col-header { text-align: center; font-size: 11px; color: #78909c; padding: 4px; background: #cfd8dc; font-weight: 600; border-bottom: 1px solid #b0bec5; }
.uview-col-body { display: flex; flex-direction: column; }
.u-slot { display: flex; align-items: stretch; min-height: 36px; border-bottom: 1px solid #cfd8dc; position: relative; transition: background 0.2s; }
.u-slot:last-child { border-bottom: none; }
.u-slot.occupied { background: rgba(33,150,243,0.04); }
.u-slot.empty { background: transparent; cursor: pointer; }
.u-slot.empty:hover { background: rgba(33,150,243,0.05); }
.u-number { width: 36px; font-size: 11px; color: #78909c; text-align: center; flex-shrink: 0; display: flex; align-items: center; justify-content: center; border-right: 1px solid #cfd8dc; font-family: 'SFMono-Regular', Consolas, monospace; font-weight: 600; background: rgba(0,0,0,0.02); }
.u-slot.occupied .u-number { color: var(--app-primary); }
.u-device { flex: 1; margin: 2px 4px; border-radius: 4px; display: flex; align-items: center; padding: 0 8px; cursor: pointer; position: relative; transition: all 0.25s; min-height: 32px; }
.u-device:hover { transform: translateX(4px); box-shadow: 0 4px 16px rgba(0,0,0,0.25); z-index: 2; }
.u-device-status-dot { width: 7px; height: 7px; border-radius: 50%; margin-right: 6px; flex-shrink: 0; }
.u-device-status-dot.status-running { background: #4caf50; box-shadow: 0 0 4px #4caf50; animation: pulseGreen 2s infinite; }
.u-device-status-dot.status-mounted { background: #2196f3; box-shadow: 0 0 4px #2196f3; }
.u-device-status-dot.status-offline { background: #f44336; }
.u-device-status-dot.status-in_stock { background: #9e9e9e; }
@keyframes pulseGreen { 0%,100% { opacity: 0.8; } 50% { opacity: 1; transform: scale(1.2); } }
.u-device-info { display: flex; flex-direction: column; gap: 1px; overflow: hidden; flex: 1; }
.u-device-name { font-size: 12px; color: #fff; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.u-device-type { font-size: 10px; color: rgba(255,255,255,0.8); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.u-device-asset { font-size: 9px; color: rgba(255,255,255,0.6); flex-shrink: 0; font-family: 'SFMono-Regular', Consolas, monospace; }
.u-empty { flex: 1; margin: 2px 4px; border: 1px dashed #cfd8dc; border-radius: 4px; min-height: 32px; display: flex; align-items: center; justify-content: center; transition: all 0.2s; }
.u-slot.empty:hover .u-empty { border-color: var(--app-primary); background: rgba(33,150,243,0.05); }
.u-empty-text { font-size: 11px; color: #b0bec5; }
.rack-face-bottom { background: #37474f; padding: 6px 16px; text-align: center; }
.rack-face-base { color: #90a4ae; font-size: 11px; display: flex; align-items: center; justify-content: center; gap: 4px; font-family: 'SFMono-Regular', Consolas, monospace; }
.uview-legend { min-width: 130px; padding: 12px; background: var(--app-bg-secondary,#f5f7fa); border-radius: 10px; align-self: flex-start; }
.legend-title { font-size: 12px; font-weight: 600; color: var(--app-text-secondary); margin-bottom: 6px; }
.legend-list { display: flex; flex-direction: column; gap: 4px; }
.legend-row { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--app-text-secondary); }
.legend-color { width: 12px; height: 12px; border-radius: 3px; flex-shrink: 0; }
.legend-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.dot-running { background: #4caf50; }
.dot-mounted { background: #2196f3; }
.dot-offline { background: #f44336; }
.legend-action { cursor: pointer; padding: 4px 6px; border-radius: 4px; transition: background 0.2s; }
.legend-action:hover { background: rgba(33,150,243,0.08); color: var(--app-primary); }
.dd-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.dd-device-name { font-size: 16px; font-weight: 700; }
.dd-actions { display: flex; gap: 8px; }
</style>