<template>
  <div class="work-order-container">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #409eff">
            <el-icon><Document /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.total }}</div>
            <div class="stat-label">工单总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #e6a23c">
            <el-icon><Clock /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.pending }}</div>
            <div class="stat-label">待处理</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #67c23a">
            <el-icon><Loading /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.processing }}</div>
            <div class="stat-label">处理中</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #909399">
            <el-icon><Check /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.completed }}</div>
            <div class="stat-label">已完成</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 搜索和操作栏 -->
    <el-card class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 120px">
            <el-option label="全部" value="" />
            <el-option label="待分配" value="pending" />
            <el-option label="待审批" value="awaiting_approval" />
            <el-option label="已指派" value="assigned" />
            <el-option label="处理中" value="processing" />
            <el-option label="待验收" value="pending_verify" />
            <el-option label="已完成" value="completed" />
            <el-option label="已关闭" value="closed" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="searchForm.priority" placeholder="全部" clearable style="width: 120px">
            <el-option label="全部" value="" />
            <el-option label="低" value="low" />
            <el-option label="普通" value="normal" />
            <el-option label="高" value="high" />
            <el-option label="紧急" value="urgent" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="searchForm.keyword" placeholder="工单标题/编号" clearable style="width: 180px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon> 搜索
          </el-button>
          <el-button @click="handleReset">
            <el-icon><Refresh /></el-icon> 重置
          </el-button>
          <el-button type="primary" @click="handleCreate">
            <el-icon><Plus /></el-icon> 创建工单
          </el-button>
          <el-button @click="handleOpenRules">
            <el-icon><SetUp /></el-icon> 自动化规则
          </el-button>
          <el-button @click="handleOpenCategories">
            <el-icon><Collection /></el-icon> 分类配置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 工单列表 -->
    <el-card class="table-card">
      <div class="view-toggle">
        <el-radio-group v-model="viewMode" @change="handleViewModeChange">
          <el-radio-button value="table">列表</el-radio-button>
          <el-radio-button value="board">看板</el-radio-button>
        </el-radio-group>
      </div>
      <el-table :data="workOrders" v-loading="loading" stripe>
        <el-table-column prop="order_no" label="工单编号" width="180" fixed />
        <el-table-column prop="title" label="工单标题" min-width="200" fixed />
        <el-table-column prop="category_name" label="分类" width="100" />
        <el-table-column prop="priority" label="优先级" width="80">
          <template #default="{ row }">
            <el-tag :type="getPriorityType(row.priority)" size="small">
              {{ getPriorityLabel(row.priority) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="creator_name" label="创建人" width="100" />
        <el-table-column prop="assignee_name" label="处理人" width="100">
          <template #default="{ row }">
            <span v-if="row.assignee_name">{{ row.assignee_name }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="device_name" label="关联设备" width="120" show-overflow-tooltip />
        <el-table-column prop="plan_date" label="计划日期" width="110" />
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleView(row)">
              查看
            </el-button>
            <el-button type="primary" link size="small" @click="handleEdit(row)" v-if="canEdit(row)">
              编辑
            </el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)" v-if="canDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadData"
          @current-change="loadData"
        />
      </div>

      <!-- 看板视图 -->
      <div class="board-view" v-if="viewMode === 'board'">
        <div class="board-column" v-for="col in boardColumns" :key="col.status">
          <div class="board-column-header">
            <span class="col-dot" :style="{ background: col.color }"></span>
            <span class="col-name">{{ col.label }}</span>
            <span class="col-count">{{ boardGroup(col.status).length }}</span>
          </div>
          <div class="board-column-body">
            <div
              class="board-card"
              v-for="wo in boardGroup(col.status)"
              :key="wo.id"
              @click="handleView(wo)"
            >
              <div class="board-card-top">
                <el-tag :type="getPriorityType(wo.priority)" size="small">
                  {{ getPriorityLabel(wo.priority) }}
                </el-tag>
                <span class="board-no">{{ wo.order_no }}</span>
              </div>
              <div class="board-title">{{ wo.title }}</div>
              <div class="board-meta">
                <span>{{ wo.category_name || '-' }}</span>
                <span>处理人: {{ wo.assignee_name || '-' }}</span>
              </div>
              <div class="board-foot">
                <span>{{ formatDate(wo.created_at) }}</span>
                <el-button link type="primary" size="small" @click.stop="handleView(wo)">查看</el-button>
              </div>
            </div>
            <div class="board-empty" v-if="boardGroup(col.status).length === 0">暂无工单</div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 创建/编辑工单对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="700px"
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="工单标题" prop="title">
          <el-input v-model="form.title" placeholder="请输入工单标题" />
        </el-form-item>
        <el-form-item label="工单分类" prop="category_id">
          <el-select v-model="form.category_id" placeholder="请选择分类" style="width: 100%">
            <el-option
              v-for="cat in categories"
              :key="cat.id"
              :label="cat.name"
              :value="cat.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级" prop="priority">
          <el-radio-group v-model="form.priority">
            <el-radio label="low">低</el-radio>
            <el-radio label="normal">普通</el-radio>
            <el-radio label="high">高</el-radio>
            <el-radio label="urgent">紧急</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="工单描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="4" placeholder="请详细描述工单内容" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="关联设备">
              <el-select
                v-model="form.device_id"
                placeholder="请选择设备"
                filterable
                clearable
                style="width: 100%"
                @change="handleDeviceChange"
              >
                <el-option
                  v-for="device in devices"
                  :key="device.id"
                  :label="`${device.name} (${device.asset_number})`"
                  :value="device.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联机房">
              <el-select v-model="form.facility_id" placeholder="请选择机房" clearable style="width: 100%">
                <el-option
                  v-for="facility in facilities"
                  :key="facility.id"
                  :label="facility.name"
                  :value="facility.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="指派给">
              <el-select
                v-model="form.assignee_id"
                placeholder="请选择处理人"
                filterable
                clearable
                style="width: 100%"
              >
                <el-option
                  v-for="user in assignableUsers"
                  :key="user.id"
                  :label="`${user.username} (${user.real_name})`"
                  :value="user.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计划完成日期">
              <el-date-picker
                v-model="form.plan_date"
                type="date"
                placeholder="选择日期"
                style="width: 100%"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="预估工时">
          <el-input-number v-model="form.estimated_hours" :min="0" :step="0.5" :precision="1" />
          <span class="form-tip">小时</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitLoading">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 工单详情对话框 -->
    <el-dialog v-model="detailVisible" title="工单详情" width="900px">
      <div v-if="currentOrder" class="order-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="工单编号">{{ currentOrder.order_no }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentOrder.status)">
              {{ getStatusLabel(currentOrder.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="工单标题" :span="2">{{ currentOrder.title }}</el-descriptions-item>
          <el-descriptions-item label="分类">{{ currentOrder.category_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="优先级">
            <el-tag :type="getPriorityType(currentOrder.priority)">
              {{ getPriorityLabel(currentOrder.priority) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建人">{{ currentOrder.creator_name }}</el-descriptions-item>
          <el-descriptions-item label="处理人">{{ currentOrder.assignee_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="关联设备">{{ currentOrder.device_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="关联机房">{{ currentOrder.facility_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="计划日期">{{ currentOrder.plan_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="预估工时">{{ currentOrder.estimated_hours ? currentOrder.estimated_hours + '小时' : '-' }}</el-descriptions-item>
          <el-descriptions-item label="实际工时">{{ currentOrder.actual_hours ? currentOrder.actual_hours + '小时' : '-' }}</el-descriptions-item>
          <el-descriptions-item label="工单描述" :span="2">{{ currentOrder.description || '-' }}</el-descriptions-item>
          <el-descriptions-item label="处理结果" :span="2">{{ currentOrder.result || '-' }}</el-descriptions-item>
          <el-descriptions-item label="满意度" :span="2">
            <el-rate v-if="currentOrder.satisfaction" v-model="currentOrder.satisfaction" disabled />
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="用户反馈" :span="2">{{ currentOrder.feedback || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDate(currentOrder.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ formatDate(currentOrder.updated_at) }}</el-descriptions-item>
        </el-descriptions>

        <!-- 处理流程 -->
        <div class="process-section">
          <h4>处理记录</h4>
          <el-timeline>
            <el-timeline-item
              v-for="(comment, index) in currentOrder.comments"
              :key="index"
              :timestamp="formatDate(comment.created_at)"
              placement="top"
            >
              <p><strong>{{ comment.user_name }}:</strong> {{ comment.content }}</p>
            </el-timeline-item>
          </el-timeline>
        </div>

        <!-- 附件 -->
        <div class="attachment-section">
          <h4>附件</h4>
          <el-upload
            :show-file-list="false"
            :before-upload="handleBeforeUpload"
            :http-request="handleUpload"
            :disabled="currentOrder.status === 'closed'"
            accept=".png,.jpg,.jpeg,.gif,.pdf,.zip,.rar,.doc,.docx,.xls,.xlsx,.txt,.log"
          >
            <el-button type="primary" plain :disabled="currentOrder.status === 'closed'">
              <el-icon><Upload /></el-icon> 上传附件
            </el-button>
          </el-upload>
          <div v-if="uploading" class="upload-hint">上传中...</div>
          <div class="attachment-list" v-if="currentOrder.attachments && currentOrder.attachments.length">
            <div class="attachment-item" v-for="att in currentOrder.attachments" :key="att.id">
              <el-icon><Paperclip /></el-icon>
              <span class="att-name" :title="att.file_name">{{ att.file_name }}</span>
              <span class="att-size">{{ formatFileSize(att.file_size) }}</span>
              <el-button type="primary" link size="small" @click="handleDownload(att)">下载</el-button>
              <el-button
                type="danger" link size="small"
                v-if="att.uploader_id === userId || isAdmin"
                @click="handleDeleteAttachment(att)"
              >删除</el-button>
            </div>
          </div>
          <div v-else class="no-attachment">暂无附件</div>
        </div>

        <!-- 相关知识 -->
        <div class="knowledge-section">
          <div class="knowledge-head">
            <h4>相关知识</h4>
            <el-button
              v-if="['completed', 'closed'].includes(currentOrder.status)"
              type="success" plain size="small"
              :loading="kbSaving"
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
        </div>

        <!-- 操作按钮 -->
        <div class="action-buttons" v-if="currentOrder.status !== 'closed'">
          <template v-if="currentOrder.status === 'awaiting_approval'">
            <el-button type="success" @click="handleApprove(currentOrder)">
              审批通过
            </el-button>
            <el-button type="danger" @click="handleReject(currentOrder)">
              拒绝
            </el-button>
            <span class="approval-hint" v-if="currentOrder.need_approval">该工单分类需要审批</span>
          </template>
          <el-button
            v-if="currentOrder.status === 'pending' && isAdmin"
            type="primary"
            @click="handleAssign(currentOrder)"
          >
            指派
          </el-button>
          <el-button
            v-if="currentOrder.status === 'assigned'"
            type="success"
            @click="handleStart(currentOrder)"
          >
            开始处理
          </el-button>
          <el-button
            v-if="currentOrder.status === 'processing'"
            type="warning"
            @click="handleComplete(currentOrder)"
          >
            完成处理
          </el-button>
          <el-button
            v-if="currentOrder.status === 'pending_verify' && currentOrder.creator_id === userId"
            type="success"
            @click="handleVerify(currentOrder, true)"
          >
            验收通过
          </el-button>
          <el-button
            v-if="currentOrder.status === 'pending_verify' && currentOrder.creator_id === userId"
            type="danger"
            @click="handleVerify(currentOrder, false)"
          >
            验收不通过
          </el-button>
          <el-button
            v-if="['completed', 'closed'].includes(currentOrder.status)"
            type="primary" plain
            @click="handleSaveKnowledge"
            :loading="kbSaving"
          >
            沉淀为知识
          </el-button>
          <el-button
            v-if="['completed', 'closed'].includes(currentOrder.status)"
            type="info"
            @click="handleClose(currentOrder)"
          >
            关闭工单
          </el-button>
        </div>

        <!-- 添加评论 -->
        <div class="comment-section" v-if="currentOrder.status !== 'closed'">
          <h4>添加评论</h4>
          <el-input
            v-model="commentContent"
            type="textarea"
            :rows="3"
            placeholder="请输入评论内容"
          />
          <el-button type="primary" @click="handleAddComment" style="margin-top: 10px">
            提交评论
          </el-button>
        </div>
      </div>
    </el-dialog>

    <!-- 指派对话框 -->
    <el-dialog v-model="assignVisible" title="指派工单" width="500px">
      <el-form :model="assignForm" label-width="80px">
        <el-form-item label="处理人">
          <el-select
            v-model="assignForm.assignee_id"
            placeholder="请选择处理人"
            filterable
            style="width: 100%"
          >
            <el-option
              v-for="user in assignableUsers"
              :key="user.id"
              :label="`${user.username} (${user.real_name})`"
              :value="user.id"
            >
              <span class="assign-option">
                <span>
                  {{ user.username }} ({{ user.real_name }})
                  <el-tag v-if="user.id === recommendedAssigneeId" type="success" size="small" style="margin-left: 6px">推荐·负载最低</el-tag>
                </span>
                <span class="assign-load">在办 {{ user.workload ?? 0 }}</span>
              </span>
            </el-option>
          </el-select>
          <div class="assign-tip" v-if="recommendedAssigneeId">
            建议指派给「{{ recommendedUserLabel }}」（当前在办数最少，合理均衡负载）
          </div>
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

    <!-- 完成处理对话框 -->
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

    <!-- 验收对话框 -->
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

    <!-- 关闭对话框 -->
    <el-dialog v-model="closeVisible" title="关闭工单" width="500px">
      <el-form :model="closeForm" label-width="80px">
        <el-form-item label="关闭说明">
          <el-input v-model="closeForm.remark" type="textarea" :rows="3" placeholder="请输入关闭说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeVisible = false">取消</el-button>
        <el-button type="primary" @click="submitClose" :loading="submitLoading">确定</el-button>
      </template>
    </el-dialog>

    <!-- 自动化规则管理 -->
    <el-dialog v-model="rulesVisible" title="自动化规则" width="860px" :close-on-click-modal="false">
      <div class="rules-toolbar">
        <el-button type="primary" size="small" @click="handleNewRule">
          <el-icon><Plus /></el-icon> 新增规则
        </el-button>
        <span class="rules-tip">创建工单时按排序依次匹配，命中后自动设置优先级/指派处理人，可配置自动完成</span>
      </div>
      <el-table :data="autoRules" v-loading="rulesLoading" stripe size="small">
        <el-table-column prop="name" label="规则名称" min-width="140" />
        <el-table-column label="启用" width="70">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" @change="toggleRule(row)" />
          </template>
        </el-table-column>
        <el-table-column prop="match_keyword" label="匹配关键词" width="120" show-overflow-tooltip>
          <template #default="{ row }"><span v-if="row.match_keyword">{{ row.match_keyword }}</span><span v-else class="text-muted">-</span></template>
        </el-table-column>
        <el-table-column prop="category_name" label="匹配分类" width="100">
          <template #default="{ row }"><span v-if="row.category_name">{{ row.category_name }}</span><span v-else class="text-muted">-</span></template>
        </el-table-column>
        <el-table-column label="动作" min-width="180">
          <template #default="{ row }">
            <span class="rule-action">
              <span v-if="row.action_set_priority">优先级→{{ getPriorityLabel(row.action_set_priority) }}</span>
              <span v-if="row.action_assign_user_id">指派→{{ row.assign_username }}</span>
              <span v-if="row.action_auto_complete" class="auto-complete-tag">自动完成</span>
              <span v-if="!row.action_set_priority && !row.action_assign_user_id && !row.action_auto_complete" class="text-muted">-</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="sort" label="排序" width="60" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleEditRule(row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="handleDeleteRule(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 规则编辑 -->
    <el-dialog v-model="ruleDialogVisible" :title="ruleForm.id ? '编辑规则' : '新增规则'" width="520px" :close-on-click-modal="false">
      <el-form :model="ruleForm" label-width="110px">
        <el-form-item label="规则名称" required>
          <el-input v-model="ruleForm.name" placeholder="如：网络故障自动指派" />
        </el-form-item>
        <el-form-item label="匹配关键词">
          <el-input v-model="ruleForm.match_keyword" placeholder="标题/描述包含该词即命中" />
        </el-form-item>
        <el-form-item label="匹配分类">
          <el-select v-model="ruleForm.match_category_id" clearable placeholder="全部" style="width: 100%">
            <el-option v-for="cat in categories" :key="cat.id" :label="cat.name" :value="cat.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="匹配优先级">
          <el-select v-model="ruleForm.match_priority" clearable placeholder="全部" style="width: 100%">
            <el-option label="低" value="low" />
            <el-option label="普通" value="normal" />
            <el-option label="高" value="high" />
            <el-option label="紧急" value="urgent" />
          </el-select>
        </el-form-item>
        <el-form-item label="动作:设优先级">
          <el-select v-model="ruleForm.action_set_priority" clearable placeholder="不调整" style="width: 100%">
            <el-option label="低" value="low" />
            <el-option label="普通" value="normal" />
            <el-option label="高" value="high" />
            <el-option label="紧急" value="urgent" />
          </el-select>
        </el-form-item>
        <el-form-item label="动作:指派处理人">
          <el-select v-model="ruleForm.action_assign_user_id" clearable placeholder="不指派" style="width: 100%">
            <el-option v-for="u in assignableUsers" :key="u.id" :label="`${u.username} (${u.real_name})`" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="自动完成">
          <el-switch v-model="ruleForm.action_auto_complete" />
          <span class="rules-tip">命中后直接置为已完成（用于自动化处置）</span>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="ruleForm.enabled" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="ruleForm.sort" :min="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ruleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="ruleSaving" @click="submitRule">保存</el-button>
      </template>
    </el-dialog>

    <!-- 分类配置 -->
    <el-dialog v-model="categoriesVisible" title="分类配置" width="760px" :close-on-click-modal="false">
      <el-form :inline="true" class="cat-form">
        <el-form-item label="分类名称">
          <el-input v-model="catForm.name" placeholder="名称" style="width:140px" />
        </el-form-item>
        <el-form-item label="编码">
          <el-input v-model="catForm.code" placeholder="code" style="width:140px" />
        </el-form-item>
        <el-form-item label="需要审批">
          <el-switch v-model="catForm.need_approval" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="default" @click="submitCategory">{{ catForm.id ? '更新' : '新增' }}</el-button>
          <el-button v-if="catForm.id" size="default" @click="resetCatForm">取消编辑</el-button>
        </el-form-item>
      </el-form>
      <el-table :data="categories" size="small" class="cat-table">
        <el-table-column prop="name" label="分类名称" width="140" />
        <el-table-column prop="code" label="编码" width="140" />
        <el-table-column prop="sort" label="排序" width="70" />
        <el-table-column label="需要审批" width="100">
          <template #default="{ row }">
            <el-switch v-model="row.need_approval" @change="toggleCategoryApproval(row)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="editCategory(row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="removeCategory(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 拒绝工单 -->
    <el-dialog v-model="rejectVisible" title="拒绝工单" width="480px" :close-on-click-modal="false">
      <el-form :model="rejectForm" label-width="90px">
        <el-form-item label="拒绝原因">
          <el-input v-model="rejectForm.reason" type="textarea" :rows="4" placeholder="请输入拒绝原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectVisible = false">取消</el-button>
        <el-button type="danger" :loading="rejecting" @click="submitReject">确认拒绝</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Document, Clock, Loading, Check, Search, Refresh, Plus, Upload, Paperclip, Reading, SetUp, Collection
} from '@element-plus/icons-vue'
import {
  getWorkOrderList,
  getWorkOrderStats,
  getWorkOrderDetail,
  createWorkOrder,
  updateWorkOrder,
  deleteWorkOrder,
  assignWorkOrder,
  startWorkOrder,
  completeWorkOrder,
  verifyWorkOrder,
  closeWorkOrder,
  addWorkOrderComment,
  getWorkOrderCategories,
  createWorkOrderCategory,
  updateWorkOrderCategory,
  deleteWorkOrderCategory,
  getAssignableUsers,
  uploadWorkOrderAttachment,
  downloadWorkOrderAttachment,
  deleteWorkOrderAttachment,
  recommendKnowledge,
  createKnowledge,
  getAutoRules,
  createAutoRule,
  updateAutoRule,
  deleteAutoRule,
  approveWorkOrder,
  rejectWorkOrder
} from '@/api/workOrder'
import { getDevicesApi } from '@/api/device'
import { getAllRoomsApi } from '@/api/facility'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const userId = computed(() => authStore.user?.id)
const isAdmin = computed(() => authStore.user?.is_super_admin)
const recommendedUserLabel = computed(() => {
  const u = assignableUsers.value.find(x => x.id === recommendedAssigneeId.value)
  return u ? `${u.username} (${u.real_name})` : ''
})

// 统计数据
const stats = ref({
  total: 0,
  pending: 0,
  processing: 0,
  completed: 0,
  closed: 0,
  my_pending: 0,
  my_processing: 0
})

// 搜索表单
const searchForm = reactive({
  status: '',
  priority: '',
  keyword: ''
})

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// 列表数据
const workOrders = ref<any[]>([])
const loading = ref(false)
const viewMode = ref<'table' | 'board'>('table')
const boardColumns = [
  { status: 'pending', label: '待分配', color: '#e6a23c' },
  { status: 'assigned', label: '已指派', color: '#409eff' },
  { status: 'processing', label: '处理中', color: '#67c23a' },
  { status: 'pending_verify', label: '待验收', color: '#a0cfff' },
  { status: 'completed', label: '已完成', color: '#909399' },
  { status: 'closed', label: '已关闭', color: '#c0c4cc' }
]
const boardGroup = (status: string) => workOrders.value.filter(w => w.status === status)
const categories = ref<any[]>([])
const assignableUsers = ref<any[]>([])
const recommendedAssigneeId = ref<number | null>(null)
const devices = ref<any[]>([])
const facilities = ref<any[]>([])

// 对话框
const dialogVisible = ref(false)
const detailVisible = ref(false)
const assignVisible = ref(false)
const completeVisible = ref(false)
const verifyVisible = ref(false)
const closeVisible = ref(false)
const dialogTitle = ref('创建工单')
const submitLoading = ref(false)
const currentOrder = ref<any>(null)

// 表单
const formRef = ref()
const form = reactive({
  id: null as number | null,
  title: '',
  description: '',
  category_id: null as number | null,
  priority: 'normal',
  device_id: null as number | null,
  facility_id: null as number | null,
  assignee_id: null as number | null,
  plan_date: '',
  estimated_hours: null as number | null
})

// 评论
const commentContent = ref('')
const uploading = ref(false)
const knowledgeArticles = ref<any[]>([])
const kbSaving = ref(false)

// 自动化规则
const rulesVisible = ref(false)
const ruleDialogVisible = ref(false)
const rulesLoading = ref(false)
const ruleSaving = ref(false)
const autoRules = ref<any[]>([])
const ruleForm = reactive({
  id: null as number | null,
  name: '',
  enabled: true,
  match_keyword: '',
  match_category_id: null as number | null,
  match_priority: '',
  action_set_priority: '',
  action_assign_user_id: null as number | null,
  action_auto_complete: false,
  sort: 0
})

// 分类配置
const categoriesVisible = ref(false)
const catForm = reactive({
  id: null as number | null,
  name: '',
  code: '',
  need_approval: false
})

// 审批
const rejectVisible = ref(false)
const rejecting = ref(false)
const rejectForm = reactive({ reason: '' })

// 指派表单
const assignForm = reactive({
  assignee_id: null as number | null,
  remark: ''
})

// 完成表单
const completeForm = reactive({
  result: '',
  actual_hours: null as number | null
})

// 验收表单
const verifyForm = reactive({
  accept: true,
  satisfaction: 5,
  feedback: ''
})

// 关闭表单
const closeForm = reactive({
  remark: ''
})

const rules = {
  title: [{ required: true, message: '请输入工单标题', trigger: 'blur' }]
}

// 加载统计数据
const loadStats = async () => {
  try {
    const res = await getWorkOrderStats()
    stats.value = res.data.data
  } catch (e) {
    console.error(e)
  }
}

// 加载列表数据
const loadData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    const res = await getWorkOrderList(params)
    workOrders.value = res.data.data || []
    pagination.total = res.data.total ?? res.data.data?.length ?? 0
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

// 加载辅助数据
const loadOptions = async () => {
  try {
    const [catRes, userRes, deviceRes, facilityRes] = await Promise.all([
      getWorkOrderCategories(),
      getAssignableUsers(),
      getDevicesApi({ page: 1, page_size: 1000 }),
      getAllRoomsApi()
    ])
    categories.value = catRes.data?.data || []
    assignableUsers.value = (userRes.data?.data || []).sort((a: any, b: any) => (a.workload ?? 0) - (b.workload ?? 0))
    recommendedAssigneeId.value = userRes.data?.recommended_id ?? null
    devices.value = deviceRes.data.items || []
    facilities.value = facilityRes.data || []
  } catch (e) {
    console.error(e)
  }
}

// 视图切换
const handleViewModeChange = () => {
  if (viewMode.value === 'board' && pagination.pageSize < 100) {
    pagination.pageSize = 100
    pagination.page = 1
    loadData()
  }
}

// 搜索
const handleSearch = () => {
  pagination.page = 1
  loadData()
}

// 重置
const handleReset = () => {
  searchForm.status = ''
  searchForm.priority = ''
  searchForm.keyword = ''
  handleSearch()
}

// 创建
const handleCreate = () => {
  form.id = null
  form.title = ''
  form.description = ''
  form.category_id = null
  form.priority = 'normal'
  form.device_id = null
  form.facility_id = null
  form.assignee_id = null
  form.plan_date = ''
  form.estimated_hours = null
  dialogTitle.value = '创建工单'
  dialogVisible.value = true
}

// 查看
const handleView = async (row: any) => {
  try {
    const res = await getWorkOrderDetail(row.id)
    currentOrder.value = res.data.data
    detailVisible.value = true
    loadKnowledgeRecommend(row.title || '')
  } catch (e) {
    console.error(e)
  }
}

// 知识库：按工单标题关键词推荐
const loadKnowledgeRecommend = async (keyword: string) => {
  if (!keyword) {
    knowledgeArticles.value = []
    return
  }
  try {
    const res = await recommendKnowledge(keyword)
    knowledgeArticles.value = res?.data?.data || []
  } catch (e) {
    knowledgeArticles.value = []
  }
}

// 知识库：把已完成的工单沉淀为知识
const handleSaveKnowledge = async () => {
  if (!currentOrder.value) return
  if (!currentOrder.value.result) {
    ElMessage.warning('请先填写处理结果再沉淀为知识')
    return
  }
  kbSaving.value = true
  try {
    const title = `[案例] ${currentOrder.value.title}`
    const content = `工单编号：${currentOrder.value.order_no}\n分类：${currentOrder.value.category_name || '-'}\n优先级：${getPriorityLabel(currentOrder.value.priority)}\n处理结果：${currentOrder.value.result}\n用户反馈：${currentOrder.value.feedback || '-'}`
    await createKnowledge({
      title,
      category: currentOrder.value.category_name || '工单案例',
      content,
      source_order_id: currentOrder.value.id
    })
    ElMessage.success('已沉淀为知识，可在相关知识中查看')
    loadKnowledgeRecommend(currentOrder.value.title || '')
  } catch (e: any) {
    ElMessage.error(e?.message || '沉淀失败')
  } finally {
    kbSaving.value = false
  }
}

// 编辑
const handleEdit = (row: any) => {
  form.id = row.id
  form.title = row.title
  form.description = row.description || ''
  form.category_id = row.category_id
  form.priority = row.priority
  form.device_id = row.device_id
  form.facility_id = row.facility_id
  form.plan_date = row.plan_date
  dialogTitle.value = '编辑工单'
  dialogVisible.value = true
}

// 删除
const handleDelete = (row: any) => {
  ElMessageBox.confirm('确定删除该工单吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await deleteWorkOrder(row.id)
      ElMessage.success('删除成功')
      loadData()
      loadStats()
    } catch (e: any) {
      ElMessage.error(e.message || '删除失败')
    }
  })
}

// 提交表单
const handleSubmit = async () => {
  await formRef.value.validate(async (valid: boolean) => {
    if (!valid) return
    submitLoading.value = true
    try {
      if (form.id) {
        await updateWorkOrder(form.id, form)
        ElMessage.success('更新成功')
      } else {
        await createWorkOrder(form)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      loadData()
      loadStats()
    } catch (e: any) {
      ElMessage.error(e.message || '操作失败')
    } finally {
      submitLoading.value = false
    }
  })
}

// 指派
const handleAssign = (row: any) => {
  currentOrder.value = row
  assignForm.assignee_id = recommendedAssigneeId.value
  assignForm.remark = ''
  assignVisible.value = true
}

const submitAssign = async () => {
  if (!assignForm.assignee_id) {
    ElMessage.warning('请选择处理人')
    return
  }
  submitLoading.value = true
  try {
    await assignWorkOrder(currentOrder.value.id, assignForm)
    ElMessage.success('指派成功')
    assignVisible.value = false
    await loadDetail()
    loadData()
    loadStats()
  } catch (e: any) {
    ElMessage.error(e.message || '指派失败')
  } finally {
    submitLoading.value = false
  }
}

// 开始处理
const handleStart = async (row: any) => {
  try {
    await startWorkOrder(row.id)
    ElMessage.success('已开始处理')
    await loadDetail()
    loadData()
    loadStats()
  } catch (e: any) {
    ElMessage.error(e.message || '操作失败')
  }
}

// 完成处理
const handleComplete = (row: any) => {
  currentOrder.value = row
  completeForm.result = ''
  completeForm.actual_hours = null
  completeVisible.value = true
}

const submitComplete = async () => {
  if (!completeForm.result) {
    ElMessage.warning('请输入处理结果')
    return
  }
  submitLoading.value = true
  try {
    await completeWorkOrder(currentOrder.value.id, completeForm)
    ElMessage.success('提交成功')
    completeVisible.value = false
    await loadDetail()
    loadData()
    loadStats()
  } catch (e: any) {
    ElMessage.error(e.message || '提交失败')
  } finally {
    submitLoading.value = false
  }
}

// 验收
const handleVerify = (row: any, accept: boolean) => {
  currentOrder.value = row
  verifyForm.accept = accept
  verifyForm.satisfaction = 5
  verifyForm.feedback = ''
  verifyVisible.value = true
}

const submitVerify = async () => {
  submitLoading.value = true
  try {
    await verifyWorkOrder(currentOrder.value.id, verifyForm)
    ElMessage.success('验收成功')
    verifyVisible.value = false
    await loadDetail()
    loadData()
    loadStats()
  } catch (e: any) {
    ElMessage.error(e.message || '验收失败')
  } finally {
    submitLoading.value = false
  }
}

// 关闭工单
const handleClose = (row: any) => {
  currentOrder.value = row
  closeForm.remark = ''
  closeVisible.value = true
}

const submitClose = async () => {
  submitLoading.value = true
  try {
    await closeWorkOrder(currentOrder.value.id, closeForm)
    ElMessage.success('工单已关闭')
    closeVisible.value = false
    await loadDetail()
    loadData()
    loadStats()
  } catch (e: any) {
    ElMessage.error(e.message || '关闭失败')
  } finally {
    submitLoading.value = false
  }
}

// 添加评论
const handleAddComment = async () => {
  if (!commentContent.value.trim()) {
    ElMessage.warning('请输入评论内容')
    return
  }
  try {
    await addWorkOrderComment(currentOrder.value.id, {
      content: commentContent.value,
      comment_type: 'normal'
    })
    ElMessage.success('评论成功')
    commentContent.value = ''
    await loadDetail()
  } catch (e: any) {
    ElMessage.error(e.message || '评论失败')
  }
}

// 附件：上传前校验
const handleBeforeUpload = (file: File) => {
  const maxSize = 10 * 1024 * 1024
  if (file.size > maxSize) {
    ElMessage.warning('单个文件不能超过 10MB')
    return false
  }
  return true
}

// 附件：执行上传
const handleUpload = async (options: any) => {
  if (!currentOrder.value) return
  uploading.value = true
  try {
    await uploadWorkOrderAttachment(currentOrder.value.id, options.file)
    ElMessage.success('上传成功')
    await loadDetail()
  } catch (e: any) {
    ElMessage.error(e?.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

// 附件：下载
const handleDownload = async (att: any) => {
  try {
    const res: any = await downloadWorkOrderAttachment(att.id)
    const blob = new Blob([res.data])
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = att.file_name
    a.click()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error('下载失败')
  }
}

// 附件：删除
const handleDeleteAttachment = (att: any) => {
  ElMessageBox.confirm('确定删除该附件吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await deleteWorkOrderAttachment(att.id)
      ElMessage.success('删除成功')
      await loadDetail()
    } catch (e: any) {
      ElMessage.error(e?.message || '删除失败')
    }
  })
}

// 附件：文件大小格式化
const formatFileSize = (bytes?: number) => {
  if (!bytes && bytes !== 0) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

// 加载详情
const loadDetail = async () => {
  if (!currentOrder.value) return
  try {
    const res = await getWorkOrderDetail(currentOrder.value.id)
    currentOrder.value = res.data.data
  } catch (e) {
    console.error(e)
  }
}

// 设备选择变化
const handleDeviceChange = (deviceId: number) => {
  if (deviceId) {
    const device = devices.value.find(d => d.id === deviceId)
    if (device?.rack_id) {
      form.facility_id = device.rack_id
    }
  }
}

// 判断权限
const canEdit = (row: any) => {
  return row.creator_id === userId.value && ['pending', 'assigned'].includes(row.status)
}

const canDelete = (row: any) => {
  return row.creator_id === userId.value && ['pending', 'closed'].includes(row.status)
}

// 格式化日期
const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

// 优先级
const getPriorityType = (priority: string) => {
  const map: Record<string, string> = {
    low: 'info',
    normal: '',
    high: 'warning',
    urgent: 'danger'
  }
  return map[priority] || ''
}

const getPriorityLabel = (priority: string) => {
  const map: Record<string, string> = {
    low: '低',
    normal: '普通',
    high: '高',
    urgent: '紧急'
  }
  return map[priority] || priority
}

// 状态
const getStatusType = (status: string) => {
  const map: Record<string, string> = {
    pending: 'warning',
    awaiting_approval: 'danger',
    assigned: 'primary',
    processing: 'warning',
    pending_verify: 'info',
    completed: 'success',
    closed: 'info'
  }
  return map[status] || ''
}

const getStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    pending: '待分配',
    awaiting_approval: '待审批',
    assigned: '已指派',
    processing: '处理中',
    pending_verify: '待验收',
    completed: '已完成',
    closed: '已关闭'
  }
  return map[status] || status
}

const loadAutoRules = async () => {
  rulesLoading.value = true
  try {
    const res = await getAutoRules()
    autoRules.value = (res as any)?.data?.data || []
  } catch (e) {
    console.error(e)
  } finally {
    rulesLoading.value = false
  }
}

const handleOpenRules = () => {
  rulesVisible.value = true
  loadAutoRules()
}

const handleNewRule = () => {
  Object.assign(ruleForm, {
    id: null, name: '', enabled: true, match_keyword: '',
    match_category_id: null, match_priority: '', action_set_priority: '',
    action_assign_user_id: null, action_auto_complete: false, sort: 0
  })
  ruleDialogVisible.value = true
}

const handleEditRule = (row: any) => {
  Object.assign(ruleForm, {
    id: row.id, name: row.name, enabled: !!row.enabled, match_keyword: row.match_keyword || '',
    match_category_id: row.match_category_id ?? null, match_priority: row.match_priority || '',
    action_set_priority: row.action_set_priority || '', action_assign_user_id: row.action_assign_user_id ?? null,
    action_auto_complete: !!row.action_auto_complete, sort: row.sort || 0
  })
  ruleDialogVisible.value = true
}

const toggleRule = async (row: any) => {
  try {
    await updateAutoRule(row.id, { enabled: row.enabled })
    ElMessage.success(row.enabled ? '规则已启用' : '规则已停用')
  } catch (e: any) {
    row.enabled = !row.enabled
    ElMessage.error(e?.message || '操作失败')
  }
}

const submitRule = async () => {
  if (!ruleForm.name.trim()) {
    ElMessage.warning('请输入规则名称')
    return
  }
  ruleSaving.value = true
  try {
    const payload: any = {
      name: ruleForm.name.trim(),
      enabled: ruleForm.enabled,
      match_keyword: ruleForm.match_keyword?.trim() || null,
      match_category_id: ruleForm.match_category_id ?? null,
      match_priority: ruleForm.match_priority || null,
      action_set_priority: ruleForm.action_set_priority || null,
      action_assign_user_id: ruleForm.action_assign_user_id ?? null,
      action_auto_complete: ruleForm.action_auto_complete,
      sort: ruleForm.sort || 0
    }
    if (ruleForm.id) {
      await updateAutoRule(ruleForm.id, payload)
      ElMessage.success('规则已更新')
    } else {
      await createAutoRule(payload)
      ElMessage.success('规则已创建')
    }
    ruleDialogVisible.value = false
    loadAutoRules()
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    ruleSaving.value = false
  }
}

const handleDeleteRule = (row: any) => {
  ElMessageBox.confirm(`确定删除规则「${row.name}」吗？`, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await deleteAutoRule(row.id)
      ElMessage.success('删除成功')
      loadAutoRules()
    } catch (e: any) {
      ElMessage.error(e?.message || '删除失败')
    }
  })
}

const handleApprove = async (row: any) => {
  try {
    await approveWorkOrder(row.id)
    ElMessage.success('审批通过')
    await loadDetail()
    loadData()
    loadStats()
  } catch (e: any) {
    ElMessage.error(e?.message || '审批失败')
  }
}

const handleReject = (row: any) => {
  currentOrder.value = row
  rejectForm.reason = ''
  rejectVisible.value = true
}

const submitReject = async () => {
  if (!currentOrder.value) return
  rejecting.value = true
  try {
    await rejectWorkOrder(currentOrder.value.id, { reason: rejectForm.reason })
    ElMessage.success('已拒绝')
    rejectVisible.value = false
    await loadDetail()
    loadData()
    loadStats()
  } catch (e: any) {
    ElMessage.error(e?.message || '拒绝失败')
  } finally {
    rejecting.value = false
  }
}

// 分类配置
const handleOpenCategories = () => {
  categoriesVisible.value = true
  resetCatForm()
  loadOptions()
}

const resetCatForm = () => {
  Object.assign(catForm, { id: null, name: '', code: '', need_approval: false })
}

const editCategory = (row: any) => {
  Object.assign(catForm, {
    id: row.id, name: row.name, code: row.code, need_approval: !!row.need_approval
  })
}

const submitCategory = async () => {
  if (!catForm.name.trim() || !catForm.code.trim()) {
    ElMessage.warning('请输入分类名称和编码')
    return
  }
  const payload = {
    name: catForm.name.trim(),
    code: catForm.code.trim(),
    need_approval: catForm.need_approval
  }
  try {
    if (catForm.id) {
      await updateWorkOrderCategory(catForm.id, payload)
      ElMessage.success('分类已更新')
    } else {
      await createWorkOrderCategory(payload)
      ElMessage.success('分类已新增')
    }
    resetCatForm()
    await loadOptions()
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  }
}

const toggleCategoryApproval = async (row: any) => {
  try {
    await updateWorkOrderCategory(row.id, { need_approval: row.need_approval })
    ElMessage.success(row.need_approval ? '该分类已开启审批' : '该分类已关闭审批')
  } catch (e: any) {
    row.need_approval = !row.need_approval
    ElMessage.error(e?.message || '操作失败')
  }
}

const removeCategory = (row: any) => {
  ElMessageBox.confirm(`确定删除分类「${row.name}」吗？`, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await deleteWorkOrderCategory(row.id)
      ElMessage.success('删除成功')
      await loadOptions()
    } catch (e: any) {
      ElMessage.error(e?.message || '删除失败')
    }
  })
}

onMounted(() => {
  loadStats()
  loadData()
  loadOptions()
})
</script>

<style scoped>
.work-order-container {
  padding: 20px;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 20px;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 20px;
  font-size: 28px;
  color: white;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  color: #909399;
  margin-top: 5px;
}

.search-card {
  margin-bottom: 20px;
}

.search-form {
  margin-bottom: 0;
}

.table-card {
  margin-bottom: 20px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.text-muted {
  color: #909399;
}

.form-tip {
  margin-left: 10px;
  color: #909399;
}

.order-detail {
  padding: 10px 0;
}

.process-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #eee;
}

.process-section h4 {
  margin-bottom: 15px;
}

.action-buttons {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #eee;
  display: flex;
  gap: 10px;
}

.comment-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #eee;
}

.comment-section h4 {
  margin-bottom: 15px;
}

.attachment-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #eee;
}

.attachment-section h4 {
  margin-bottom: 15px;
}

.attachment-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.attachment-item {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #f5f7fa;
  border-radius: 6px;
  padding: 8px 12px;
}

.attachment-item .att-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.attachment-item .att-size {
  color: #909399;
  font-size: 12px;
}

.no-attachment {
  color: #909399;
  font-size: 13px;
  margin-top: 10px;
}

.upload-hint {
  color: #409eff;
  font-size: 13px;
  margin-top: 8px;
}

.view-toggle {
  margin-bottom: 15px;
}

.board-view {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 8px;
}

.board-column {
  flex: 1;
  min-width: 200px;
  background: #f5f7fa;
  border-radius: 8px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  max-height: 560px;
}

.board-column-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  padding: 4px 6px 10px;
}

.col-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.col-count {
  margin-left: auto;
  background: #e4e7ed;
  border-radius: 10px;
  padding: 0 8px;
  font-size: 12px;
  line-height: 18px;
}

.board-column-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
}

.board-card {
  background: #fff;
  border-radius: 8px;
  padding: 10px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  cursor: pointer;
  transition: box-shadow 0.2s;
}

.board-card:hover {
  box-shadow: 0 3px 8px rgba(0,0,0,0.15);
}

.board-card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.board-no {
  color: #909399;
  font-size: 12px;
}

.board-title {
  font-size: 14px;
  font-weight: 500;
  margin: 8px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.board-meta {
  display: flex;
  justify-content: space-between;
  color: #909399;
  font-size: 12px;
}

.board-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  color: #909399;
  font-size: 12px;
}

.board-empty {
  color: #c0c4cc;
  text-align: center;
  font-size: 13px;
  padding: 20px 0;
}

.assign-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.assign-load {
  color: #909399;
  font-size: 12px;
}

.assign-tip {
  color: #67c23a;
  font-size: 13px;
  margin-top: 6px;
}

.knowledge-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #eee;
}

.knowledge-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.knowledge-head h4 {
  margin: 0;
  line-height: 32px;
}

.knowledge-list {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.knowledge-item {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #f5f7fa;
  border-radius: 6px;
  padding: 8px 12px;
}

.knowledge-item .kb-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}

.knowledge-item .kb-category {
  color: #409eff;
  background: #ecf5ff;
  border-radius: 4px;
  padding: 1px 8px;
  font-size: 12px;
}

.knowledge-empty {
  color: #c0c4cc;
  font-size: 13px;
  margin-top: 10px;
}

.rules-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.rules-tip {
  color: #909399;
  font-size: 12px;
}

.rule-action {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.auto-complete-tag {
  color: #67c23a;
  background: #f0f9eb;
  border-radius: 4px;
  padding: 1px 8px;
  font-size: 12px;
}

.approval-hint {
  color: #e6a23c;
  font-size: 13px;
  line-height: 32px;
}

.cat-form {
  margin-bottom: 12px;
}

.cat-table {
  margin-top: 8px;
}
</style>