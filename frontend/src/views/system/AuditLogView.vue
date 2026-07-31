<template>
  <div class="audit-log-page">
    <div class="page-header">
      <div>
        <h3 class="page-title">审计日志</h3>
        <p class="page-desc">记录系统所有用户的操作行为，用于安全审计与问题追踪</p>
      </div>
    </div>

    <!-- 搜索筛选 -->
    <el-card class="search-card" :body-style="{ padding: '16px 20px' }">
      <el-row :gutter="16" align="middle">
        <el-col :span="5">
          <el-input v-model="filters.keyword" placeholder="搜索操作人/详情..." clearable @clear="fetchLogs" @keyup.enter="fetchLogs">
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
        <el-col :span="4">
          <el-select v-model="filters.action" placeholder="操作类型" clearable @change="fetchLogs">
            <el-option label="登录" value="login" />
            <el-option label="登出" value="logout" />
            <el-option label="创建" value="create" />
            <el-option label="更新" value="update" />
            <el-option label="删除" value="delete" />
            <el-option label="导出" value="export" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="filters.target_type" placeholder="对象类型" clearable @change="fetchLogs">
            <el-option label="用户" value="user" />
            <el-option label="角色" value="role" />
            <el-option label="设备" value="device" />
            <el-option label="设备类型" value="device_type" />
            <el-option label="机房" value="room" />
            <el-option label="机柜" value="rack" />
            <el-option label="系统" value="system" />
            <el-option label="告警" value="alert" />
          </el-select>
        </el-col>
        <el-col :span="8">
          <el-date-picker
            v-model="dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm:ss"
            @change="handleDateChange"
            style="width: 100%"
          />
        </el-col>
        <el-col :span="3" style="text-align: right">
          <el-button @click="resetFilters">
            <el-icon><Refresh /></el-icon>重置
          </el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 日志列表 -->
    <el-card :body-style="{ padding: 0 }" class="table-card">
      <el-table :data="logs" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column prop="username" label="操作人" width="120">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.username }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getActionType(row.action)" size="small">
              {{ getActionLabel(row.action) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="对象类型" width="110" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.target_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="target_id" label="对象ID" width="80" align="center" />
        <el-table-column prop="detail" label="操作详情" min-width="280" show-overflow-tooltip />
        <el-table-column prop="ip_address" label="IP地址" width="130" />
        <el-table-column prop="created_at" label="操作时间" width="170">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchLogs"
          @current-change="fetchLogs"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { Search, Refresh } from "@element-plus/icons-vue";
import { getAuditLogsApi } from "@/api/auditLog";
import type { AuditLogResponse, AuditLogQuery } from "@/api/auditLog";

const loading = ref(false);
const logs = ref<AuditLogResponse[]>([]);
const page = ref(1);
const pageSize = ref(20);
const total = ref(0);
const dateRange = ref<[string, string] | null>(null);

const filters = reactive({
  keyword: "",
  action: "",
  target_type: "",
  start_date: "",
  end_date: "",
});

async function fetchLogs() {
  loading.value = true;
  try {
    const params: AuditLogQuery = {
      page: page.value,
      page_size: pageSize.value,
      keyword: filters.keyword || undefined,
      action: filters.action || undefined,
      target_type: filters.target_type || undefined,
      start_date: filters.start_date || undefined,
      end_date: filters.end_date || undefined,
    };
    const res = await getAuditLogsApi(params);
    logs.value = res.data.items;
    total.value = res.data.total;
  } catch (err) {
    console.error("Failed to fetch audit logs:", err);
  } finally {
    loading.value = false;
  }
}

function resetFilters() {
  filters.keyword = "";
  filters.action = "";
  filters.target_type = "";
  filters.start_date = "";
  filters.end_date = "";
  dateRange.value = null;
  page.value = 1;
  fetchLogs();
}

function handleDateChange(val: [string, string] | null) {
  if (val) {
    filters.start_date = val[0];
    filters.end_date = val[1];
  } else {
    filters.start_date = "";
    filters.end_date = "";
  }
  fetchLogs();
}

function formatDate(dateStr: string): string {
  if (!dateStr) return "-";
  const d = new Date(dateStr);
  return d.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function getActionType(action: string): string {
  const map: Record<string, string> = {
    login: "success",
    logout: "info",
    create: "primary",
    update: "warning",
    delete: "danger",
    export: "success",
  };
  return map[action] || "";
}

function getActionLabel(action: string): string {
  const map: Record<string, string> = {
    login: "登录",
    logout: "登出",
    create: "创建",
    update: "更新",
    delete: "删除",
    export: "导出",
  };
  return map[action] || action;
}

onMounted(() => {
  fetchLogs();
});
</script>

<style scoped>
.audit-log-page {
  padding: 0;
}

.page-header {
  margin-bottom: 16px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin: 0;
}

.page-desc {
  font-size: 13px;
  color: #909399;
  margin: 4px 0 0;
}

.search-card {
  margin-bottom: 16px;
  border-radius: 10px;
}

.table-card {
  border-radius: 10px;
}

.pagination-wrap {
  padding: 16px 20px;
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid #f0f2f5;
}
</style>
