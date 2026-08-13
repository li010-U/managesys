<template>
  <div class="audit-log-page">
    <div class="page-header">
      <div>
        <h3 class="page-title">审计日志</h3>
        <p class="page-desc">记录系统所有用户的操作行为，用于安全审计与问题追溯</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" plain :icon="Download" @click="handleExport" :loading="exporting">导出Excel</el-button>
        <el-button type="danger" plain :icon="Delete" @click="handleRetention" :loading="cleaning" v-if="isSuperAdmin">清理历史</el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row" v-loading="summaryLoading">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-num">{{ summary?.total ?? 0 }}</div>
          <div class="stat-label">近7天操作总数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-num stat-primary">{{ topAction?.name ?? "-" }}</div>
          <div class="stat-label">高频操作类型 ({{ topAction?.count ?? 0 }}次)</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-num stat-warning">{{ topUser?.name ?? "-" }}</div>
          <div class="stat-label">活跃操作人 ({{ topUser?.count ?? 0 }}次)</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-num stat-danger">{{ topTarget?.name ?? "-" }}</div>
          <div class="stat-label">高频对象类型</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 搜索筛选 -->
    <el-card class="search-card" :body-style="{ padding: '16px 20px' }">
      <el-row :gutter="16" align="middle">
        <el-col :span="5">
          <el-input v-model="filters.keyword" placeholder="搜索操作人/详情..." clearable @clear="fetchLogs" @keyup.enter="fetchLogs">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </el-col>
        <el-col :span="4">
          <el-select v-model="filters.action" placeholder="操作类型" clearable @change="fetchLogs">
            <el-option v-for="(label, val) in actionLabels" :key="val" :label="label" :value="val" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="filters.target_type" placeholder="对象类型" clearable @change="fetchLogs">
            <el-option v-for="(label, val) in targetLabels" :key="val" :label="label" :value="val" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-input v-model="filters.username" placeholder="操作用户" clearable @clear="fetchLogs" @keyup.enter="fetchLogs" />
        </el-col>
        <el-col :span="7">
          <el-date-picker v-model="dateRange" type="datetimerange" range-separator="至" start-placeholder="开始时间" end-placeholder="结束时间" format="YYYY-MM-DD HH:mm" value-format="YYYY-MM-DDTHH:mm:ss" @change="handleDateChange" style="width: 100%" />
        </el-col>
      </el-row>
      <el-row :gutter="16" class="filter-actions">
        <el-col :span="24" style="text-align: right">
          <el-button @click="resetFilters"><el-icon><Refresh /></el-icon>重置筛选</el-button>
          <el-button type="primary" @click="fetchLogs"><el-icon><Search /></el-icon>查询</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 日志列表 -->
    <el-card :body-style="{ padding: 0 }" class="table-card">
      <el-table :data="logs" v-loading="loading" stripe style="width: 100%">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="expand-detail">
              <div v-if="row.request_path"><span class="detail-label">请求路径:</span>{{ row.request_path }}</div>
              <div v-if="row.user_agent"><span class="detail-label">User-Agent:</span>{{ row.user_agent }}</div>
              <div v-if="row.target_id"><span class="detail-label">对象ID:</span>{{ row.target_id }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column prop="username" label="操作人" width="100">
          <template #default="{ row }"><el-tag size="small" type="info">{{ row.username }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作类型" width="100" align="center">
          <template #default="{ row }"><el-tag :type="getActionType(row.action)" size="small">{{ getActionLabel(row.action) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="对象类型" width="120" align="center">
          <template #default="{ row }"><el-tag size="small" effect="plain">{{ getTargetLabel(row.target_type) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="target_id" label="对象ID" width="80" align="center" />
        <el-table-column prop="detail" label="操作详情" min-width="240" show-overflow-tooltip />
        <el-table-column label="IP地址" width="150">
          <template #default="{ row }"><span>{{ row.ip_address || "-" }}</span></template>
        </el-table-column>
        <el-table-column prop="created_at" label="操作时间" width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
      </el-table>
      <div class="pagination-wrap">
        <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next, jumper" @size-change="fetchLogs" @current-change="fetchLogs" />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'AuditLogs' })
import { ref, reactive, onMounted, computed } from "vue";
import { Search, Refresh, Download, Delete } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { getAuditLogsApi, getAuditSummaryApi, exportAuditLogsApi, cleanupAuditLogsApi } from "@/api/auditLog";
import { useAuthStore } from "@/stores/auth";
import type { AuditLogResponse, AuditLogQuery, AuditSummaryResponse } from "@/api/auditLog";

const authStore = useAuthStore();
const isSuperAdmin = computed(() => !!authStore.user?.is_super_admin);

const loading = ref(false);
const summaryLoading = ref(false);
const exporting = ref(false);
const cleaning = ref(false);
const logs = ref<AuditLogResponse[]>([]);
const summary = ref<AuditSummaryResponse | null>(null);
const page = ref(1);
const pageSize = ref(20);
const total = ref(0);
const dateRange = ref<[string, string] | null>(null);

const filters = reactive({
  keyword: "",
  action: "",
  target_type: "",
  username: "",
  start_date: "",
  end_date: "",
});

const actionLabels: Record<string, string> = {
  login: "登录", logout: "退出", login_fail: "登录失败", create: "创建", update: "更新",
  delete: "删除", export: "导出", mount: "上架", unmount: "下架", move: "挪位",
  handle: "处理", approve: "审批", reject: "驳回", assign: "分配", start: "开始",
  complete: "完成", verify: "核验", close: "关闭", comment: "评论", upload: "上传", execute: "执行",
};

const targetLabels: Record<string, string> = {
  auth: "认证", user: "用户", role: "角色", device: "设备", device_type: "设备类型",
  data_center: "数据中心", room: "机房", rack: "机柜", system: "业务系统", business_system: "业务系统",
  alert: "告警", alert_rule: "告警规则", sensor: "传感器",
  work_order: "工单", work_order_category: "工单分类", auto_rule: "自动规则",
  inspection_template: "巡检模板", inspection_plan: "巡检计划", inspection_task: "巡检任务", issue: "问题",
  knowledge: "知识库", conversation: "AI会话", file: "文件", ip_resource: "IP资源",
};

const topAction = computed(() => summary.value?.by_action?.[0] || null);
const topUser = computed(() => summary.value?.by_user?.[0] || null);
const topTarget = computed(() => summary.value?.by_target?.[0] || null);

async function fetchSummary() {
  summaryLoading.value = true;
  try {
    const res = await getAuditSummaryApi({ days: 7 });
    summary.value = res.data;
  } catch (err) {
    console.error("Failed to fetch audit summary:", err);
  } finally {
    summaryLoading.value = false;
  }
}

async function fetchLogs() {
  loading.value = true;
  try {
    const params: AuditLogQuery = {
      page: page.value,
      page_size: pageSize.value,
      keyword: filters.keyword || undefined,
      action: filters.action || undefined,
      target_type: filters.target_type || undefined,
      username: filters.username || undefined,
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

async function handleExport() {
  exporting.value = true;
  try {
    const params: AuditLogQuery = {
      keyword: filters.keyword || undefined,
      action: filters.action || undefined,
      target_type: filters.target_type || undefined,
      username: filters.username || undefined,
      start_date: filters.start_date || undefined,
      end_date: filters.end_date || undefined,
    };
    const res = await exportAuditLogsApi(params);
    const blob = res.data as Blob;
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit_logs_${Date.now()}.xlsx`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    ElMessage.success("导出成功");
  } catch (err) {
    console.error("Failed to export audit logs:", err);
    ElMessage.error("导出失败");
  } finally {
    exporting.value = false;
  }
}

async function handleRetention() {
  try {
    await ElMessageBox.confirm("将清理 180 天以前的审计日志，该操作不可恢复，是否继续？", "清理历史审计", {
      type: "warning",
      confirmButtonText: "确认清理",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  cleaning.value = true;
  try {
    const res = await cleanupAuditLogsApi(180);
    ElMessage.success(`已清理 ${res.data?.removed ?? 0} 条历史日志`);
    fetchLogs();
    fetchSummary();
  } catch (err) {
    console.error("Failed to cleanup audit logs:", err);
    ElMessage.error("清理失败");
  } finally {
    cleaning.value = false;
  }
}

function resetFilters() {
  filters.keyword = "";
  filters.action = "";
  filters.target_type = "";
  filters.username = "";
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
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

function getActionType(action: string): string {
  const map: Record<string, string> = {
    login: "success", login_fail: "danger", logout: "info",
    create: "primary", update: "warning", delete: "danger", export: "success",
    handle: "warning", approve: "success", reject: "danger", assign: "primary", start: "primary",
    complete: "success", verify: "success", close: "info", comment: "info", upload: "primary", execute: "warning",
  };
  return (map[action] || "") as string;
}

function getActionLabel(action: string): string {
  return actionLabels[action] || action;
}

function getTargetLabel(t: string): string {
  return targetLabels[t] || t;
}

onMounted(() => {
  fetchLogs();
  fetchSummary();
});
</script>

<style scoped>
.audit-log-page { padding: 0; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.header-actions { display: flex; gap: 8px; }
.page-title { font-size: 18px; font-weight: 600; color: #303133; margin: 0; }
.page-desc { font-size: 13px; color: #909399; margin: 4px 0 0; }
.stat-row { margin-bottom: 16px; }
.stat-card { border-radius: 10px; text-align: center; }
.stat-num { font-size: 26px; font-weight: 700; color: #303133; }
.stat-primary { color: #409eff; }
.stat-warning { color: #e6a23c; }
.stat-danger { color: #f56c6c; }
.stat-label { font-size: 12px; color: #909399; margin-top: 4px; }
.search-card { margin-bottom: 16px; border-radius: 10px; }
.filter-actions { margin-top: 12px; }
.table-card { border-radius: 10px; }
.pagination-wrap { padding: 16px 20px; display: flex; justify-content: flex-end; border-top: 1px solid #f0f2f5; }
.expand-detail { padding: 8px 40px; color: #606266; font-size: 13px; line-height: 1.8; word-break: break-all; }
.detail-label { color: #909399; margin-right: 6px; }
</style>
