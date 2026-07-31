<template>
  <div class="inspection-container">
    <el-tabs v-model="activeTab" class="inspection-tabs">
      <!-- 巡检任务 -->
      <el-tab-pane label="巡检任务" name="tasks">
        <!-- 统计卡片 -->
        <el-row :gutter="20" class="stats-row">
          <el-col :span="6">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-icon" style="background: #409eff"><el-icon><Calendar /></el-icon></div>
              <div class="stat-info">
                <div class="stat-value">{{ stats.task_today }}</div>
                <div class="stat-label">今日任务</div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-icon" style="background: #f56c6c"><el-icon><Warning /></el-icon></div>
              <div class="stat-info">
                <div class="stat-value">{{ stats.task_overdue }}</div>
                <div class="stat-label">逾期任务</div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-icon" style="background: #67c23a"><el-icon><Check /></el-icon></div>
              <div class="stat-info">
                <div class="stat-value">{{ stats.task_completed }}</div>
                <div class="stat-label">已完成</div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-icon" style="background: #e6a23c"><el-icon><WarningFilled /></el-icon></div>
              <div class="stat-info">
                <div class="stat-value">{{ stats.issue_open }}</div>
                <div class="stat-label">待处理问题</div>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <!-- 搜索栏 -->
        <el-card class="search-card">
          <el-form :inline="true" :model="searchForm">
            <el-form-item label="状态">
              <el-select v-model="searchForm.status" clearable style="width: 120px">
                <el-option label="全部" value="" />
                <el-option label="待执行" value="pending" />
                <el-option label="执行中" value="in_progress" />
                <el-option label="已完成" value="completed" />
                <el-option label="已逾期" value="overdue" />
              </el-select>
            </el-form-item>
            <el-form-item label="日期">
              <el-date-picker
                v-model="searchForm.dateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                value-format="YYYY-MM-DD"
                style="width: 240px"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSearch">
                <el-icon><Search /></el-icon> 搜索
              </el-button>
              <el-button @click="handleReset">重置</el-button>
              <el-button type="primary" @click="showCreateTaskDialog = true">
                <el-icon><Plus /></el-icon> 创建任务
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- 任务列表 -->
        <el-card class="table-card">
          <el-table :data="tasks" v-loading="loading" stripe>
            <el-table-column prop="plan_name" label="计划名称" min-width="150" />
            <el-table-column prop="facility_name" label="所属机房" width="120" />
            <el-table-column prop="scheduled_date" label="计划日期" width="110" />
            <el-table-column prop="status" label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">
                  {{ getStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="assignee_name" label="巡检人" width="100">
              <template #default="{ row }">
                {{ row.assignee_name || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="进度" width="150">
              <template #default="{ row }">
                <el-progress
                  :percentage="getProgress(row)"
                  :status="row.abnormal_items > 0 ? 'warning' : undefined"
                />
                <span class="progress-text">
                  {{ row.completed_items }}/{{ row.total_items }}
                  <span v-if="row.abnormal_items > 0" class="abnormal-count">({{ row.abnormal_items }}异常)</span>
                </span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handleViewTask(row)">查看</el-button>
                <el-button
                  v-if="row.status === 'pending'"
                  type="success"
                  link
                  size="small"
                  @click="handleStartTask(row)"
                >
                  开始
                </el-button>
                <el-button
                  v-if="row.status === 'in_progress'"
                  type="warning"
                  link
                  size="small"
                  @click="handleExecuteTask(row)"
                >
                  执行
                </el-button>
                <el-button
                  v-if="row.status === 'in_progress' && row.completed_items > 0"
                  type="success"
                  link
                  size="small"
                  @click="handleCompleteTask(row)"
                >
                  完成
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 巡检计划 -->
      <el-tab-pane label="巡检计划" name="plans">
        <el-card class="search-card">
          <el-form :inline="true">
            <el-form-item>
              <el-button type="primary" @click="showPlanDialog = true">
                <el-icon><Plus /></el-icon> 创建计划
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
        <el-card class="table-card">
          <el-table :data="plans" v-loading="plansLoading" stripe>
            <el-table-column prop="name" label="计划名称" min-width="150" />
            <el-table-column prop="frequency" label="周期" width="80">
              <template #default="{ row }">
                {{ getFrequencyLabel(row.frequency) }}
              </template>
            </el-table-column>
            <el-table-column prop="facility_name" label="机房" width="120" />
            <el-table-column prop="template_name" label="模板" width="120" />
            <el-table-column prop="status" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
                  {{ row.status === 'active' ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="next_execute_date" label="下次执行" width="110" />
            <el-table-column prop="last_execute_date" label="上次执行" width="110" />
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="editPlan(row)">编辑</el-button>
                <el-button type="danger" link size="small" @click="handleDeletePlan(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 巡检问题 -->
      <el-tab-pane label="巡检问题" name="issues">
        <el-card class="table-card">
          <el-table :data="issues" v-loading="issuesLoading" stripe>
            <el-table-column prop="issue_title" label="问题标题" min-width="200" />
            <el-table-column prop="task_name" label="所属任务" width="150" />
            <el-table-column prop="device_name" label="关联设备" width="120" />
            <el-table-column prop="severity" label="严重程度" width="90">
              <template #default="{ row }">
                <el-tag :type="getSeverityType(row.severity)" size="small">
                  {{ getSeverityLabel(row.severity) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="getIssueStatusType(row.status)" size="small">
                  {{ getIssueStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="reporter_name" label="上报人" width="100" />
            <el-table-column prop="handler_name" label="处理人" width="100">
              <template #default="{ row }">
                {{ row.handler_name || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="160">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 创建任务对话框 -->
    <el-dialog v-model="showCreateTaskDialog" title="创建巡检任务" width="500px">
      <el-form :model="taskForm" label-width="100px">
        <el-form-item label="巡检计划" required>
          <el-select v-model="taskForm.plan_id" placeholder="请选择计划" style="width: 100%">
            <el-option
              v-for="plan in plans.filter(p => p.status === 'active')"
              :key="plan.id"
              :label="plan.name"
              :value="plan.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="执行日期">
          <el-date-picker
            v-model="taskForm.scheduled_date"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateTaskDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreateTask" :loading="submitLoading">确定</el-button>
      </template>
    </el-dialog>

    <!-- 创建计划对话框 -->
    <el-dialog v-model="showPlanDialog" :title="editingPlan ? '编辑计划' : '创建计划'" width="600px">
      <el-form :model="planForm" label-width="100px">
        <el-form-item label="计划名称" required>
          <el-input v-model="planForm.name" placeholder="请输入计划名称" />
        </el-form-item>
        <el-form-item label="计划描述">
          <el-input v-model="planForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="执行周期" required>
          <el-radio-group v-model="planForm.frequency">
            <el-radio label="daily">每天</el-radio>
            <el-radio label="weekly">每周</el-radio>
            <el-radio label="monthly">每月</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="执行时间">
          <el-time-picker
            v-model="planForm.execute_time"
            format="HH:mm"
            value-format="HH:mm"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="巡检模板">
          <el-select v-model="planForm.template_id" placeholder="请选择模板" clearable style="width: 100%">
            <el-option
              v-for="t in templates"
              :key="t.id"
              :label="t.name"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="所属机房">
          <el-select v-model="planForm.facility_id" placeholder="请选择机房" clearable style="width: 100%">
            <el-option
              v-for="f in facilities"
              :key="f.id"
              :label="f.name"
              :value="f.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="巡检人">
          <el-select v-model="planForm.assignee_id" placeholder="请选择巡检人" clearable style="width: 100%">
            <el-option
              v-for="u in users"
              :key="u.id"
              :label=\"\\ (\)\\"
              :value="u.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPlanDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSavePlan" :loading="submitLoading">确定</el-button>
      </template>
    </el-dialog>

    <!-- 任务详情/执行对话框 -->
    <el-dialog v-model="showTaskDialog" :title="currentTask?.plan_name" width="900px">
      <div v-if="currentTask">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentTask.status)">{{ getStatusLabel(currentTask.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="计划日期">{{ currentTask.scheduled_date }}</el-descriptions-item>
          <el-descriptions-item label="巡检人">{{ currentTask.assignee_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="完成进度">{{ currentTask.completed_items }}/{{ currentTask.total_items }}</el-descriptions-item>
          <el-descriptions-item label="异常项">{{ currentTask.abnormal_items }}</el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ currentTask.start_time ? formatDate(currentTask.start_time) : '-' }}</el-descriptions-item>
        </el-descriptions>

        <h4 style="margin: 20px 0 10px">巡检项</h4>
        <el-table :data="currentTask.records" border size="small">
          <el-table-column prop="item_name" label="巡检项" width="150" />
          <el-table-column prop="check_content" label="检查内容" min-width="200" />
          <el-table-column prop="check_result" label="结果" width="100">
            <template #default="{ row }">
              <el-tag
                v-if="row.check_result"
                :type="row.check_result === 'normal' ? 'success' : row.check_result === 'abnormal' ? 'danger' : 'info'"
                size="small"
              >
                {{ row.check_result === 'normal' ? '正常' : row.check_result === 'abnormal' ? '异常' : '不适用' }}
              </el-tag>
              <span v-else class="text-muted">待检查</span>
            </template>
          </el-table-column>
          <el-table-column prop="check_value" label="检查值" width="150" />
          <el-table-column prop="check_remark" label="备注" min-width="150" show-overflow-tooltip />
          <el-table-column label="操作" width="150" v-if="currentTask.status === 'in_progress'">
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click="showRecordDialog(row)">
                {{ row.check_result ? '修改' : '记录' }}
              </el-button>
              <el-button
                v-if="row.check_result === 'abnormal'"
                type="danger"
                link
                size="small"
                @click="showIssueDialog(row)"
              >
                记录问题
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <template #footer>
        <el-button @click="showTaskDialog = false">关闭</el-button>
        <el-button v-if="currentTask?.status === 'in_progress'" type="success" @click="handleCompleteTask(currentTask)">
          完成巡检
        </el-button>
      </template>
    </el-dialog>

    <!-- 巡检记录对话框 -->
    <el-dialog v-model="showRecordDialog" title="巡检记录" width="500px">
      <el-form :model="recordForm" label-width="100px">
        <el-form-item label="巡检项">{{ recordForm.item_name }}</el-form-item>
        <el-form-item label="检查内容">{{ recordForm.check_content }}</el-form-item>
        <el-form-item label="检查结果" required>
          <el-radio-group v-model="recordForm.check_result">
            <el-radio label="normal">正常</el-radio>
            <el-radio label="abnormal">异常</el-radio>
            <el-radio label="na">不适用</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="检查值">
          <el-input v-model="recordForm.check_value" placeholder="输入检查值" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="recordForm.check_remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRecordDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSaveRecord">保存</el-button>
      </template>
    </el-dialog>

    <!-- 问题记录对话框 -->
    <el-dialog v-model="showIssueDialog" title="记录问题" width="500px">
      <el-form :model="issueForm" label-width="100px">
        <el-form-item label="问题标题" required>
          <el-input v-model="issueForm.issue_title" placeholder="请输入问题标题" />
        </el-form-item>
        <el-form-item label="问题描述">
          <el-input v-model="issueForm.issue_description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="严重程度">
          <el-select v-model="issueForm.severity" style="width: 100%">
            <el-option label="低" value="low" />
            <el-option label="普通" value="normal" />
            <el-option label="严重" value="serious" />
            <el-option label="紧急" value="critical" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showIssueDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSaveIssue">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Calendar, Warning, Check, WarningFilled, Search, Plus
} from '@element-plus/icons-vue'
import {
  getInspectionTasks, getInspectionTaskDetail, createInspectionTask,
  startInspectionTask, completeInspectionTask, addInspectionRecord,
  updateInspectionRecord, getInspectionPlans, createInspectionPlan,
  updateInspectionPlan, deleteInspectionPlan, getInspectionTemplates,
  getInspectionIssues, createInspectionIssue, getInspectionStats
} from '@/api/inspection'
import { getFacilityList } from '@/api/facility'
import { getAssignableUsers } from '@/api/workOrder'

const activeTab = ref('tasks')

// 统计数据
const stats = ref({
  plan_count: 0,
  active_plan_count: 0,
  task_today: 0,
  task_overdue: 0,
  task_completed: 0,
  issue_open: 0,
  issue_resolved: 0
})

// 搜索
const searchForm = reactive({
  status: '',
  dateRange: []
})

// 列表数据
const tasks = ref<any[]>([])
const plans = ref<any[]>([])
const issues = ref<any[]>([])
const templates = ref<any[]>([])
const facilities = ref<any[]>([])
const users = ref<any[]>([])

const loading = ref(false)
const plansLoading = ref(false)
const issuesLoading = ref(false)
const submitLoading = ref(false)

// 对话框
const showCreateTaskDialog = ref(false)
const showPlanDialog = ref(false)
const showTaskDialog = ref(false)
const showRecordDialog = ref(false)
const showIssueDialog = ref(false)
const editingPlan = ref<any>(null)
const currentTask = ref<any>(null)
const currentRecord = ref<any>(null)

// 表单
const taskForm = reactive({
  plan_id: null as number | null,
  scheduled_date: ''
})

const planForm = reactive({
  name: '',
  description: '',
  frequency: 'daily',
  execute_time: '09:00',
  template_id: null as number | null,
  facility_id: null as number | null,
  assignee_id: null as number | null
})

const recordForm = reactive({
  id: null as number | null,
  item_name: '',
  item_key: '',
  check_content: '',
  check_result: 'normal',
  check_value: '',
  check_remark: ''
})

const issueForm = reactive({
  record_id: null as number | null,
  device_id: null as number | null,
  issue_title: '',
  issue_description: '',
  severity: 'normal'
})

// 加载统计
const loadStats = async () => {
  try {
    const res = await getInspectionStats()
    stats.value = res.data
  } catch (e) {
    console.error(e)
  }
}

// 加载任务列表
const loadTasks = async () => {
  loading.value = true
  try {
    const params: any = {}
    if (searchForm.status) params.status = searchForm.status
    if (searchForm.dateRange?.length === 2) {
      params.date_from = searchForm.dateRange[0]
      params.date_to = searchForm.dateRange[1]
    }
    const res = await getInspectionTasks(params)
    tasks.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

// 加载计划列表
const loadPlans = async () => {
  plansLoading.value = true
  try {
    const res = await getInspectionPlans()
    plans.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    plansLoading.value = false
  }
}

// 加载问题列表
const loadIssues = async () => {
  issuesLoading.value = true
  try {
    const res = await getInspectionIssues()
    issues.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    issuesLoading.value = false
  }
}

// 加载辅助数据
const loadOptions = async () => {
  try {
    const [tplRes, facRes, userRes] = await Promise.all([
      getInspectionTemplates(),
      getFacilityList({ page_size: 1000 }),
      getAssignableUsers()
    ])
    templates.value = tplRes.data || []
    facilities.value = facRes.data?.data || []
    users.value = userRes.data || []
  } catch (e) {
    console.error(e)
  }
}

// 搜索
const handleSearch = () => {
  loadTasks()
}

// 重置
const handleReset = () => {
  searchForm.status = ''
  searchForm.dateRange = []
  loadTasks()
}

// 创建任务
const handleCreateTask = async () => {
  if (!taskForm.plan_id) {
    ElMessage.warning('请选择巡检计划')
    return
  }
  submitLoading.value = true
  try {
    await createInspectionTask({
      plan_id: taskForm.plan_id,
      scheduled_date: taskForm.scheduled_date || undefined
    })
    ElMessage.success('任务创建成功')
    showCreateTaskDialog.value = false
    loadTasks()
    loadStats()
  } catch (e: any) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    submitLoading.value = false
  }
}

// 开始任务
const handleStartTask = async (row: any) => {
  try {
    await startInspectionTask(row.id)
    ElMessage.success('已开始巡检')
    loadTasks()
    loadStats()
  } catch (e: any) {
    ElMessage.error(e.message || '操作失败')
  }
}

// 查看任务
const handleViewTask = async (row: any) => {
  try {
    const res = await getInspectionTaskDetail(row.id)
    currentTask.value = res.data
    showTaskDialog.value = true
  } catch (e: any) {
    ElMessage.error(e.message || '加载失败')
  }
}

// 执行任务
const handleExecuteTask = (row: any) => {
  handleViewTask(row)
}

// 完成任务
const handleCompleteTask = async (row: any) => {
  try {
    await completeInspectionTask(row.id)
    ElMessage.success('巡检完成')
    showTaskDialog.value = false
    loadTasks()
    loadStats()
  } catch (e: any) {
    ElMessage.error(e.message || '操作失败')
  }
}

// 编辑计划
const editPlan = (row: any) => {
  editingPlan.value = row
  planForm.name = row.name
  planForm.description = row.description || ''
  planForm.frequency = row.frequency
  planForm.execute_time = row.execute_time || '09:00'
  planForm.template_id = row.template_id
  planForm.facility_id = row.facility_id
  planForm.assignee_id = row.assignee_id
  showPlanDialog.value = true
}

// 保存计划
const handleSavePlan = async () => {
  if (!planForm.name) {
    ElMessage.warning('请输入计划名称')
    return
  }
  submitLoading.value = true
  try {
    if (editingPlan.value) {
      await updateInspectionPlan(editingPlan.value.id, planForm)
      ElMessage.success('更新成功')
    } else {
      await createInspectionPlan(planForm)
      ElMessage.success('创建成功')
    }
    showPlanDialog.value = false
    editingPlan.value = null
    loadPlans()
    loadStats()
  } catch (e: any) {
    ElMessage.error(e.message || '操作失败')
  } finally {
    submitLoading.value = false
  }
}

// 删除计划
const handleDeletePlan = async (row: any) => {
  try {
    await deleteInspectionPlan(row.id)
    ElMessage.success('删除成功')
    loadPlans()
  } catch (e: any) {
    ElMessage.error(e.message || '删除失败')
  }
}

// 显示记录对话框
const showRecordDialogFn = (record: any) => {
  currentRecord.value = record
  recordForm.id = record.id
  recordForm.item_name = record.item_name
  recordForm.item_key = record.item_key
  recordForm.check_content = record.check_content
  recordForm.check_result = record.check_result || 'normal'
  recordForm.check_value = record.check_value || ''
  recordForm.check_remark = record.check_remark || ''
  showRecordDialog.value = true
}


// 修改 showRecordDialog 方法
const showRecordDialogFn = (row: any) => {
  currentRecord.value = row
  recordForm.id = row.id
  recordForm.item_name = row.item_name
  recordForm.item_key = row.item_key
  recordForm.check_content = row.check_content
  recordForm.check_result = row.check_result || 'normal'
  recordForm.check_value = row.check_value || ''
  recordForm.check_remark = row.check_remark || ''
  showRecordDialogRef.value = true
}

// 保存记录
const handleSaveRecord = async () => {
  if (!recordForm.check_result) {
    ElMessage.warning('请选择检查结果')
    return
  }
  submitLoading.value = true
  try {
    if (recordForm.id) {
      await updateInspectionRecord(recordForm.id, {
        item_name: recordForm.item_name,
        item_key: recordForm.item_key,
        check_content: recordForm.check_content,
        check_result: recordForm.check_result,
        check_value: recordForm.check_value,
        check_remark: recordForm.check_remark
      })
    }
    ElMessage.success('保存成功')
    showRecordDialogRef.value = false
    if (currentTask.value) {
      const res = await getInspectionTaskDetail(currentTask.value.id)
      currentTask.value = res.data
    }
    loadTasks()
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    submitLoading.value = false
  }
}

// 显示问题对话框
const showIssueDialogFn = (row: any) => {
  issueForm.record_id = row.id
  issueForm.device_id = row.device_id
  issueForm.issue_title = row.item_name + '异常'
  issueForm.issue_description = row.check_remark || ''
  issueForm.severity = 'normal'
  showIssueDialog.value = true
}

// 保存问题
const handleSaveIssue = async () => {
  if (!issueForm.issue_title) {
    ElMessage.warning('请输入问题标题')
    return
  }
  submitLoading.value = true
  try {
    await createInspectionIssue(currentTask.value.id, issueForm)
    ElMessage.success('问题已记录')
    showIssueDialog.value = false
    loadTasks()
    loadStats()
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    submitLoading.value = false
  }
}

// 进度计算
const getProgress = (row: any) => {
  if (!row.total_items) return 0
  return Math.round((row.completed_items / row.total_items) * 100)
}

// 状态标签
const getStatusType = (status: string) => {
  const map: Record<string, string> = {
    pending: 'info',
    in_progress: 'warning',
    completed: 'success',
    overdue: 'danger'
  }
  return map[status] || ''
}

const getStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    pending: '待执行',
    in_progress: '执行中',
    completed: '已完成',
    overdue: '已逾期'
  }
  return map[status] || status
}

const getFrequencyLabel = (freq: string) => {
  const map: Record<string, string> = {
    daily: '每天',
    weekly: '每周',
    monthly: '每月'
  }
  return map[freq] || freq
}

const getSeverityType = (severity: string) => {
  const map: Record<string, string> = {
    low: 'info',
    normal: '',
    serious: 'warning',
    critical: 'danger'
  }
  return map[severity] || ''
}

const getSeverityLabel = (severity: string) => {
  const map: Record<string, string> = {
    low: '低',
    normal: '普通',
    serious: '严重',
    critical: '紧急'
  }
  return map[severity] || severity
}

const getIssueStatusType = (status: string) => {
  const map: Record<string, string> = {
    open: 'warning',
    in_progress: 'primary',
    resolved: 'success',
    closed: 'info'
  }
  return map[status] || ''
}

const getIssueStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    open: '待处理',
    in_progress: '处理中',
    resolved: '已解决',
    closed: '已关闭'
  }
  return map[status] || status
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

// 监听 tab 切换
const handleTabChange = (tab: string) => {
  if (tab === 'plans') loadPlans()
  else if (tab === 'issues') loadIssues()
}

// Old version removed = (row: any) => {
  currentRecord.value = row
  recordForm.id = row.id
  recordForm.item_name = row.item_name
  recordForm.item_key = row.item_key
  recordForm.check_content = row.check_content
  recordForm.check_result = row.check_result || 'normal'
  recordForm.check_value = row.check_value || ''
  recordForm.check_remark = row.check_remark || ''
  showRecordDialogRef.value = true
}

onMounted(() => {
  loadStats()
  loadTasks()
  loadOptions()
})
</script>

<style scoped>
.inspection-container {
  padding: 20px;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 15px;
}

.stat-icon {
  width: 50px;
  height: 50px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 15px;
  font-size: 24px;
  color: white;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  color: #909399;
  font-size: 14px;
}

.search-card {
  margin-bottom: 20px;
}

.table-card {
  margin-bottom: 20px;
}

.progress-text {
  font-size: 12px;
  color: #606266;
}

.abnormal-count {
  color: #f56c6c;
}

.text-muted {
  color: #909399;
}
</style>
