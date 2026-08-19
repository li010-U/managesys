<template>
  <div class="ip-resource-page">
    <div class="page-header">
      <div>
        <h3 class="page-title">IP 资源管理</h3>
        <p class="page-desc">基于设备台账的 IP 字段实时聚合，叠加子网规划与地址台账管理</p>
      </div>
      <div class="header-actions">
        <el-button :icon="Warning" @click="goConflictCenter()">冲突处理中心</el-button>
        <el-button :icon="Download" :loading="importing" @click="handleImport">从设备导入</el-button>
        <el-button type="primary" :loading="loading" @click="fetchAll"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>
    </div>

    <el-row :gutter="16" class="stat-row" v-if="data">
      <el-col :span="4"><el-statistic title="设备数" :value="data.device_count" /></el-col>
      <el-col :span="4"><el-statistic title="IP记录数" :value="data.total_entries" /></el-col>
      <el-col :span="4"><el-statistic title="去重IP数" :value="data.unique_ips" /></el-col>
      <el-col :span="4"><el-statistic title="网段数" :value="data.subnets.length" /></el-col>
      <el-col :span="4"><el-statistic title="IP冲突" :value="data.conflict_count" /></el-col>
      <el-col :span="4"><el-statistic title="托管子网" :value="subnets.length" /></el-col>
    </el-row>

    <el-alert v-if="data && data.conflict_count > 0" type="error" :closable="false" show-icon class="conflict-alert" :title="'检测到 ' + data.conflict_count + ' 处 IP 冲突，请及时核查处理'" />

    <el-card shadow="never" class="section-card" :body-style="{ padding: 0 }">
      <template #header>
        <div class="card-head"><strong>子网规划 / 台账使用率</strong><el-button size="small" type="primary" :icon="Plus" @click="openSubnet()">新增子网</el-button></div>
      </template>
      <el-table :data="subnets" v-loading="subLoading" stripe size="small" style="width:100%">
        <el-table-column prop="name" label="子网名称" min-width="110" />
        <el-table-column prop="cidr" label="网段" min-width="130"><template #default="{ row }"><b>{{ row.cidr }}</b></template></el-table-column>
        <el-table-column prop="gateway" label="网关" min-width="120"><template #default="{ row }">{{ row.gateway || '-' }}</template></el-table-column>
        <el-table-column prop="vlan" label="VLAN" width="80"><template #default="{ row }">{{ row.vlan || '-' }}</template></el-table-column>
        <el-table-column label="容量/已用/空闲" width="170" align="center">
          <template #default="{ row }"><span>{{ row.capacity }}</span> / <span class="used-txt">{{ row.allocated + row.reserved }}</span> / <span class="free-txt">{{ row.free }}</span></template>
        </el-table-column>
        <el-table-column label="使用率" min-width="150">
          <template #default="{ row }"><el-progress :percentage="Math.min(row.usage, 100)" :stroke-width="10" :color="usageColor(row.usage)" /></template>
        </el-table-column>
        <el-table-column label="操作" width="160" align="center">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="openSubnet(row)">编辑</el-button>
            <el-button size="small" text type="danger" @click="removeSubnet(row)">删除</el-button>
            <el-button size="small" text @click="viewSubnet(row)">台账</el-button><el-button size="small" text type="success" @click="openAllocate(row)">自动分配</el-button><el-button size="small" text @click="openHistory(row)">历史</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="!subnets.length" class="empty">尚未配置托管子网，可点击“新增子网”或“从设备导入”</div>
    </el-card>

    <el-card shadow="never" class="section-card" :body-style="{ padding: 0 }">
      <template #header>
        <div class="card-head"><strong>地址台账 ({{ addrTotal }})</strong>
          <div class="head-right">
            <el-select v-model="addrFilter.subnet_id" placeholder="全部子网" clearable size="small" style="width:150px" @change="fetchAddrs"><el-option v-for="s in subnets" :key="s.id" :label="s.cidr" :value="s.id" /></el-select>
            <el-select v-model="addrFilter.status" placeholder="全部状态" clearable size="small" style="width:120px" @change="fetchAddrs"><el-option label="已分配" value="allocated" /><el-option label="预留" value="reserved" /><el-option label="空闲" value="free" /></el-select>
            <el-input v-model="addrFilter.keyword" placeholder="搜索IP/备注" clearable size="small" style="width:150px" @keyup.enter="fetchAddrs" />
            <el-button size="small" type="primary" :icon="Plus" @click="openAddr()">登记IP</el-button>
          </div>
        </div>
      </template>
      <el-table :data="addrs" v-loading="addrLoading" stripe size="small" style="width:100%">
        <el-table-column prop="address" label="IP地址" min-width="130"><template #default="{ row }"><b>{{ row.address }}</b></template></el-table-column>
        <el-table-column prop="status" label="状态" width="90" align="center"><template #default="{ row }"><el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
        <el-table-column prop="subnet" label="所属网段" min-width="130"><template #default="{ row }">{{ row.subnet || '-' }}</template></el-table-column>
        <el-table-column prop="device_name" label="占用设备" min-width="130"><template #default="{ row }">{{ row.device_name || '-' }}</template></el-table-column>
        <el-table-column prop="used_as" label="用途" width="90" align="center"><template #default="{ row }">{{ usedAsLabel(row.used_as) }}</template></el-table-column>
        <el-table-column prop="remark" label="备注" min-width="140" show-overflow-tooltip />
        <el-table-column label="操作" width="140" align="center">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="openAddr(row)">编辑</el-button>
            <el-button size="small" text type="danger" @click="removeAddr(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager" v-if="addrTotal > pageSize"><el-pagination background layout="prev, pager, next" :total="addrTotal" :page-size="pageSize" v-model:current-page="page" @current-change="fetchAddrs" /></div>
      <div v-if="!addrs.length" class="empty">暂无台账记录，点击“登记IP”或“从设备导入”</div>
    </el-card>

    <el-card shadow="never" class="section-card"><h4>IP 占用分布（按类型，来自设备台账）</h4><el-row :gutter="16" v-if="data"><el-col :span="8" v-for="(label, role) in data.role_labels" :key="role"><div class="role-card"><span class="role-label">{{ label }}</span><span class="role-count">{{ data.role_counts[role] || 0 }}</span></div></el-col></el-row></el-card>

    <el-card shadow="never" class="section-card"><h4>明确冲突（同字段重复）</h4><el-table :data="data?.conflicts || []" stripe size="small" style="width:100%"><el-table-column label="IP 地址" width="150"><template #default="{ row }"><b>{{ row.ip }}</b></template></el-table-column><el-table-column label="字段" width="120"><template #default="{ row }">{{ roleName(row.role) }}</template></el-table-column><el-table-column label="涉及设备"><template #default="{ row }"><span v-for="(d, i) in row.devices" :key="i" class="dev-chip">{{ d.name }}（{{ d.asset_number }}）</span></template></el-table-column><el-table-column label="处理" width="150" align="center"><template #default="{ row }"><el-button size="small" text type="primary" @click="goConflictCenter(row)">立即处理</el-button></template></el-table-column></el-table><div v-if="!data?.conflicts?.length" class="empty">无冲突，IP 分配正常</div></el-card>

    <el-card shadow="never" class="section-card"><h4>网段占用情况</h4><el-table :data="data?.subnets || []" stripe size="small" style="width:100%"><el-table-column prop="subnet" label="网段" width="180" /><el-table-column prop="total" label="IP数" width="90" align="center" /><el-table-column prop="private" label="内网" width="90" align="center" /><el-table-column prop="public" label="公网" width="90" align="center" /><el-table-column label="所在设备" min-width="220"><template #default="{ row }"><span v-for="(it, i) in row.ips.slice(0, 8)" :key="i" class="ip-chip">{{ it.ip }} <i>({{ roleName(it.role) }})</i></span><span v-if="row.ips.length > 8" class="more">+{{ row.ips.length - 8 }}</span></template></el-table-column></el-table></el-card>
  </div>

  <el-dialog v-model="subnetDlg.visible" :title="subnetDlg.isEdit ? '编辑子网' : '新增子网'" width="460px">
    <el-form :model="subnetDlg.form" label-width="80px">
      <el-form-item label="名称"><el-input v-model="subnetDlg.form.name" placeholder="如 办公网段" /></el-form-item>
      <el-form-item label="网段地址"><el-input v-model="subnetDlg.form.network" :disabled="subnetDlg.isEdit" placeholder="如 10.0.0.0" /></el-form-item>
      <el-form-item label="前缀"><el-input-number v-model="subnetDlg.form.prefix" :min="1" :max="32" /></el-form-item>
      <el-form-item label="网关"><el-input v-model="subnetDlg.form.gateway" placeholder="如 10.0.0.1" /></el-form-item>
      <el-form-item label="VLAN"><el-input v-model="subnetDlg.form.vlan" placeholder="如 100" /></el-form-item>
      <el-form-item label="说明"><el-input v-model="subnetDlg.form.description" type="textarea" :rows="2" /></el-form-item>
    </el-form>
    <template #footer><el-button @click="subnetDlg.visible = false">取消</el-button><el-button type="primary" :loading="subSaving" @click="saveSubnet">保存</el-button></template>
  </el-dialog>

  <el-dialog v-model="addrDlg.visible" :title="addrDlg.isEdit ? '编辑IP' : '登记IP'" width="460px">
    <el-form :model="addrDlg.form" label-width="80px">
      <el-form-item label="IP地址"><el-input v-model="addrDlg.form.address" :disabled="addrDlg.isEdit" placeholder="如 10.0.0.10" /></el-form-item>
      <el-form-item label="状态"><el-select v-model="addrDlg.form.status"><el-option label="已分配" value="allocated" /><el-option label="预留" value="reserved" /><el-option label="空闲" value="free" /></el-select></el-form-item>
      <el-form-item label="子网"><el-select v-model="addrDlg.form.subnet_id" clearable><el-option v-for="s in subnets" :key="s.id" :label="s.cidr" :value="s.id" /></el-select></el-form-item>
      <el-form-item label="备注"><el-input v-model="addrDlg.form.remark" /></el-form-item>
    </el-form>
    <template #footer><el-button @click="addrDlg.visible = false">取消</el-button><el-button type="primary" :loading="addrSaving" @click="saveAddr">保存</el-button></template>
  </el-dialog>

  <!-- 自动分配 -->
  <el-dialog v-model="allocDlg.visible" title="自动分配 IP" width="460px" :close-on-click-modal="false">
    <el-form label-width="90px">
      <el-form-item label="所属子网"><b>{{ allocDlg.subnet?.cidr }}</b></el-form-item>
      <el-form-item label="用途">
        <el-select v-model="allocDlg.role" style="width:100%">
          <el-option label="管理IP" value="management" />
          <el-option label="业务IP" value="business" />
          <el-option label="带外IP" value="oob" />
        </el-select>
      </el-form-item>
      <el-form-item label="偏好地址">
        <el-input v-model="allocDlg.preferred" placeholder="可选，若空闲则优先选它" />
      </el-form-item>
      <el-form-item label="挂载设备ID">
        <el-input-number v-model="allocDlg.deviceId" :min="1" style="width:100%" placeholder="可选" />
      </el-form-item>
      <el-alert type="info" :closable="false" show-icon title="会自动跳过网络/广播/网关地址，并检测是否已被他设备占用" />
    </el-form>
    <template #footer>
      <el-button @click="allocDlg.visible = false">取消</el-button>
      <el-button type="primary" :loading="allocDlg.saving" @click="doAllocate">分配</el-button>
    </template>
  </el-dialog>

  <!-- IP 变更历史 -->
  <el-dialog v-model="histDlg.visible" title="IP 变更历史" width="760px">
    <el-table :data="histDlg.items" v-loading="histDlg.loading" size="small" stripe max-height="420">
      <el-table-column prop="address" label="IP 地址" width="130" />
      <el-table-column label="变更字段" width="100">
        <template #default="{ row }">{{ historyLabel(row.field_changed) }}</template>
      </el-table-column>
      <el-table-column prop="from_value" label="变更前" show-overflow-tooltip />
      <el-table-column prop="to_value" label="变更后" show-overflow-tooltip />
      <el-table-column prop="operator" label="操作人" width="100" />
      <el-table-column prop="source" label="来源" width="110" />
      <el-table-column prop="created_at" label="时间" width="170">
        <template #default="{ row }">{{ row.created_at ? new Date(row.created_at).toLocaleString('zh-CN') : '-' }}</template>
      </el-table-column>
    </el-table>
    <template #footer><el-button @click="histDlg.visible = false">关闭</el-button></template>
  </el-dialog>
</template>

<script setup lang="ts">
defineOptions({ name: 'IpResources' })
import { ref, reactive, onMounted } from "vue"
import { Refresh, Warning, Download, Plus } from "@element-plus/icons-vue"
import { useRouter } from "vue-router"
import { ElMessage, ElMessageBox } from "element-plus"
import { getIpOverviewApi, type IpOverview } from "@/api/ipResource"
import {
  getIpSubnetsApi, createIpSubnetApi, updateIpSubnetApi, deleteIpSubnetApi,
  getIpRegistryAddressesApi, saveIpRegistryAddressApi, deleteIpRegistryAddressApi, importDeviceIpsApi,
  allocateIpApi, getIpHistoryApi,
  listVlansApi, createVlanApi, updateVlanApi, deleteVlanApi,
  exportSubnetsApi, exportAddressesApi, downloadCsvBlob,
  type IpSubnet, type IpRegistryAddress, type IpAllocateResult, type IpHistoryEntry, type IpVlan,
} from "@/api/ipRegistry"

const router = useRouter()
const loading = ref(false)
const data = ref<IpOverview | null>(null)

// 子网
const subnets = ref<IpSubnet[]>([])
const subLoading = ref(false)
const subSaving = ref(false)
const importing = ref(false)

// 地址台账
const addrs = ref<IpRegistryAddress[]>([])
const addrLoading = ref(false)
const addrSaving = ref(false)
const addrTotal = ref(0)
const page = ref(1)
const pageSize = ref(20)
const addrFilter = reactive({ subnet_id: undefined as number | undefined, status: undefined as string | undefined, keyword: '' })

const roleName = (r: string) => (data.value?.role_labels?.[r] || r)
const statusLabel = (s: string) => ({ allocated: '已分配', reserved: '预留', free: '空闲' } as any)[s] || s
const statusType = (s: string) => ({ allocated: 'success', reserved: 'warning', free: 'info' } as any)[s] || 'info'
const usedAsLabel = (u?: string) => ({ management: '管理IP', business: '业务IP', oob: '带外IP' } as any)[u || ''] || u || '-'
const usageColor = (p: number) => p >= 90 ? '#ef4444' : p >= 60 ? '#f59e0b' : '#10b981'

async function fetchOverview() {
  loading.value = true
  try { const res = await getIpOverviewApi(); data.value = res.data }
  catch (e) { console.error('Failed to load IP overview:', e) }
  finally { loading.value = false }
}

async function fetchSubnets() {
  subLoading.value = true
  try { const res = await getIpSubnetsApi(); subnets.value = res.data }
  catch (e) { console.error('Failed to load subnets:', e) }
  finally { subLoading.value = false }
}

async function fetchAddrs() {
  addrLoading.value = true
  try {
    const res = await getIpRegistryAddressesApi({ subnet_id: addrFilter.subnet_id, status: addrFilter.status, keyword: addrFilter.keyword || undefined, page: page.value, page_size: pageSize.value })
    addrs.value = res.data.items
    addrTotal.value = res.data.total
  } catch (e) { console.error('Failed to load addresses:', e) }
  finally { addrLoading.value = false }
}

async function fetchAll() { await Promise.all([fetchOverview(), fetchSubnets(), fetchAddrs()]) }

// 子网弹窗
const subnetDlg = reactive({ visible: false, isEdit: false, form: {} as any })
let subnetEditId = 0 as number
function openSubnet(row?: IpSubnet) {
  subnetDlg.isEdit = !!row
  subnetEditId = row?.id || 0
  subnetDlg.form = row ? { name: row.name, network: row.network, prefix: row.prefix, gateway: row.gateway || '', vlan: row.vlan || '', description: row.description || '' } : { name: '', network: '', prefix: 24, gateway: '', vlan: '', description: '' }
  subnetDlg.visible = true
}
async function saveSubnet() {
  const f = subnetDlg.form
  if (!f.name || !f.network) { ElMessage.warning('请填写名称与网段'); return }
  subSaving.value = true
  try {
    if (subnetDlg.isEdit) {
      await updateIpSubnetApi(subnetEditId, { name: f.name, gateway: f.gateway, vlan: f.vlan, description: f.description })
    } else {
      await createIpSubnetApi({ name: f.name, network: f.network, prefix: f.prefix, gateway: f.gateway, vlan: f.vlan, description: f.description })
    }
    ElMessage.success('保存成功')
    subnetDlg.visible = false
    await Promise.all([fetchSubnets(), fetchAddrs()])
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '保存失败') }
  finally { subSaving.value = false }
}
async function removeSubnet(row: IpSubnet) {
  try { await ElMessageBox.confirm('删除子网将同时删除其台账地址，是否继续？', '删除子网', { type: 'warning' }) } catch { return }
  try { await deleteIpSubnetApi(row.id); ElMessage.success('删除成功'); await Promise.all([fetchSubnets(), fetchAddrs()]) }
  catch (e: any) { ElMessage.error(e?.response?.data?.detail || '删除失败') }
}
async function viewSubnet(row: IpSubnet) {
  addrFilter.subnet_id = row.id; page.value = 1; await fetchAddrs()
}

// 地址弹窗
const addrDlg = reactive({ visible: false, isEdit: false, form: {} as any })
function openAddr(row?: IpRegistryAddress) {
  addrDlg.isEdit = !!row
  addrDlg.form = row ? { address: row.address, status: row.status, subnet_id: row.subnet_id, remark: row.remark || '' } : { address: '', status: 'allocated', subnet_id: addrFilter.subnet_id, remark: '' }
  addrDlg.visible = true
}
async function saveAddr() {
  const f = addrDlg.form
  if (!f.address) { ElMessage.warning('请填写IP地址'); return }
  addrSaving.value = true
  try {
    await saveIpRegistryAddressApi({ address: f.address, status: f.status, subnet_id: f.subnet_id || null, remark: f.remark })
    ElMessage.success('保存成功')
    addrDlg.visible = false
    await Promise.all([fetchAddrs(), fetchSubnets()])
  } catch (e: any) { ElMessage.error(e?.response?.data?.detail || '保存失败') }
  finally { addrSaving.value = false }
}
async function removeAddr(row: IpRegistryAddress) {
  try { await ElMessageBox.confirm('确认删除该台账地址？', '删除', { type: 'warning' }) } catch { return }
  try { await deleteIpRegistryAddressApi(row.id); ElMessage.success('删除成功'); await Promise.all([fetchAddrs(), fetchSubnets()]) }
  catch (e: any) { ElMessage.error(e?.response?.data?.detail || '删除失败') }
}

const allocDlg = reactive({ visible: false, subnet: null as any, deviceId: undefined as number | undefined, role: 'management', preferred: '', saving: false })
function openAllocate(row: IpSubnet) {
  allocDlg.subnet = row
  allocDlg.deviceId = undefined
  allocDlg.role = 'management'
  allocDlg.preferred = ''
  allocDlg.visible = true
}
async function doAllocate() {
  allocDlg.saving = true
  try {
    const r = await allocateIpApi({
      subnet_id: allocDlg.subnet.id,
      device_id: allocDlg.deviceId || null,
      used_as: allocDlg.role,
      preferred: allocDlg.preferred || undefined,
    })
    ElMessage.success('已分配 ' + r.data.address)
    allocDlg.visible = false
    await Promise.all([fetchAddrs(), fetchSubnets()])
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '分配失败')
  } finally { allocDlg.saving = false }
}

const histDlg = reactive({ visible: false, address: '', items: [] as IpHistoryEntry[], total: 0, loading: false })
async function openHistory(row: IpSubnet) {
  histDlg.address = row.cidr
  histDlg.visible = true
  await loadHistory()
}
async function loadHistory() {
  histDlg.loading = true
  try {
    const r = await getIpHistoryApi({ page: 1, page_size: 100 })
    histDlg.items = r.data.items || []
    histDlg.total = r.data.total || 0
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载历史失败')
  } finally { histDlg.loading = false }
}
function historyLabel(f: string): string {
  return { status: '状态', device: '归属设备', used_as: '用途', remark: '备注' }[f] || f
}

async function handleImport() {
  importing.value = true
  try { const res = await importDeviceIpsApi(); ElMessage.success('导入完成：新增 ' + res.data.added + '，跳过 ' + res.data.skipped); await Promise.all([fetchAddrs(), fetchSubnets()]) }
  catch (e: any) { ElMessage.error(e?.response?.data?.detail || '导入失败') }
  finally { importing.value = false }
}

onMounted(fetchAll)

function goConflictCenter(row?: any) {
  router.push({ path: '/system/ip-conflict-center', query: row ? { ip: row.ip } : undefined })
}
</script>

<style scoped>
.ip-resource-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.header-actions { display: flex; gap: 8px; }
.page-title { font-size: 20px; margin: 0 0 4px; color: #1e293b; }
.page-desc { margin: 0; color: #94a3b8; font-size: 13px; }
.stat-row { margin-bottom: 8px; }
.stat-row .el-col { background: #f8fafc; border-radius: 10px; padding: 16px; }
.conflict-alert { margin-bottom: 16px; }
.section-card { margin-bottom: 16px; }
.section-card h4 { margin: 0 0 12px; color: #334155; }
.card-head { display: flex; justify-content: space-between; align-items: center; }
.head-right { display: flex; gap: 8px; }
.role-card { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; background: #f8fafc; border-radius: 10px; }
.role-label { color: #64748b; font-size: 13px; }
.role-count { font-size: 22px; font-weight: 700; color: #2563eb; }
.dev-chip { display: inline-block; margin: 2px 6px 2px 0; padding: 2px 8px; background: #fef2f2; color: #dc2626; border-radius: 6px; font-size: 12px; }
.ip-chip { display: inline-block; margin: 2px 6px 2px 0; padding: 2px 8px; background: #eff6ff; color: #2563eb; border-radius: 6px; font-size: 12px; }
.ip-chip i { color: #94a3b8; font-style: normal; }
.more { color: #94a3b8; font-size: 12px; }
.empty { color: #94a3b8; padding: 12px; text-align: center; }
.pager { padding: 10px; display: flex; justify-content: flex-end; }
.used-txt { color: #ef4444; font-weight: 600; }
.free-txt { color: #10b981; font-weight: 600; }
</style>
