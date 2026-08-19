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
          <el-button :icon="Grid" @click="overviewMode ? exitOverview() : enterOverview()">{{ overviewMode ? '返回机房' : '跨机房总览' }}</el-button>
          <el-button type="warning" :icon="View" @click="go3d">3D 视图</el-button>
          <el-button :icon="Download" @click="exportCapacityCsv">导出容量</el-button>
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
    <!-- 9: 跨机房总览 -->
    <el-card v-if="overviewMode && !viewRack" shadow="never" class="overview-card">
      <div v-loading="overviewLoading" class="overview-body">
        <el-empty v-if="!overviewLoading && roomOverviewList.length === 0" description="暂无机房数据" :image-size="80" />
        <el-row :gutter="12" v-else>
          <el-col :span="12" v-for="room in roomOverviewList" :key="room.id" style="margin-bottom:12px">
            <div class="overview-room-card" @click="enterRoom(room)">
              <div class="ov-header">
                <span class="ov-name">{{ room.name }}</span>
                <span class="ov-code">{{ room.code }}</span>
                <el-tag size="small" :type="room.util >= 80 ? 'danger' : room.util >= 50 ? 'warning' : 'success'">{{ room.util }}%</el-tag>
              </div>
              <div class="ov-stats">
                <span>机柜 {{ room.rackCount }}</span>
                <span>U位 {{ room.usedU }}/{{ room.capU }}</span>
                <span>功率 {{ room.power }}kW</span>
              </div>
              <div class="ov-bar"><div class="ov-fill" :style="{width:room.util+'%',background:utilColorFor(room.util)}"></div></div>
              <div class="ov-racks" v-if="room.racks.length">
                <div v-for="rk in room.racks.slice(0, 14)" :key="rk.id" class="ov-rack" :title="rk.code" :style="{background:rackUtilColor(rk), opacity: 0.9}"></div>
                <span v-if="room.racks.length > 14" class="ov-more">+{{ room.racks.length - 14 }}</span>
              </div>
            </div>
          </el-col>
        </el-row>
      </div>
    </el-card>

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
              <el-tooltip v-if="getRackAt(r, c)!" placement="top" :show-after="200">
                <template #content>
                  <div class="rack-hover">
                    <div><b>{{ getRackAt(r, c)!.code }}</b> {{ getRackAt(r, c)!.name }}</div>
                    <div>已用U位：{{ getRackAt(r, c)!.total_units - getRackAt(r, c)!.available_units }} / {{ getRackAt(r, c)!.total_units }}</div>
                    <div>设备数：{{ getRackAt(r, c)!.device_count }} 台</div>
                    <div v-if="getRackAt(r, c)!.rated_power">额定功率：{{ getRackAt(r, c)!.rated_power }} kW</div>
                    <div :style="{color: (roomAlertMap[getRackAt(r, c)!.id]||0)>0 ? '#e74c3c':'#27ae60'}">活跃告警：{{ roomAlertMap[getRackAt(r, c)!.id] || 0 }}</div>
                    <div>利用率：{{ rackUtilPercent(getRackAt(r, c)!) }}%</div>
                  </div>
                </template>
                <div class="rack-mini-card" :class="utilClass(getRackAt(r, c)!)" @click="showDetail(getRackAt(r, c)!)">
                  <div class="rack-mini-alert" v-if="(roomAlertMap[getRackAt(r, c)!.id] || 0) > 0">
                    <el-icon :size="12"><Warning /></el-icon>{{ roomAlertMap[getRackAt(r, c)!.id] }}
                  </div>
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
              </el-tooltip>
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
          <el-input v-model="deviceSearch" placeholder="搜索设备..." :prefix-icon="Search" clearable size="small" style="width:150px" />
          <el-select v-model="deviceTypeFilter" placeholder="类型" clearable size="small" style="width:120px">
            <el-option v-for="c in deviceCategories" :key="c.key" :label="c.label" :value="c.key" />
          </el-select>
          <el-button size="small" :class="faceMode==='front'?'is-active':''" @click="faceMode='front'"><el-icon :size="13"><View /></el-icon>正面</el-button>
          <el-button size="small" :class="faceMode==='rear'?'is-active':''" @click="faceMode='rear'"><el-icon :size="13"><Odometer /></el-icon>背面</el-button>
          <el-button size="small" :icon="Download" @click="exportRackImage">导出图</el-button>
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
        <div class="us-item" v-if="rackPowerLoad > 0"><span class="us-label">功率负载</span>
          <span class="us-power-wrap">
            <span class="us-value" :style="{color:powerLoadColor(rackPowerPercent)}">{{ rackPowerLoadKw }} kW</span>
            <span v-if="viewRack!.rated_power" class="power-pct" :style="{color:powerLoadColor(rackPowerPercent)}">({{ rackPowerPercent }}%)</span>
          </span>
          <div v-if="viewRack!.rated_power" class="power-bar"><div class="power-fill" :style="{width:rackPowerPercent+'%',background:powerLoadColor(rackPowerPercent)}"></div></div>
        </div>
        <div class="us-item"><span class="us-label">设备数</span><span class="us-value" style="color:#7b1fa2">{{ filteredByType.length }}</span></div>
        <div class="us-item"><span class="us-label">最大空闲块</span><span class="us-value" style="color:#27ae60">{{ maxFreeU }}U</span></div>
        <div v-if="envOnline" class="us-item env-item">
          <span class="us-label">环境</span>
          <span class="us-value us-env">
            <el-icon :size="13" color="#e74c3c"><WarningFilled /></el-icon> 温度{{ envTemp }}°C
            <el-icon :size="13" color="#1976d2"><DataLine /></el-icon> 湿度{{ envHumidity }}%
            <span v-if="envDoor"><el-icon :size="13" color="#e67e22"><Cpu /></el-icon> 门{{ envDoor }}</span>
          </span>
        </div>
        <div class="us-item" v-if="envLoading"><span class="us-label">环境</span><el-icon class="is-loading" :size="14"><Loading /></el-icon></div>
      </div>
      <div class="uview-main">
        <div class="uview-container">
          <div class="uview-rack-face">
            <div class="rack-face-top"><div class="rack-face-logo">{{ viewRack!.code }}</div></div>
            <div class="uview-columns">
              <div v-for="(col,ci) in uSlots" :key="'ucol'+ci" class="uview-col">
                <div class="uview-col-header">列 {{ ci+1 }} <span v-if="faceMode==='rear'" class="face-tag">背面</span></div>
                <div class="uview-col-body">
                  <div v-for="(slot) in col" :key="'uslot'+slot.number"
                    class="u-slot"
                    :class="slot.occupied ? 'occupied' : 'empty'"
                    :style="{minHeight: slotHeight+'px'}"
                    @click="slot.occupied ? showDeviceDetail(slot.device) : null">
                    <div class="u-number">{{ slot.number }}</div>
                    <template v-if="faceMode==='front'">
                      <div v-if="slot.occupied"
                        class="u-device"
                        :class="{dimmed: deviceTypeFilter && slot.device.device_type_category !== deviceTypeFilter}"
                        :style="{background: deviceColor(slot.device)}"
                        :draggable="true"
                        @dragstart.stop="onDragStart(slot.device, $event)"
                        @dragend="onDragEnd"
                        @click.stop="showDeviceDetail(slot.device)">
                        <span class="u-device-status-dot" :class="'status-'+slot.device.status"></span>
                        <div class="u-device-info">
                          <span class="u-device-name">{{ slot.device.name }}</span>
                          <span class="u-device-type">{{ slot.device.device_type_name }}<span class="u-device-pw">· {{ slot.device.power_rating || '—' }}kW</span></span>
                        </div>
                        <el-tooltip :content="'资产编号: '+slot.device.asset_number" placement="right">
                          <span class="u-device-asset">{{ slot.device.asset_number.slice(-8) }}</span>
                        </el-tooltip>
                      </div>
                      <div v-else
                        class="u-empty"
                        :class="{'drop-target': dragDevice && canDropAt(slot.number), 'free-block-start': isFreeBlockStart(slot.number)}"
                        @click="promptAddDevice(slot.number)"
                        @dragover.prevent="dragOverU = slot.number"
                        @dragleave="handleDragLeave(slot.number)"
                        @drop.prevent="onDrop(slot.number)">
                        <span class="u-empty-text">{{ isFreeBlockStart(slot.number) ? '空闲块起点' : '空' }}</span>
                      </div>
                    </template>
                    <template v-else>
                      <div v-if="slot.occupied" class="u-device u-rear" :style="{background: deviceColor(slot.device)}">
                        <div class="u-rear-info">
                          <span class="u-device-name">{{ slot.device.name }}</span>
                          <span class="u-device-type">功率 {{ slot.device.power_rating || '—' }}kW</span>
                        </div>
                        <el-tooltip :content="'管理IP: '+ (slot.device.management_ip || '—')" placement="right">
                          <span class="u-device-asset">{{ (slot.device.management_ip || '—').slice(-12) }}</span>
                        </el-tooltip>
                      </div>
                      <div v-else class="u-empty"><span class="u-empty-text">空</span></div>
                    </template>
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
        <el-divider content-position="left">3D 几何参数（精确摆位，可留空自动排布）</el-divider>
        <el-row :gutter="12">
          <el-col :span="12"><el-form-item label="世界X(m)"><el-input-number v-model="form.pos_x_m" :step="0.1" :precision="1" :controls="false" style="width:100%" placeholder="如 0.6" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="世界Z(m)"><el-input-number v-model="form.pos_z_m" :step="0.1" :precision="1" :controls="false" style="width:100%" placeholder="如 1.7" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="机柜宽(m)"><el-input-number v-model="form.width_m" :min="0.2" :max="2" :step="0.1" :precision="2" style="width:100%" placeholder="缺省0.6" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="机柜深(m)"><el-input-number v-model="form.depth_m" :min="0.2" :max="2" :step="0.1" :precision="2" style="width:100%" placeholder="缺省1.0" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="朝向角(°)"><el-input-number v-model="form.facing_deg" :min="-360" :max="360" :step="15" style="width:100%" placeholder="缺省0" /></el-form-item></el-col>
        </el-row>
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
          <el-button type="info" size="small" @click="openLifecycle(deviceActionDialog.device)">变更留痕</el-button>
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

    <!-- 6: 设备变更留痕弹窗 -->
    <el-dialog v-model="lifecycleDialog.visible" :title="devicesInfoTitle" width="560px" :close-on-click-modal="false">
      <div v-loading="lifecycleLoading">
        <el-timeline v-if="lifecycleDialog.items.length">
          <el-timeline-item v-for="(item, idx) in lifecycleDialog.items" :key="idx" :timestamp="fmtTime(item.created_at)" placement="top">
            <div class="lc-row">
              <el-tag size="small" :type="lcTagType(item.action)">{{ lifecycleActionLabel(item.action) }}</el-tag>
              <span class="lc-desc">{{ item.remark || (item.to_status ? '状态 ' + (item.from_status||'-') + ' -> ' + item.to_status : '') }}</span>
            </div>
            <div class="lc-op" v-if="item.operator">操作人：{{ item.operator }}</div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无变更记录" :image-size="70" />
      </div>
      <template #footer><el-button @click="lifecycleDialog.visible=false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'Racks' })
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Edit, Delete, Loading, Monitor, DataLine, Coin, WarningFilled, Cpu, Lightning, Bottom, ArrowLeft, ArrowRight, Search, Warning, Download, Grid, View, Odometer } from '@element-plus/icons-vue'
import { getRoomsApi, getRacksApi, getAllRacksApi, createRackApi, updateRackApi, deleteRackApi, getRackEnvironmentApi } from '../../api/facility'
import { getDevicesApi, updateDeviceApi, getDeviceLifecyclesApi } from '../../api/device'
import type { RackInfo } from '../../api/facility'
import type { DeviceInfo } from '../../api/device'
import { deviceStatusType, deviceStatusLabel, toChineseOrdinal, rackUtilPercent, rackUtilColor, powerLoadColor, getRackUnitText, lifecycleActionLabel, lcTagType, utilClass, fmtTime, utilColorFor } from '../../composables/useRackUi'

const selectedRoomId = ref<number>(0)
const roomList = ref<any[]>([])
const rackList = ref<RackInfo[]>([])
const loading = ref(false)
const viewRack = ref<RackInfo | null>(null)
const rackDevices = ref<DeviceInfo[]>([])
const submitting = ref(false)
const formRef = ref<any>(null)
const dialog = ref({ visible: false, isEdit: false, id: 0 })
const form = ref<any>({ code: '', name: '', total_units: 42, rated_power: undefined, row_pos: undefined, col_pos: undefined, pos_x_m: undefined, pos_z_m: undefined, width_m: undefined, depth_m: undefined, facing_deg: undefined, description: '' })
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

// ===== 新增状态：功率/环境/类型过滤/双面/拖拽/导出/总览 =====
const rackEnv = ref<any>(null)                    // 机柜环境覆盖数据
const envLoading = ref(false)
const faceMode = ref<'front' | 'rear'>('front')   // 5: 前后双面
const deviceTypeFilter = ref('')                  // 7: 设备类型过滤
const dragDevice = ref<DeviceInfo | null>(null)   // 4: 拖拽来源设备
const dragOverU = ref<number | null>(null)        // 4: 拖拽悬停的空U
const dragTotal = ref<number>(0)                  // 4: 拖拽设备占用U数
const freeBlocks = computed<any[]>(() => computeFreeBlocks()) // 2: 连续空闲U块
const moving = ref(false)

// ===== 9: 跨机房总览 =====
const overviewMode = ref(false)
const roomOverviewList = ref<any[]>([])           // 每个机房的机柜摘要
const overviewLoading = ref(false)

// ===== 6: 变更留痕 =====
const lifecycleDialog = ref({ visible: false, device: null as any, items: [] as any[] })
const lifecycleLoading = ref(false)
const roomAlertMap = ref<Record<number, number>>({})   // 8: 机房内各机柜告警数

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

// ===== 1: 功率负载（真实设备额定功率求和）=====
const rackPowerLoad = computed(() => {
  let sum = 0
  for (const d of rackDevices.value) { sum += d.power_rating || 0 }
  return sum
})
const rackPowerLoadKw = computed(() => rackPowerLoad.value.toFixed(2))
const rackPowerPercent = computed(() => {
  const rated = viewRack.value?.rated_power
  if (!rated || rated <= 0) return 0
  return Math.min(100, Math.round(rackPowerLoad.value / rated * 100))
})
// ===== 2: 连续空闲U块计算 =====
function computeFreeBlocks() {
  const rack = viewRack.value
  if (!rack) return []
  const totalU = rack.total_units || 0
  const occupied = new Set<number>()
  for (const d of rackDevices.value) {
    if (d.start_u === undefined || d.end_u === undefined) continue
    const lo = Math.min(d.start_u, d.end_u); const hi = Math.max(d.start_u, d.end_u)
    for (let u = lo; u <= hi; u++) occupied.add(u)
  }
  const blocks: any[] = []
  let start = -1
  for (let u = 1; u <= totalU; u++) {
    if (!occupied.has(u)) { if (start < 0) start = u }
    else if (start >= 0) { blocks.push({ start, end: u - 1, size: u - start }); start = -1 }
  }
  if (start >= 0) blocks.push({ start, end: totalU, size: totalU - start + 1 })
  return blocks
}
const maxFreeU = computed(() => freeBlocks.value.reduce((m, b) => Math.max(m, b.size), 0))
function isFreeBlockStart(u: number): boolean {
  return freeBlocks.value.some(b => b.start === u)
}

// ===== 7: 设备类型过滤 =====
const filteredByType = computed(() => {
  if (!deviceTypeFilter.value) return filteredDevices.value
  return filteredDevices.value.filter(d => (d as any).device_type_category === deviceTypeFilter.value)
})

// ===== 9: 跨机房总览 — 拉取所有机房及机柜 =====
async function loadRoomOverview() {
  overviewLoading.value = true
  try {
    const [routerResp, allRacksResp]: any[] = await Promise.all([
      getRoomsApi({ page: 1, page_size: 100 }),
    ])
    const rooms = routerResp.data.items
    const racks: any[] = await getAllRacks()
    const rackByRoom: Record<number, any[]> = {}
    for (const rk of racks) { (rackByRoom[rk.room_id] = rackByRoom[rk.room_id] || []).push(rk) }
    roomOverviewList.value = rooms.map((rm: any) => {
      const rs = rackByRoom[rm.id] || []
      const usedTotal = rs.reduce((a, r) => a + (r.total_units - r.available_units), 0)
      const capTotal = rs.reduce((a, r) => a + r.total_units, 0)
      const powTotal = rs.reduce((a, r) => a + (r.rated_power || 0), 0)
      return { ...rm, racks: rs, rackCount: rs.length, usedU: usedTotal, capU: capTotal, util: capTotal ? Math.round(usedTotal / capTotal * 100) : 0, power: powTotal }
    })
  } catch { roomOverviewList.value = [] }
  finally { overviewLoading.value = false }
}
async function getAllRacks(): Promise<any[]> {
  try { const r = await getAllRacksApi(); return r.data || [] } catch { return [] }
}

// ===== 3: 机柜实时环境覆盖 =====
async function loadRackEnvironment(rackId: number) {
  envLoading.value = true
  try {
    const r = await getRackEnvironmentApi(rackId)
    rackEnv.value = r.data || null
  } catch { rackEnv.value = null }
  finally { envLoading.value = false }
}
const envTemp = computed(() => {
  const s = (rackEnv.value?.sensors || []).find((x: any) => x.sensor_type === 'temperature')
  return s ? String(s.current_value?.value ?? s.current_value?.temperature ?? s.current_value?.temp ?? '-') : '-'
})
const envHumidity = computed(() => {
  const s = (rackEnv.value?.sensors || []).find((x: any) => x.sensor_type === 'humidity')
  return s ? String(s.current_value?.value ?? s.current_value?.humidity ?? s.current_value?.humi ?? '-') : '-'
})
const envDoor = computed(() => {
  const s = (rackEnv.value?.sensors || []).find((x: any) => x.sensor_type === 'door_magnetic' || x.sensor_type === 'door')
  if (!s) return null
  const v = s.current_value?.value ?? s.current_value?.status
  return s.status === 'online' && (v === 'open' || v === '1' || v === true) ? '开' : '关'
})
const envHasAlerts = computed(() => (rackEnv.value?.active_alerts || 0) > 0)
const envOnline = computed(() => (rackEnv.value?.sensors || []).some((x: any) => x.status === 'online'))

// ===== 6: 变更留痕弹窗 =====
async function openLifecycle(device: DeviceInfo) {
  lifecycleDialog.value = { visible: true, device, items: [] }
  lifecycleLoading.value = true
  try {
    const r = await getDeviceLifecyclesApi(device.id)
    lifecycleDialog.value.items = r.data || []
  } catch { lifecycleDialog.value.items = [] }
  finally { lifecycleLoading.value = false }
}
const devicesInfoTitle = computed(() => '设备变更留痕' + (lifecycleDialog.value.device ? ' — ' + lifecycleDialog.value.device.name : ''))
// ===== 4: 拖拽上架/挪位 =====
function onDragStart(device: DeviceInfo, ev?: DragEvent) {
  dragDevice.value = device
  dragTotal.value = device.end_u && device.start_u ? Math.max(device.end_u, device.start_u) - Math.min(device.end_u, device.start_u) + 1 : 1
  if (ev?.dataTransfer) ev.dataTransfer.effectAllowed = 'move'
}
function onDragEnd() { dragDevice.value = null; dragOverU.value = null }
function canDropAt(u: number): boolean {
  if (!dragDevice.value || !viewRack.value) return false
  // 只能在机柜内重排；同一设备原位置忽略
  const size = dragTotal.value
  if (u + size - 1 > (viewRack.value.total_units || 0)) return false
  // 检查目标块是否与其它设备冲突（排除自身）
  const others = rackDevices.value.filter(d => d.id !== dragDevice.value!.id)
  for (let k = u; k < u + size; k++) {
    for (const o of others) {
      if (o.start_u !== undefined && o.end_u !== undefined) {
        const lo = Math.min(o.start_u, o.end_u); const hi = Math.max(o.start_u, o.end_u)
        if (k >= lo && k <= hi) return false
      }
    }
  }
  return true
}
function handleDragLeave(u: number) { if (dragOverU.value === u) dragOverU.value = null }
async function onDrop(u: number) {
  if (!dragDevice.value || !viewRack.value || !canDropAt(u)) { dragDevice.value = null; dragOverU.value = null; return }
  moving.value = true
  try {
    await updateDeviceApi(dragDevice.value.id, {
      rack_id: viewRack.value.id, start_u: u, end_u: u + dragTotal.value - 1, status: dragDevice.value.status === 'in_stock' ? 'mounted' : dragDevice.value.status,
    })
    ElMessage.success('已移动设备到 U' + u)
    await fetchRackDevices(viewRack.value.id)
    // 挪位后刷新环境（设备归属变化可能影响告警）
    loadRackEnvironment(viewRack.value.id)
  } catch { /* handled */ }
  finally { moving.value = false; dragDevice.value = null; dragOverU.value = null }
}

// ===== 10: 导出 =====
async function exportRackImage() {
  const rack = viewRack.value
  if (!rack) { ElMessage.warning('请先进入机柜视图'); return }
  const canvas = document.createElement('canvas')
  const cols = uSlots.value.length || 2
  const rows = Math.max(...uSlots.value.map((c: any) => c.length))
  const cellW = 90, cellH = 22, headerH = 40, pad = 12
  canvas.width = cols * cellW + pad * 2
  canvas.height = rows * cellH + headerH + pad * 2 + 30
  const ctx = canvas.getContext('2d')!
  ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.fillStyle = '#333'; ctx.font = 'bold 14px sans-serif'
  ctx.fillText(`机柜 ${rack.code} ${rack.name} (${rack.total_units}U)`, pad, 24)
  ctx.font = '11px sans-serif'
  ;(uSlots.value as any[]).forEach((col, ci) => {
    col.forEach((slot: any, ri: number) => {
      const x = pad + ci * cellW, y = headerH + pad + ri * cellH
      ctx.fillStyle = slot.occupied ? deviceColor(slot.device) : '#f5f5f5'
      ctx.fillRect(x, y, cellW - 2, cellH - 1)
      ctx.strokeStyle = '#ddd'; ctx.strokeRect(x, y, cellW - 2, cellH - 1)
      ctx.fillStyle = slot.occupied ? '#fff' : '#999'
      ctx.font = '10px sans-serif'
      if (slot.occupied && slot.firstOfMulti) ctx.fillText(String(slot.number) + ':' + (slot.device.name || '').slice(0, 6), x + 4, y + 14)
      else if (!slot.occupied) ctx.fillText(String(slot.number), x + 4, y + 14)
    })
  })
  const a = document.createElement('a')
  a.download = `rack_${rack.code}.png`
  a.href = canvas.toDataURL('image/png')
  a.click()
}
function exportCapacityCsv() {
  const csvRows: string[] = []
  csvRows.push('机柜代号,机柜名称,U位总数,已用U,空闲U,利用率,额定功率(kW)')
  for (const r of roomRacks.value) {
    const u = r.total_units - r.available_units
    csvRows.push([r.code, r.name, r.total_units, u, r.available_units, rackUtilPercent(r) + '%', r.rated_power || ''].join(','))
  }
  const blob = new Blob(['\ufeff' + csvRows.join('\n')], { type: 'text/csv;charset=utf-8' })
  const a = document.createElement('a')
  a.download = `rack_capacity_${selectedRoomId.value}.csv`
  a.href = URL.createObjectURL(blob)
  a.click()
}


async function loadRoomAlertMap(roomId: number) {
  if (!roomId) return
  try {
    const firstRack = roomRacks.value[0] || rackList.value[0]
    if (!firstRack) { roomAlertMap.value = {}; return }
    const r = await getRackEnvironmentApi(firstRack.id)
    roomAlertMap.value = r.data?.rack_alerts || {}
  } catch { roomAlertMap.value = {} }
}

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
    applyRackDeepLink()
    loadRoomAlertMap(selectedRoomId.value)
  } catch (e) {
    console.error('Failed to fetch racks:', e)
    rackList.value = []
  } finally {
    loading.value = false
  }
}

function onRoomChange() { fetchRacks() }
function applyRackDeepLink() {
  const qRack = Number(route.query.rack)
  if (!qRack) return
  const rack = rackList.value.find(r => r.id === qRack)
  if (rack) showDetail(rack)
}

function openDialog(rack?: RackInfo) {
  dialog.value = { visible: true, isEdit: !!rack, id: rack?.id || 0 }
  if (rack) {
    form.value = { code: rack.code, name: rack.name, total_units: rack.total_units, rated_power: rack.rated_power ?? undefined, row_pos: rack.row_pos ?? undefined, col_pos: rack.col_pos ?? undefined, pos_x_m: rack.pos_x_m ?? undefined, pos_z_m: rack.pos_z_m ?? undefined, width_m: rack.width_m ?? undefined, depth_m: rack.depth_m ?? undefined, facing_deg: rack.facing_deg ?? undefined, description: rack.description || '' }
  } else {
    form.value = { code: '', name: '', total_units: 42, rated_power: undefined, row_pos: undefined, col_pos: undefined, description: '' }
  }
  setTimeout(() => formRef.value?.clearValidate(), 0)
}

function openDialogAt(row: number, col: number) {
  dialog.value = { visible: true, isEdit: false, id: 0 }
  form.value = { code: '', name: '', total_units: 42, rated_power: undefined, row_pos: row, col_pos: col, pos_x_m: undefined, pos_z_m: undefined, width_m: undefined, depth_m: undefined, facing_deg: undefined, description: '' }
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
    const numFields = ['row_pos', 'col_pos', 'total_units', 'pos_x_m', 'pos_z_m', 'width_m', 'depth_m', 'facing_deg']
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
  deviceTypeFilter.value = ''
  dragDevice.value = null
  Promise.all([fetchRackDevices(rack.id), loadRackEnvironment(rack.id)])
}

async function fetchRackDevices(rackId: number) {
  try {
    const r = await getDevicesApi({ page: 1, page_size: 100, rack_id: rackId })
    rackDevices.value = r.data.items || []
  } catch {
    rackDevices.value = []
  }
}

function backToFloorplan() { viewRack.value = null; rackDevices.value = []; rackEnv.value = null }
function enterOverview() { overviewMode.value = true; loadRoomOverview() }
function go3d() { if (!selectedRoomId.value) { ElMessage.warning('请先选择机房'); return } router.push({ name: 'Rack3D', query: { room_id: selectedRoomId.value } }) }
function exitOverview() { overviewMode.value = false }
function enterRoom(room: any) { overviewMode.value = false; selectedRoomId.value = room.id; showRoomSelector.value = true; fetchRacks() }
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
  .u-device-pw { font-size: 10px; color: rgba(255,255,255,0.68); margin-left: 4px; font-weight: 500; }
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

/* ===== 8: 机柜概况悬浮卡 / 告警角标 ===== */
.rack-hover { font-size: 12px; line-height: 1.8; color: #333; }
.rack-hover b { color: var(--app-primary); }
.rack-mini-alert { position: absolute; top: -6px; right: -6px; background: #e74c3c; color: #fff; border-radius: 10px; font-size: 10px; line-height: 1; padding: 2px 5px; display: flex; align-items: center; gap: 2px; z-index: 2; box-shadow: 0 1px 4px rgba(0,0,0,0.25); }
.rack-mini-card { position: relative; }

/* ===== 9: 跨机房总览 ===== */
.overview-card { border-radius: 12px; }
.overview-body { min-height: 120px; }
.overview-room-card { background: var(--el-bg-color); border: 1px solid var(--app-border); border-radius: 12px; padding: 14px; cursor: pointer; transition: all 0.25s; }
.overview-room-card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.08); border-color: var(--app-primary); }
.ov-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.ov-name { font-size: 15px; font-weight: 700; color: var(--app-text-color); }
.ov-code { font-size: 12px; color: var(--app-text-muted); }
.ov-stats { display: flex; gap: 14px; font-size: 12px; color: var(--app-text-secondary); margin-bottom: 8px; }
.ov-bar { height: 6px; background: var(--el-fill-color-lighter); border-radius: 3px; overflow: hidden; margin-bottom: 10px; }
.ov-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
.ov-racks { display: flex; gap: 3px; flex-wrap: wrap; }
.ov-rack { width: 10px; height: 10px; border-radius: 2px; }
.ov-more { font-size: 10px; color: var(--app-text-muted); line-height: 10px; }

/* ===== 1: 功率负载条 ===== */
.us-power-wrap { display: flex; align-items: center; gap: 6px; }
.power-pct { font-size: 11px; }
.power-bar { height: 5px; background: var(--el-fill-color-lighter); border-radius: 3px; overflow: hidden; margin-top: 4px; width: 80px; }
.power-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
.env-item .us-label { align-self: flex-start; }
.us-env { display: inline-flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 12px; }

/* ===== 5: 前后双面 ===== */
.face-tag { color: #fff; background: #7b1fa2; font-size: 10px; padding: 1px 5px; border-radius: 4px; margin-left: 4px; }
.u-rear { display: flex; flex-direction: column; justify-content: center; padding: 2px 6px; }
.u-rear-info { display: flex; flex-direction: column; min-width: 0; }
.u-device.is-active { outline: 2px solid var(--app-primary); }
.uview-actions .is-active { border-color: var(--app-primary); color: var(--app-primary); }

/* ===== 7: 类型过滤置灰 ===== */
.u-device.dimmed { opacity: 0.25; }

/* ===== 4: 拖拽 ===== */
.u-device { cursor: grab; }
.u-device:active { cursor: grabbing; }
.u-empty.drop-target { background: #d1ecf1; border: 1px dashed #0d47a1; box-shadow: inset 0 0 8px rgba(13,71,161,0.15); }
.u-empty.free-block-start .u-empty-text { color: #27ae60; font-weight: 600; }

/* ===== 6: 变更留痕 ===== */
.lc-row { display: flex; align-items: center; gap: 8px; }
.lc-desc { font-size: 13px; color: var(--app-text-color); }
.lc-op { font-size: 11px; color: var(--app-text-muted); margin-top: 2px; }
</style>