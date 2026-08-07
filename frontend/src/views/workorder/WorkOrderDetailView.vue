<template>
  <div class="work-order-detail" v-loading="loading">
    <div class="detail-head">
      <el-button link type="primary" @click="goBack">
        <el-icon><ArrowLeft /></el-icon> 返回列表
      </el-button>
      <span class="page-title">工单详情</span>
      <div class="head-order" v-if="order">
        <span class="head-order-no">#{{ order.order_no }}</span>
        <span class="head-order-title">{{ order.title }}</span>
        <el-tag :type="getStatusType(order.status)" size="small">{{ getStatusLabel(order.status) }}</el-tag>
      </div>
      <div class="head-nav">
        <el-button link :disabled="!hasPrev" @click="goPrev">
          <el-icon><ArrowLeft /></el-icon> 上一张
        </el-button>
        <el-button link :disabled="!hasNext" @click="goNext">
          下一张 <el-icon><ArrowRight /></el-icon>
        </el-button>
      </div>
    </div>

    <template v-if="order">
      <el-card shadow="never" class="info-card">
        <div class="card-head">
          <h3 class="order-title">#{{ order.order_no }} {{ order.title }}</h3>
          <el-tag :type="getStatusType(order.status)">{{ getStatusLabel(order.status) }}</el-tag>
        </div>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="工单编号">{{ order.order_no }}</el-descriptions-item>
          <el-descriptions-item label="优先级">
            <el-tag :type="getPriorityType(order.priority)">{{ getPriorityLabel(order.priority) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="分类">{{ order.category_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建人">{{ order.creator_name }}</el-descriptions-item>
          <el-descriptions-item label="处理人">{{ order.assignee_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="关联设备">{{ order.device_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="关联机房">{{ order.facility_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="计划日期">{{ order.plan_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="预估工时">{{ order.estimated_hours ? order.estimated_hours + '小时' : '-' }}</el-descriptions-item>
          <el-descriptions-item label="实际工时">{{ order.actual_hours ? order.actual_hours + '小时' : '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDate(order.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatDate(order.updated_at) }}</el-descriptions-item>
          <el-descriptions-item label="工单描述" :span="2">{{ order.description || '-' }}</el-descriptions-item>
          <el-descriptions-item label="处理结果" :span="2">{{ order.result || '-' }}</el-descriptions-item>
          <el-descriptions-item label="满意度" :span="2">
            <el-rate v-if="order.satisfaction" v-model="order.satisfaction" disabled />
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="用户反馈" :span="2">{{ order.feedback || '-' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 处理流程 -->
      <el-card shadow="never" class="section-card">
        <h4>处理记录</h4>
        <el-timeline>
          <el-timeline-item
            v-for="(comment, index) in order.comments"
            :key="index"
            :timestamp="formatDate(comment.created_at)"
            placement="top"
          >
            <p><strong>{{ comment.user_name }}:</strong> {{ comment.content }}</p>
          </el-timeline-item>
        </el-timeline>
      </el-card>

      <!-- 附件 -->
      <el-card shadow="never" class="section-card">
        <h4>附件</h4>
        <el-upload
          :show-file-list="false"
          :before-upload="handleBeforeUpload"
          :http-request="handleUpload"
          :disabled="order.status === 'closed'"
          accept=".png,.jpg,.jpeg,.gif,.pdf,.zip,.rar,.doc,.docx,.xls,.xlsx,.txt,.log"
        >
          <el-button type="primary" plain :disabled="order.status === 'closed'">
            <el-icon><Upload /></el-icon> 上传附件
          </el-button>
        </el-upload>
        <div v-if="uploading" class="upload-hint">上传中...</div>
        <div class="attachment-list" v-if="order.attachments && order.attachments.length">
          <div class="attachment-item" v-for="att in order.attachments" :key="att.id">
            <el-icon><Paperclip /></el-icon>
            <span class="att-name" :title="att.file_name">{{ att.file_name }}</span>
            <span class="att-size">{{ formatFileSize(att.file_size) }}</span>
            <el-button type="primary" link size="small" @click="handleDownload(att)">下载</el-button>
            <el-button type="danger" link size="small" v-if="att.uploader_id === userId || isAdmin" @click="handleDeleteAttachment(att)">删除</el-button>
          </div>
        </div>
        <div v-else class="no-attachment">暂无附件</div>
      </el-card>

      <!-- 相关知识 -->
      <el-card shadow="never" class="section-card">
        <div class="knowledge-head">
          <h4>相关知识</h4>
          <el-button
            v-if="['completed', 'closed'].includes(order.status)"
            type="success" plain size="small" :loading="kbSaving"
            @click="handleSaveKnowledge"
          >沉淀为知识</el-button>
        </div>
        <div v-if="knowledgeArticles.length" class="knowledge-list">
          <div class="knowledge-item" v-for="art in knowledgeArticles" :key="art.id">
            <el-icon><Reading /></el-icon>
            <span class="kb-title" :title="art.title">{{ art.title }}</span>
            <span class="kb-category" v-if="art.category">{{ art.category }}</span>
          </div>
        </div>
        <div v-else class="knowledge-empty">暂无相关知识（完成工单后可沉淀为知识）</div>
      </el-card>

      <!-- 操作按钮 -->
      <el-card shadow="never" class="section-card action-card">
        <template v-if="order.status !== 'closed'">
          <template v-if="order.status === 'awaiting_approval'">
            <el-button type="success" @click="handleApprove">审批通过</el-button>
            <el-button type="danger" @click="handleReject">拒绝</el-button>
            <span class="approval-hint" v-if="order.need_approval">该工单分类需要审批</span>
          </template>
          <el-button v-if="order.status === 'pending' && isAdmin" type="primary" @click="handleAssign">指派</el-button>
          <el-button v-if="order.status === 'assigned'" type="success" @click="handleStart">开始处理</el-button>
          <el-button v-if="order.status === 'processing'" type="warning" @click="handleComplete">完成处理</el-button>
          <el-button v-if="order.status === 'pending_verify' && order.creator_id === userId" type="success" @click="handleVerify(true)">验收通过</el-button>
          <el-button v-if="order.status === 'pending_verify' && order.creator_id === userId" type="danger" @click="handleVerify(false)">验收不通过</el-button>
        </template>
      </el-card>

      <!-- 添加评论 -->
      <el-card shadow="never" class="section-card" v-if="order.status !== 'closed'">
        <h4>添加评论</h4>
        <el-input v-model="commentContent" type="textarea" :rows="3" placeholder="请输入评论内容" />
        <el-button type="primary" @click="handleAddComment" style="margin-top: 10px">提交评论</el-button>
      </el-card>
    </template>

    <el-empty v-else-if="!loading" description="未找到该工单或暂无权限" />

    <!-- 指派 -->
    <el-dialog v-model="assignVisible" title="指派工单" width="500px">
      <el-form :model="assignForm" label-width="80px">
        <el-form-item label="处理人">
          <el-select v-model="assignForm.assignee_id" placeholder="请选择处理人" filterable style="width: 100%">
            <el-option v-for="user in assignableUsers" :key="user.id" :label="`${user.username} (${user.real_name})`" :value="user.id">
              <span class="assign-option">
                <span>{{ user.username }} ({{ user.real_name }}) <el-tag v-if="user.id === recommendedAssigneeId" type="success" size="small" style="margin-left: 6px">推荐·负载最低</el-tag></span>
                <span class="assign-load">在办 {{ user.workload ?? 0 }}</span>
              </span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="assignForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAssign" :loading="submitLoading">确定</el-button>
      </template>
    </el-dialog>

    <!-- 完成处理 -->
    <el-dialog v-model="completeVisible" title="完成处理" width="500px">
      <el-form :model="completeForm" label-width="80px">
        <el-form-item label="处理结果">
          <el-input v-model="completeForm.result" type="textarea" :rows="4" placeholder="请描述处理结果" />
        </el-form-item>
        <el-form-item label="实际工时">
          <el-input-number v-model="completeForm.actual_hours" :min="0" :step="0.5" :precision="1" /> 小时
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="completeVisible = false">取消</el-button>
        <el-button type="primary" @click="submitComplete" :loading="submitLoading">确定</el-button>
      </template>
    </el-dialog>

    <!-- 验收 -->
    <el-dialog v-model="verifyVisible" :title="verifyForm.accept ? '验收通过' : '验收不通过'" width="500px">
      <el-form :model="verifyForm" label-width="100px">
        <el-form-item label="满意度评分" v-if="verifyForm.accept">
          <el-rate v-model="verifyForm.satisfaction" />
        </el-form-item>
        <el-form-item label="用户反馈">
          <el-input v-model="verifyForm.feedback" type="textarea" :rows="3" placeholder="请输入反馈意见" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="verifyVisible = false">取消</el-button>
        <el-button type="primary" @click="submitVerify" :loading="submitLoading">确定</el-button>
      </template>
    </el-dialog>

    <!-- 拒绝 -->
    <el-dialog v-model="rejectVisible" title="拒绝工单" width="480px">
      <el-form :model="rejectForm" label-width="80px">
        <el-form-item label="拒绝原因">
          <el-input v-model="rejectForm.reason" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectVisible = false">取消</el-button>
        <el-button type="danger" @click="submitReject" :loading="rejecting">确定拒绝</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'WorkOrderDetail' })
import { ref, onMounted, computed, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { ElMessage, ElMessageBox } from "element-plus"
import { ArrowLeft, ArrowRight, Upload, Paperclip, Reading } from "@element-plus/icons-vue"
import {
  getWorkOrderDetail,
  getWorkOrderList,
  getAssignableUsers,
  assignWorkOrder,
  startWorkOrder,
  completeWorkOrder,
  verifyWorkOrder,
  closeWorkOrder,
  addWorkOrderComment,
  uploadWorkOrderAttachment,
  downloadWorkOrderAttachment,
  deleteWorkOrderAttachment,
  recommendKnowledge,
  createKnowledge,
  approveWorkOrder,
  rejectWorkOrder,
} from "../../api/workOrder"
import { useAuthStore } from "../../stores/auth"

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const userId = computed(() => authStore.user?.id)
const isAdmin = computed(() => authStore.user?.is_super_admin)

const order = ref<any>(null)
const loading = ref(false)
const orderIds = ref<number[]>([])
const currentIndex = ref(-1)

const hasPrev = computed(() => currentIndex.value > 0)
const hasNext = computed(() => currentIndex.value >= 0 && currentIndex.value < orderIds.value.length - 1)

// 预取工单列表 id 顺序，用于上一张/下一张导航
const loadOrderIds = async () => {
  try {
    const res = await getWorkOrderList({ page: 1, page_size: 100 })
    const items = res.data?.data || []
    orderIds.value = items.map((w: any) => w.id)
  } catch { orderIds.value = [] }
}

const goPrev = () => {
  if (hasPrev.value) router.push(`/workorder/detail/${orderIds.value[currentIndex.value - 1]}`)
}
const goNext = () => {
  if (hasNext.value) router.push(`/workorder/detail/${orderIds.value[currentIndex.value + 1]}`)
}
const commentContent = ref("")
const uploading = ref(false)
const knowledgeArticles = ref<any[]>([])
const kbSaving = ref(false)
const submitLoading = ref(false)
const rejecting = ref(false)

const assignableUsers = ref<any[]>([])
const recommendedAssigneeId = ref<number | null>(null)
const assignVisible = ref(false)
const assignForm = ref({ assignee_id: null as number | null, remark: "" })

const completeVisible = ref(false)
const completeForm = ref({ result: "", actual_hours: null as number | null })

const verifyVisible = ref(false)
const verifyForm = ref({ accept: true, satisfaction: 5, feedback: "" })

const rejectVisible = ref(false)
const rejectForm = ref({ reason: "" })

const formatDate = (dateStr?: string) => {
  if (!dateStr) return "-"
  return new Date(dateStr).toLocaleString("zh-CN")
}

const getPriorityType = (priority: string) => {
  const map: Record<string, string> = { low: "info", normal: "", high: "warning", urgent: "danger" }
  return map[priority] || ""
}
const getPriorityLabel = (priority: string) => {
  const map: Record<string, string> = { low: "低", normal: "普通", high: "高", urgent: "紧急" }
  return map[priority] || priority
}
const getStatusType = (status: string) => {
  const map: Record<string, string> = {
    pending: "warning", awaiting_approval: "danger", assigned: "primary",
    processing: "warning", pending_verify: "info", completed: "success", closed: "info",
  }
  return map[status] || ""
}
const getStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    pending: "待分配", awaiting_approval: "待审批", assigned: "已指派",
    processing: "处理中", pending_verify: "待验收", completed: "已完成", closed: "已关闭",
  }
  return map[status] || status
}

const goBack = () => router.push("/workorder/list")

// 记录最近浏览的工单（本地存储，上限 8 条）
const RECENT_KEY = "pet_recent_work_orders"
function recordRecent(wo: any) {
  if (!wo?.id) return
  try {
    let arr: any[] = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]")
    arr = arr.filter((x) => x.id !== wo.id)
    arr.unshift({ id: wo.id, order_no: wo.order_no, title: wo.title, status: wo.status })
    localStorage.setItem(RECENT_KEY, JSON.stringify(arr.slice(0, 8)))
  } catch { /* ignore */ }
}

const loadDetail = async () => {
  loading.value = true
  try {
    const id = Number(route.params.id)
    const res = await getWorkOrderDetail(id)
    order.value = res.data.data
    currentIndex.value = orderIds.value.indexOf(id)
    recordRecent(order.value)
    loadKnowledgeRecommend(order.value?.title || "")
  } catch (e: any) {
    order.value = null
    ElMessage.error(e?.response?.data?.detail || e?.message || "加载工单详情失败")
  } finally {
    loading.value = false
  }
}

const loadAssignable = async () => {
  try {
    const res = await getAssignableUsers()
    assignableUsers.value = res.data?.data || []
    recommendedAssigneeId.value = res.data?.recommended_id ?? null
  } catch { /* ignore */ }
}

const loadKnowledgeRecommend = async (keyword: string) => {
  if (!keyword) { knowledgeArticles.value = []; return }
  try {
    const res = await recommendKnowledge(keyword)
    knowledgeArticles.value = res.data?.data || []
  } catch { knowledgeArticles.value = [] }
}

const handleSaveKnowledge = async () => {
  if (!order.value) return
  if (!order.value.result) {
    ElMessage.warning("请先填写处理结果再沉淀为知识")
    return
  }
  kbSaving.value = true
  try {
    const title = `[案例] ${order.value.title}`
    const content = `工单编号：${order.value.order_no}\n分类：${order.value.category_name || "-"}\n优先级：${getPriorityLabel(order.value.priority)}\n处理结果：${order.value.result}\n用户反馈：${order.value.feedback || "-"}`
    await createKnowledge({ title, category: order.value.category_name || "工单案例", content, source_order_id: order.value.id })
    ElMessage.success("已沉淀为知识，可在相关知识中查看")
    loadKnowledgeRecommend(order.value.title || "")
  } catch (e: any) {
    ElMessage.error(e?.message || "沉淀失败")
  } finally {
    kbSaving.value = false
  }
}

const handleAssign = () => {
  assignForm.value = { assignee_id: recommendedAssigneeId.value, remark: "" }
  assignVisible.value = true
}
const submitAssign = async () => {
  if (!assignForm.value.assignee_id) { ElMessage.warning("请选择处理人"); return }
  submitLoading.value = true
  try {
    await assignWorkOrder(order.value.id, assignForm.value)
    ElMessage.success("指派成功")
    assignVisible.value = false
    await loadDetail()
  } catch (e: any) {
    ElMessage.error(e.message || "指派失败")
  } finally { submitLoading.value = false }
}

const handleStart = async () => {
  try {
    await startWorkOrder(order.value.id)
    ElMessage.success("已开始处理")
    await loadDetail()
  } catch (e: any) {
    ElMessage.error(e.message || "操作失败")
  }
}

const handleComplete = () => {
  completeForm.value = { result: "", actual_hours: null }
  completeVisible.value = true
}
const submitComplete = async () => {
  if (!completeForm.value.result) { ElMessage.warning("请输入处理结果"); return }
  submitLoading.value = true
  try {
    await completeWorkOrder(order.value.id, completeForm.value)
    ElMessage.success("提交成功")
    completeVisible.value = false
    await loadDetail()
  } catch (e: any) {
    ElMessage.error(e.message || "提交失败")
  } finally { submitLoading.value = false }
}

const handleVerify = (accept: boolean) => {
  verifyForm.value = { accept, satisfaction: 5, feedback: "" }
  verifyVisible.value = true
}
const submitVerify = async () => {
  submitLoading.value = true
  try {
    await verifyWorkOrder(order.value.id, verifyForm.value)
    ElMessage.success("验收成功")
    verifyVisible.value = false
    await loadDetail()
  } catch (e: any) {
    ElMessage.error(e.message || "验收失败")
  } finally { submitLoading.value = false }
}

const handleReject = () => {
  rejectForm.value = { reason: "" }
  rejectVisible.value = true
}
const submitReject = async () => {
  rejecting.value = true
  try {
    await rejectWorkOrder(order.value.id, { reason: rejectForm.value.reason })
    ElMessage.success("已拒绝")
    rejectVisible.value = false
    await loadDetail()
  } catch (e: any) {
    ElMessage.error(e?.message || "拒绝失败")
  } finally { rejecting.value = false }
}

const handleApprove = async () => {
  try {
    await approveWorkOrder(order.value.id)
    ElMessage.success("审批通过")
    await loadDetail()
  } catch (e: any) {
    ElMessage.error(e?.message || "审批失败")
  }
}

const handleAddComment = async () => {
  if (!commentContent.value.trim()) { ElMessage.warning("请输入评论内容"); return }
  try {
    await addWorkOrderComment(order.value.id, { content: commentContent.value, comment_type: "normal" })
    ElMessage.success("评论成功")
    commentContent.value = ""
    await loadDetail()
  } catch (e: any) {
    ElMessage.error(e.message || "评论失败")
  }
}

const handleBeforeUpload = (file: File) => {
  if (file.size > 10 * 1024 * 1024) { ElMessage.warning("单个文件不能超过 10MB"); return false }
  return true
}
const handleUpload = async (options: any) => {
  if (!order.value) return
  uploading.value = true
  try {
    await uploadWorkOrderAttachment(order.value.id, options.file)
    ElMessage.success("上传成功")
    await loadDetail()
  } catch (e: any) {
    ElMessage.error(e?.message || "上传失败")
  } finally { uploading.value = false }
}
const handleDownload = async (att: any) => {
  try {
    const res: any = await downloadWorkOrderAttachment(att.id)
    const blob = new Blob([res.data])
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = att.file_name
    a.click()
    window.URL.revokeObjectURL(url)
  } catch { ElMessage.error("下载失败") }
}
const handleDeleteAttachment = (att: any) => {
  ElMessageBox.confirm("确定删除该附件吗？", "提示", {
    confirmButtonText: "确定", cancelButtonText: "取消", type: "warning",
  }).then(async () => {
    try {
      await deleteWorkOrderAttachment(att.id)
      ElMessage.success("删除成功")
      await loadDetail()
    } catch (e: any) {
      ElMessage.error(e?.message || "删除失败")
    }
  })
}
const formatFileSize = (bytes?: number) => {
  if (!bytes && bytes !== 0) return "-"
  if (bytes < 1024) return bytes + " B"
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB"
  return (bytes / 1024 / 1024).toFixed(1) + " MB"
}

// 在同一详情组件内切换上一张/下一张时，路由参数变化触发重新加载
watch(() => route.params.id, () => loadDetail())

onMounted(async () => {
  await loadOrderIds()
  loadDetail()
  loadAssignable()
})
</script>

<style scoped>
.work-order-detail { padding: 20px; max-width: 960px; margin: 0 auto; }
.detail-head { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.page-title { font-size: 18px; font-weight: 700; color: #1e293b; }
.head-nav { margin-left: auto; display: flex; gap: 8px; }
.head-order { display: flex; align-items: center; gap: 8px; min-width: 0; margin-left: 8px; }
.head-order-no { color: #64748b; font-size: 13px; }
.head-order-title { font-size: 13px; color: #334155; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 320px; }
.info-card { margin-bottom: 16px; }
.card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.order-title { margin: 0; font-size: 16px; color: #1e293b; }
.section-card { margin-bottom: 16px; }
.section-card h4 { margin: 0 0 12px; color: #334155; }
.knowledge-head { display: flex; align-items: center; justify-content: space-between; }
.attachment-item { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px dashed #e2e8f0; }
.att-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #334155; }
.att-size { color: #94a3b8; font-size: 12px; }
.knowledge-item { display: flex; align-items: center; gap: 8px; padding: 6px 0; }
.kb-title { flex: 1; color: #334155; }
.kb-category { font-size: 12px; color: #64748b; background: #f1f5f9; padding: 1px 8px; border-radius: 6px; }
.knowledge-empty, .no-attachment, .upload-hint { color: #94a3b8; font-size: 13px; padding: 8px 0; }
.action-card { display: flex; gap: 10px; }
.approval-hint { color: #f59e0b; font-size: 12px; }
</style>
