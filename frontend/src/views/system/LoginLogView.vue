<template>
  <div class="login-log-page">
    <div class="page-header">
      <div>
        <h3 class="page-title">登录日志</h3>
        <p class="page-desc">记录所有用户登录行为，包括来源 IP、归属分类及异常登录识别</p>
      </div>
      <el-button type="primary" :loading="loading" @click="fetchLogs">
        <el-icon><Refresh /></el-icon>刷新
      </el-button>
    </div>

    <el-card class="search-card" :body-style="{ padding: '16px 20px' }">
      <el-row :gutter="16" align="middle">
        <el-col :span="6">
          <el-input v-model="keyword" placeholder="搜索用户名/IP..." clearable @keyup.enter="applyKeyword">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </el-col>
        <el-col :span="4">
          <el-select v-model="status" placeholder="登录状态" clearable @change="applyKeyword">
            <el-option label="成功" value="success" />
            <el-option label="失败" value="fail" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="anomalyFilter" placeholder="异常过滤" clearable @change="applyKeyword">
            <el-option label="疑似爆破" value="suspicious" />
            <el-option label="公网登录" value="public" />
          </el-select>
        </el-col>
        <el-col :span="6">
          <span class="summary">今日登录 <b>{{ todayCount }}</b> 次 · 失败 <b>{{ failCount }}</b> 次</span>
        </el-col>
        <el-col :span="4" style="text-align:right">
          <el-button @click="resetFilters"><el-icon><RefreshLeft /></el-icon>重置</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-card :body-style="{ padding: 0 }" class="table-card">
      <el-table :data="displayed" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column prop="username" label="用户名" width="130">
          <template #default="{ row }"><el-tag size="small" type="info">{{ row.username }}</el-tag></template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.login_status === 'success' ? 'success' : 'danger'" size="small">
              {{ row.login_status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ip_address" label="IP地址" width="170">
          <template #default="{ row }">
            <span>{{ row.ip_address || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="归属" width="170">
          <template #default="{ row }">
            <el-tag v-if="row.location" size="small" :type="locationType(row.location)">{{ row.location }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="异常标记" width="210">
          <template #default="{ row }">
            <template v-if="row.anomaly && row.anomaly.length">
              <el-tag v-for="a in row.anomaly" :key="a" size="small" type="danger" effect="plain" class="anomaly-tag">{{ a }}</el-tag>
            </template>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="fail_reason" label="失败原因" min-width="160" show-overflow-tooltip />
        <el-table-column prop="created_at" label="登录时间" width="180">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="filtered.length"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'LoginLogs' })
import { ref, computed, onMounted } from "vue"
import { Search, Refresh, RefreshLeft } from "@element-plus/icons-vue"
import { getLoginLogsApi } from "@/api/auth"
import type { LoginLogItem } from "@/api/auth"

const loading = ref(false)
const logs = ref<LoginLogItem[]>([])
const keyword = ref("")
const status = ref("")
const anomalyFilter = ref("")
const page = ref(1)
const pageSize = ref(20)

const locationType = (loc: string) => {
  if (loc.includes("内网") || loc.includes("回环") || loc.includes("链路") || loc.includes("保留")) return "info"
  if (loc.includes("公网")) return "warning"
  return "info"
}

const formatDate = (d?: string) => (d ? new Date(d).toLocaleString("zh-CN") : "-")

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  const st = status.value
  const af = anomalyFilter.value
  return logs.value.filter((l) => {
    if (st && l.login_status !== st) return false
    if (kw && !((l.username || "") + " " + (l.ip_address || "")).toLowerCase().includes(kw)) return false
    if (af === "suspicious" && !(l.anomaly || []).includes("疑似爆破")) return false
    if (af === "public" && !(l.anomaly || []).includes("公网登录")) return false
    return true
  })
})

const displayed = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filtered.value.slice(start, start + pageSize.value)
})

const todayCount = computed(() => {
  const today = new Date().toDateString()
  return logs.value.filter((l) => new Date(l.created_at).toDateString() === today).length
})
const failCount = computed(() => logs.value.filter((l) => l.login_status === "fail").length)

function applyKeyword() { page.value = 1 }
function resetFilters() {
  keyword.value = ""; status.value = ""; anomalyFilter.value = ""; page.value = 1
}

async function fetchLogs() {
  loading.value = true
  try {
    const res = await getLoginLogsApi()
    logs.value = (res.data || []).slice()
  } catch (e: any) {
    console.error("Failed to fetch login logs:", e)
  } finally {
    loading.value = false
  }
}

onMounted(fetchLogs)
</script>

<style scoped>
.login-log-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-title { font-size: 20px; margin: 0 0 4px; color: #1e293b; }
.page-desc { margin: 0; color: #94a3b8; font-size: 13px; }
.search-card { margin-bottom: 16px; }
.summary { color: #64748b; font-size: 13px; }
.summary b { color: #2563eb; }
.table-card { padding: 0; }
.anomaly-tag { margin-right: 4px; }
.pagination-wrap { display: flex; justify-content: flex-end; padding: 14px 20px; }
</style>
