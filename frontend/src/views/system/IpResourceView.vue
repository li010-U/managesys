<template>
  <div class="ip-resource-page">
    <div class="page-header">
      <div>
        <h3 class="page-title">IP 资源管理</h3>
        <p class="page-desc">基于设备台账的 IP 字段实时聚合：占用统计、网段分组与冲突检测</p>
      </div>
      <el-button type="primary" :icon="Warning" @click="goConflictCenter()">冲突处理中心</el-button>
      <el-button type="primary" :loading="loading" @click="fetchData">
        <el-icon><Refresh /></el-icon>刷新
      </el-button>
    </div>

    <el-row :gutter="16" class="stat-row" v-if="data">
      <el-col :span="4"><el-statistic title="设备数" :value="data.device_count" /></el-col>
      <el-col :span="4"><el-statistic title="IP记录数" :value="data.total_entries" /></el-col>
      <el-col :span="4"><el-statistic title="去重IP数" :value="data.unique_ips" /></el-col>
      <el-col :span="4"><el-statistic title="网段数" :value="data.subnets.length" /></el-col>
      <el-col :span="4">
        <el-statistic title="IP冲突" :value="data.conflict_count">
          <template #suffix><span style="font-size:14px">处</span></template>
        </el-statistic>
      </el-col>
      <el-col :span="4"><el-statistic title="IP类型" :value="Object.keys(data.role_counts).length" /></el-col>
    </el-row>

    <el-alert
      v-if="data && data.conflict_count > 0"
      type="error" :closable="false" show-icon
      class="conflict-alert"
      :title="`检测到 ${data.conflict_count} 处 IP 冲突，请及时核查处理`"
    />

    <el-card shadow="never" class="section-card">
      <h4>IP 占用分布（按类型）</h4>
      <el-row :gutter="16" v-if="data">
        <el-col :span="8" v-for="(label, role) in data.role_labels" :key="role">
          <div class="role-card">
            <span class="role-label">{{ label }}</span>
            <span class="role-count">{{ data.role_counts[role] || 0 }}</span>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-card shadow="never" class="section-card" v-if="data">
      <h4>明确冲突（同字段重复）</h4>
      <el-table :data="data.conflicts" stripe size="small" style="width:100%">
        <el-table-column label="IP 地址" width="150"><template #default="{ row }"><b>{{ row.ip }}</b></template></el-table-column>
        <el-table-column label="字段" width="120"><template #default="{ row }">{{ roleName(row.role) }}</template></el-table-column>
        <el-table-column label="涉及设备">
          <template #default="{ row }">
            <span v-for="(d, i) in row.devices" :key="i" class="dev-chip">{{ d.name }}（{{ d.asset_number }}）</span>
          </template>
        </el-table-column>

        <el-table-column label="处理" width="150" align="center">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="goConflictCenter(row)">立即处理</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="!data.conflicts.length" class="empty">无冲突，IP 分配正常</div>
    </el-card>

    <el-card shadow="never" class="section-card" v-if="data">
      <h4>网段占用情况</h4>
      <el-table :data="data.subnets" stripe size="small" style="width:100%">
        <el-table-column prop="subnet" label="网段" width="180" />
        <el-table-column prop="total" label="IP数" width="90" align="center" />
        <el-table-column prop="private" label="内网" width="90" align="center" />
        <el-table-column prop="public" label="公网" width="90" align="center" />
        <el-table-column label="所在设备" min-width="220">
          <template #default="{ row }">
            <span v-for="(it, i) in row.ips.slice(0, 8)" :key="i" class="ip-chip">{{ it.ip }} <i>({{ roleName(it.role) }})</i></span>
            <span v-if="row.ips.length > 8" class="more">+{{ row.ips.length - 8 }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'IpResources' })
import { ref, onMounted } from "vue"
import { Refresh, Warning } from "@element-plus/icons-vue"
import { useRouter } from "vue-router"
import { getIpOverviewApi, type IpOverview } from "@/api/ipResource"

const router = useRouter()
const loading = ref(false)
const data = ref<IpOverview | null>(null)

const roleName = (r: string) => (data.value?.role_labels?.[r] || r)

async function fetchData() {
  loading.value = true
  try {
    const res = await getIpOverviewApi()
    data.value = res.data
  } catch (e: any) {
    console.error("Failed to load IP resources:", e)
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)

function goConflictCenter(row?: any) {
  router.push({ path: '/system/ip-conflict-center', query: row ? { ip: row.ip } : undefined })
}
</script>

<style scoped>
.ip-resource-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-title { font-size: 20px; margin: 0 0 4px; color: #1e293b; }
.page-desc { margin: 0; color: #94a3b8; font-size: 13px; }
.stat-row { margin-bottom: 8px; }
.stat-row .el-col { background: #f8fafc; border-radius: 10px; padding: 16px; }
.conflict-alert { margin-bottom: 16px; }
.section-card { margin-bottom: 16px; }
.section-card h4 { margin: 0 0 12px; color: #334155; }
.role-card { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; background: #f8fafc; border-radius: 10px; }
.role-label { color: #64748b; font-size: 13px; }
.role-count { font-size: 22px; font-weight: 700; color: #2563eb; }
.dev-chip { display: inline-block; margin: 2px 6px 2px 0; padding: 2px 8px; background: #fef2f2; color: #dc2626; border-radius: 6px; font-size: 12px; }
.ip-chip { display: inline-block; margin: 2px 6px 2px 0; padding: 2px 8px; background: #eff6ff; color: #2563eb; border-radius: 6px; font-size: 12px; }
.ip-chip i { color: #94a3b8; font-style: normal; }
.more { color: #94a3b8; font-size: 12px; }
.empty { color: #94a3b8; padding: 12px; text-align: center; }
</style>
