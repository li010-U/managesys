<template>
  <div class="conflict-page">
    <div class="page-header">
      <h3 class="page-title">IP 冲突处理中心</h3>
      <div class="header-actions">
        <el-button :icon="Refresh" @click="fetchData" :loading="loading">重新检测</el-button>
        <el-button type="primary" :icon="Position" @click="goOverview">IP 资源总览</el-button>
      </div>
    </div>

    <el-row :gutter="12" class="stat-row" v-if="data">
      <el-col :span="6"><div class="stat-card stat-total"><div class="stat-num">{{ data.total }}</div><div class="stat-lbl">冲突总数</div></div></el-col>
      <el-col :span="6"><div class="stat-card stat-explicit"><div class="stat-num">{{ data.explicit.length }}</div><div class="stat-lbl">明确冲突</div></div></el-col>
      <el-col :span="6"><div class="stat-card stat-potential"><div class="stat-num">{{ data.potential.length }}</div><div class="stat-lbl">潜在冲突</div></div></el-col>
      <el-col :span="6"><div class="stat-card stat-done"><div class="stat-num">{{ resolvedCount }}</div><div class="stat-lbl">本会话已处理</div></div></el-col>
    </el-row>

    <el-alert v-if="data && data.total === 0" type="success" :closable="false" show-icon title="未检测到IP冲突，分配正常" class="ok-alert" />

    <el-card shadow="never" class="section-card" v-if="data && data.explicit.length">
      <template #header><div class="card-head"><strong>明确冲突（同字段重复）</strong><el-tag type="danger" size="small">{{ data.explicit.length }}</el-tag></div></template>
      <div v-for="c in data.explicit" :key="'e-'+c.role+'-'+c.ip" class="conflict-block">
        <div class="conflict-title">
          <el-tag type="danger">{{ c.ip }}</el-tag>
          <span class="role-pill">{{ roleName(c.role) }}</span>
          <span class="warn-text">同一 {{ roleName(c.role) }} 被多台设备占用</span>
        </div>
        <div class="device-grid">
          <div v-for="(d, i) in c.devices" :key="i" class="device-cell" :class="{ active: isEditing(c.ip, c.role, d) }">
            <div class="dev-head">
              <strong>{{ d.name }}</strong>
              <span class="asset">{{ d.asset_number }}</span>
            </div>
            <div class="dev-sub"><el-tag size="small" type="warning">{{ conflictIpText(c, d) }}</el-tag></div>
            <div class="dev-loc" v-if="d.racked"><el-icon><Position /></el-icon><span>{{ d.rack_name || '未知机柜' }}<template v-if="d.room_id"> · 机房{{ d.room_id }}</template></span></div>
            <div class="dev-loc unracked" v-else><el-tag size="small" type="warning" effect="dark">未挂载</el-tag><span>该设备未挂载到机柜</span></div>
            <div class="dev-actions">
              <el-button size="small" text type="primary" :icon="Position" @click="locateRack(d)">定位机柜</el-button>
              <el-button size="small" text type="primary" :icon="Edit" @click="startEdit(c, d)">改IP</el-button>
            </div>
            <div v-if="isEditing(c.ip, c.role, d)" class="inline-edit">
              <el-input v-model="editForm.newIp" placeholder="输入新IP" size="small" style="margin-bottom:8px"><template #prepend>{{ roleName(c.role) }}</template></el-input>
              <div class="edit-btns">
                <el-button size="small" type="primary" :loading="resolving" @click="submitEdit(c, d)">保存并审计</el-button>
                <el-button size="small" @click="cancelEdit()">取消</el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="section-card" v-if="data && data.potential.length">
      <template #header><div class="card-head"><strong>潜在冲突（跨字段重复）</strong><el-tag type="warning" size="small">{{ data.potential.length }}</el-tag></div></template>
      <div v-for="c in data.potential" :key="'p-'+c.ip" class="conflict-block">
        <div class="conflict-title">
          <el-tag type="warning">{{ c.ip }}</el-tag>
          <span class="warn-text">同一IP同时出现在多个字段：{{ (c.roles||[]).map(roleName).join('、') }}</span>
        </div>
        <div class="device-grid">
          <div v-for="(d,i) in (c.devices||[])" :key="i" class="device-cell">
            <div class="dev-head"><strong>{{ d.name }}</strong><span class="asset">{{ d.asset_number }}</span></div>
            <div class="dev-sub"><el-tag size="small" type="warning">{{ roleName(d.role) }}</el-tag></div>
            <div class="dev-loc" v-if="d.racked"><el-icon><Position /></el-icon><span>{{ d.rack_name || '未知机柜' }}<template v-if="d.room_id"> · 机房{{ d.room_id }}</template></span></div>
            <div class="dev-loc unracked" v-else><el-tag size="small" type="warning" effect="dark">未挂载</el-tag><span>该设备未挂载到机柜</span></div>
            <div class="dev-actions">
              <el-button size="small" text type="primary" :icon="Position" @click="locateRack(d)">定位机柜</el-button>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <el-empty v-if="data && data.total===0" description="一切正常" :image-size="80" />
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'IpConflictCenter' })
import { ref, computed, onMounted } from "vue"
import { useRouter } from "vue-router"
import { ElMessage } from "element-plus"
import { Refresh, Position, Edit } from "@element-plus/icons-vue"
import { getIpConflictsApi, resolveIpConflictApi, type IpConflicts, type ConflictDevice } from "@/api/ipResource"

const router = useRouter()
const loading = ref(false)
const resolving = ref(false)
const data = ref<IpConflicts | null>(null)
const resolvedKeys = ref<Set<string>>(new Set())
const editForm = ref<{ newIp: string }>({ newIp: "" })
const editing = ref<{ key: string; device: ConflictDevice; role: string } | null>(null)

const roleLabel: Record<string, string> = { management: "管理IP", business: "业务IP", oob: "带外IP" }
const roleName = (r?: string) => (r ? roleLabel[r] || r : "")
const resolvedCount = computed(() => resolvedKeys.value.size)

function conflictIpText(c: any, d: ConflictDevice) {
  const r = c.role || d.role
  if (r === "management") return "管理 " + c.ip
  if (r === "business") return "业务 " + c.ip
  if (r === "oob") return "带外 " + c.ip
  return c.ip
}

function isEditing(ip: string, role: string | undefined, d: ConflictDevice) {
  return editing.value && editing.value.key === editingKey(ip, role, d)
}
function editingKey(ip: string, role: string | undefined, d: ConflictDevice) {
  return ip + "|" + role + "|" + d.id
}

function locateRack(d: ConflictDevice) {
  if (!d.rack_id) { ElMessage.warning("该设备未挂载到机柜"); return }
  const q: any = { rack: String(d.rack_id) }
  if (d.room_id) q.room_id = String(d.room_id)
  router.push({ path: "/room/racks", query: q })
}

function startEdit(c: any, d: ConflictDevice) {
  editing.value = { key: editingKey(c.ip, c.role, d), device: d, role: c.role }
  editForm.value.newIp = ""
}

function cancelEdit() {
  editing.value = null
  editForm.value.newIp = ""
}

async function submitEdit(c: any, d: ConflictDevice) {
  if (!editForm.value.newIp || !editForm.value.newIp.trim()) {
    ElMessage.warning("请输入新IP")
    return
  }
  resolving.value = true
  const ed = editing.value!
  try {
    await resolveIpConflictApi({ device_id: d.id, role: ed.role, new_ip: editForm.value.newIp.trim() })
    resolvedKeys.value.add(ed.key)
    ElMessage.success("已修改 %s 的 %s 并记录审计".replace("%s", d.name).replace("%s", roleName(ed.role)))
    cancelEdit()
    fetchData()
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || "处理失败")
  } finally {
    resolving.value = false
  }
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getIpConflictsApi()
    data.value = res.data
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "加载失败")
  } finally {
    loading.value = false
  }
}

function goOverview() {
  router.push("/system/ip-resources")
}

onMounted(fetchData)
</script>

<style scoped>
.conflict-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-title { font-size: 20px; margin: 0; color: #1e293b; }
.header-actions { display: flex; gap: 8px; }
.stat-row { margin-bottom: 16px; }
.stat-card { border-radius: 12px; padding: 16px; text-align: center; color: #fff; }
.stat-total { background: linear-gradient(135deg,#64748b,#475569); }
.stat-explicit { background: linear-gradient(135deg,#ef4444,#dc2626); }
.stat-potential { background: linear-gradient(135deg,#f59e0b,#d97706); }
.stat-done { background: linear-gradient(135deg,#10b981,#059669); }
.stat-num { font-size: 30px; font-weight: 700; }
.stat-lbl { opacity: .9; font-size: 13px; }
.ok-alert { margin-bottom: 16px; }
.section-card { margin-bottom: 16px; border-radius: 12px; }
.card-head { display: flex; align-items: center; gap: 8px; }
.conflict-block { border: 1px solid #f1f5f9; border-radius: 10px; padding: 14px; margin-bottom: 14px; background: #fafbfc; }
.conflict-title { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.role-pill { background: #fef2f2; color: #dc2626; padding: 2px 10px; border-radius: 20px; font-size: 12px; }
.warn-text { color: #64748b; font-size: 13px; }
.device-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 10px; }
.device-cell { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px; }
.device-cell.active { border-color: #ef4444; box-shadow: 0 0 0 2px #fee2e2; }
.dev-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.dev-head strong { font-size: 14px; color: #1e293b; }
.asset { color: #94a3b8; font-size: 12px; }
.dev-sub { margin-bottom: 8px; }
.dev-loc { display: flex; align-items: center; gap: 4px; font-size: 12px; color: #64748b; margin-bottom: 8px; }
.dev-loc.unracked { color: #b45309; }
.dev-actions { display: flex; gap: 4px; }
.inline-edit { margin-top: 10px; padding-top: 10px; border-top: 1px dashed #e2e8f0; }
.edit-btns { display: flex; gap: 8px; }
</style>
