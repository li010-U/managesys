<template>
  <div class="work-order-container">
    <el-row :gutter="20" class="stats-row">
      <el-col :span="5"><el-card shadow="hover" class="stat-card" @click="statsFilter('')"><div class="stat-icon gradient-primary"><el-icon><Document /></el-icon></div><div class="stat-info"><div class="stat-value">{{ stats.total }}</div><div class="stat-label">工单总数</div></div></el-card></el-col>
      <el-col :span="5"><el-card shadow="hover" class="stat-card" @click="statsFilter('pending')"><div class="stat-icon gradient-warning"><el-icon><Clock /></el-icon></div><div class="stat-info"><div class="stat-value">{{ stats.pending }}</div><div class="stat-label">待处理</div></div></el-card></el-col>
      <el-col :span="5"><el-card shadow="hover" class="stat-card" @click="statsFilter('processing')"><div class="stat-icon gradient-info"><el-icon><Loading /></el-icon></div><div class="stat-info"><div class="stat-value">{{ stats.processing }}</div><div class="stat-label">处理中</div></div></el-card></el-col>
      <el-col :span="5"><el-card shadow="hover" class="stat-card" @click="statsFilter('completed')"><div class="stat-icon gradient-success"><el-icon><Check /></el-icon></div><div class="stat-info"><div class="stat-value">{{ stats.completed }}</div><div class="stat-label">已完成</div></div></el-card></el-col>
      <el-col :span="4"><el-card shadow="hover" class="stat-card stat-card-alert" @click="statsFilter('overdue')"><div class="stat-icon gradient-danger"><el-icon><WarningFilled /></el-icon></div><div class="stat-info"><div class="stat-value">{{ stats.sla_overdue || 0 }}</div><div class="stat-label">逾期工单</div></div></el-card></el-col>
    </el-row>
    <el-card class="search-card"><el-form :inline="true" :model="searchForm"><el-form-item label="状态"><el-select v-model="searchForm.status" clearable style="width:120px"><el-option label="全部" value=""/><el-option label="待分配" value="pending"/><el-option label="处理中" value="processing"/><el-option label="已完成" value="completed"/><el-option label="已关闭" value="closed"/></el-select></el-form-item><el-form-item label="关键词"><el-input v-model="searchForm.keyword" clearable style="width:180px"/></el-form-item><el-form-item><el-button type="primary" @click="handleSearch">搜索</el-button><el-button @click="handleReset">重置</el-button><el-button type="primary" @click="handleCreate">创建工单</el-button><el-button @click="categoryVisible=true">分类管理</el-button></el-form-item></el-form><div v-if="selectedRows.length>0" class="search-actions"><el-button type="warning" @click="handleBatchAssign">批量分配({{selectedRows.length}})</el-button><el-button type="info" @click="handleBatchExport">导出</el-button></div></el-card>
    <el-card class="table-card"><el-table :data="workOrders" v-loading="loading" stripe @selection-change="handleSelectionChange"><el-table-column type="selection" width="50"/><el-table-column prop="order_no" label="工单编号" width="160"><template #default="{row}"><el-link type="primary" @click="handleDetail(row)">{{row.order_no}}</el-link></template></el-table-column><el-table-column prop="title" label="工单标题" min-width="200" show-overflow-tooltip/><el-table-column prop="priority" label="优先级" width="80"><template #default="{row}"><el-tag :type="getPriorityType(row.priority)" size="small">{{getPriorityLabel(row.priority)}}</el-tag></template></el-table-column><el-table-column prop="status" label="状态" width="90"><template #default="{row}"><el-tag :type="getStatusType(row.status)" size="small">{{getStatusLabel(row.status)}}</el-tag></template></el-table-column><el-table-column prop="assignee_name" label="处理人" width="100"><template #default="{row}">{{row.assignee_name||'待分配'}}</template></el-table-column><el-table-column prop="creator_name" label="创建人" width="90"/><el-table-column prop="created_at" label="创建时间" width="160"><template #default="{row}">{{formatDate(row.created_at)}}</template></el-table-column><el-table-column label="操作" width="150" fixed="right"><template #default="{row}"><el-button link type="primary" @click="handleDetail(row)">详情</el-button><el-button v-if="canEdit(row)" link type="warning" @click="handleEdit(row)">编辑</el-button><el-button v-if="canDelete(row)" link type="danger" @click="handleDelete(row)">删除</el-button></template></el-table-column></el-table><div class="pagination"><span class="pagination-info">共{{pagination.total}}条</span><el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.pageSize" :page-sizes="[10,20,50]" :total="pagination.total" layout="sizes,prev,pager,next" @size-change="loadData" @current-change="loadData"/></div></el-card>
    <el-dialog v-model="formVisible" :title="isEdit?'编辑工单':'创建工单'" width="500px"><el-form :model="form" :rules="formRules" ref="formRef" label-width="80px"><el-form-item label="标题" prop="title"><el-input v-model="form.title"/></el-form-item><el-form-item label="优先级"><el-select v-model="form.priority"><el-option label="低" value="low"/><el-option label="普通" value="normal"/><el-option label="高" value="high"/><el-option label="紧急" value="urgent"/></el-select></el-form-item><el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="3"/></el-form-item></el-form><template #footer><el-button @click="formVisible=false">取消</el-button><el-button type="primary" :loading="submitLoading" @click="submitForm">确定</el-button></template></el-dialog>
    <el-dialog v-model="detailVisible" title="工单详情" width="700px"><div v-if="currentOrder"><el-descriptions :column="2" border><el-descriptions-item label="工单编号">{{currentOrder.order_no}}</el-descriptions-item><el-descriptions-item label="状态"><el-tag :type="getStatusType(currentOrder.status)">{{getStatusLabel(currentOrder.status)}}</el-tag></el-descriptions-item><el-descriptions-item label="标题" :span="2">{{currentOrder.title}}</el-descriptions-item><el-descriptions-item label="处理人">{{currentOrder.assignee_name||'待分配'}}</el-descriptions-item><el-descriptions-item label="创建人">{{currentOrder.creator_name}}</el-descriptions-item><el-descriptions-item label="创建时间">{{formatDate(currentOrder.created_at)}}</el-descriptions-item></el-descriptions><div class="detail-section"><h4>处理记录</h4><el-timeline><el-timeline-item v-for="msg in currentOrder.messages" :key="msg.id" :timestamp="formatDate(msg.created_at)"><p>{{msg.user_name}}:{{msg.content}}</p></el-timeline-item><el-timeline-item v-if="!currentOrder.messages?.length">暂无记录</el-timeline-item></el-timeline></div><div class="action-buttons"><template v-if="currentOrder.status==='pending'"><el-button type="primary" @click="openAssignDialog">分配</el-button></template><template v-else-if="['assigned','processing'].includes(currentOrder.status)"><el-button v-if="currentOrder.assignee_id===userId" type="success" @click="handleStart">开始</el-button><el-button v-if="currentOrder.assignee_id===userId" type="warning" @click="handleComplete">完成</el-button></template><template v-else-if="currentOrder.status==='pending_verify'"><el-button v-if="currentOrder.creator_id===userId" type="success" @click="handleVerify(true)">通过</el-button><el-button v-if="currentOrder.creator_id===userId" type="danger" @click="handleVerify(false)">不通过</el-button></template><el-button @click="handleClose">关闭</el-button></div><div class="comment-section"><h4>添加评论</h4><el-input v-model="commentContent" type="textarea" :rows="2"/><el-button type="primary" size="small" class="mt-2" @click="handleAddComment">提交</el-button></div></div><template #footer><el-button @click="detailVisible=false">关闭</el-button></template></el-dialog>
    <el-dialog v-model="assignVisible" title="分配处理人" width="400px"><el-form><el-form-item label="处理人"><el-select v-model="assignForm.assignee_id" filterable style="width:100%"><el-option v-for="u in users" :key="u.id" :label="u.real_name||u.username" :value="u.id"/></el-select></el-form-item></el-form><template #footer><el-button @click="assignVisible=false">取消</el-button><el-button type="primary" :loading="submitLoading" @click="submitAssign">确定</el-button></template></el-dialog>
    <el-dialog v-model="batchAssignVisible" title="批量分配" width="400px"><p class="text-muted">已选{{selectedRows.length}}条</p><el-form><el-form-item label="处理人"><el-select v-model="batchAssignForm.assignee_id" filterable style="width:100%"><el-option v-for="u in users" :key="u.id" :label="u.real_name||u.username" :value="u.id"/></el-select></el-form-item></el-form><template #footer><el-button @click="batchAssignVisible=false">取消</el-button><el-button type="primary" :loading="submitLoading" @click="submitBatchAssign">确定</el-button></template></el-dialog>
    <el-dialog v-model="completeVisible" title="完成处理" width="400px"><el-form><el-form-item label="结果"><el-input v-model="completeForm.result" type="textarea" :rows="4"/></el-form-item></el-form><template #footer><el-button @click="completeVisible=false">取消</el-button><el-button type="primary" :loading="submitLoading" @click="submitComplete">确定</el-button></template></el-dialog>
    <el-dialog v-model="verifyVisible" title="验收确认" width="400px"><el-form label-width="80px"><el-form-item label="结果"><el-radio-group v-model="verifyForm.accept"><el-radio :label="true">通过</el-radio><el-radio :label="false">不通过</el-radio></el-radio-group></el-form-item><el-form-item label="满意度"><el-rate v-model="verifyForm.satisfaction" allow-half/></el-form-item><el-form-item label="反馈"><el-input v-model="verifyForm.feedback" type="textarea" :rows="2"/></el-form-item></el-form><template #footer><el-button @click="verifyVisible=false">取消</el-button><el-button type="primary" :loading="submitLoading" @click="submitVerify">确定</el-button></template></el-dialog>
    <el-dialog v-model="closeVisible" title="关闭工单" width="400px"><el-form><el-form-item label="原因"><el-input v-model="closeForm.remark" type="textarea" :rows="3"/></el-form-item></el-form><template #footer><el-button @click="closeVisible=false">取消</el-button><el-button type="primary" :loading="submitLoading" @click="submitClose">确定</el-button></template></el-dialog>
  
    <el-dialog v-model="categoryVisible" title="分类管理" width="500px">
      <div style="margin-bottom:12px"><el-button type="primary" size="small" @click="openCategoryDialog()">新增分类</el-button></div>
      <el-table :data="categories" stripe size="small">
        <el-table-column prop="name" label="名称" width="120"/>
        <el-table-column prop="code" label="编码" width="100"/>
        <el-table-column prop="sort" label="排序" width="60"/>
        <el-table-column label="操作" width="140"><template #default="{row}"><el-button link type="warning" size="small" @click="openCategoryDialog(row)">编辑</el-button><el-button link type="danger" size="small" @click="deleteCategory(row.id)">删除</el-button></template></el-table-column>
      </el-table>
    </el-dialog>
    <el-dialog v-model="categoryFormVisible" :title="categoryEdit.id?'编辑分类':'新增分类'" width="400px">
      <el-form :model="categoryEdit" label-width="80px">
        <el-form-item label="名称" required><el-input v-model="categoryEdit.name"/></el-form-item>
        <el-form-item label="编码"><el-input v-model="categoryEdit.code" :disabled="!!categoryEdit.id"/></el-form-item>
        <el-form-item label="排序"><el-input-number v-model="categoryEdit.sort" :min="0"/></el-form-item>
      </el-form>
      <template #footer><el-button @click="categoryFormVisible=false">取消</el-button><el-button type="primary" @click="saveCategory">确定</el-button></template>
    </el-dialog>
  </div>
</template>
<script setup lang="ts">
import {ref,reactive,onMounted,computed} from "vue"
import {ElMessage,ElMessageBox} from "element-plus"
import {Document,Clock,Loading,Check,Plus,Search,Refresh,User,Download,WarningFilled} from "@element-plus/icons-vue"
import {getWorkOrders,getWorkOrderStats,getWorkOrderApi,createWorkOrder,updateWorkOrder,deleteWorkOrder,assignWorkOrder,startWorkOrder,completeWorkOrder,verifyWorkOrder,closeWorkOrder,addWorkOrderComment,getWorkOrderCategories,createWorkOrderCategory,updateWorkOrderCategory,deleteWorkOrderCategory} from "@/api/workOrder"
import {getUserList} from "@/api/user"
import {useAuthStore} from "@/stores/auth"
const auth=useAuthStore()
const userId=computed(()=>auth.user?.id)
const loading=ref(false)
const workOrders=ref<any[]>([])
const users=ref<any[]>([])
const categories=ref<any[]>([])
const selectedRows=ref<any[]>([])
const stats=reactive({total:0,pending:0,processing:0,completed:0,sla_overdue:0})
const searchForm=reactive({status:"",keyword:""})
const pagination=reactive({page:1,pageSize:20,total:0})
const formRef=ref()
const formVisible=ref(false)
const isEdit=ref(false)
const submitLoading=ref(false)
const form=reactive({id:null as number|null,title:"",priority:"normal",description:""})
const formRules={title:[{required:true,message:"请输入标题",trigger:"blur"}]}
const detailVisible=ref(false)
const currentOrder=ref<any>(null)
const commentContent=ref("")
const assignVisible=ref(false)
const assignForm=reactive({assignee_id:null as number|null})
const batchAssignVisible=ref(false)
const batchAssignForm=reactive({assignee_id:null as number|null})
const completeVisible=ref(false)
const completeForm=reactive({result:""})
const verifyVisible=ref(false)
const verifyForm=reactive({accept:true,satisfaction:5,feedback:""})
const closeVisible=ref(false)
const closeForm=reactive({remark:""})
const loadStats=async()=>{try{const r=await getWorkOrderStats();Object.assign(stats,r.data||{})}catch(e){console.error(e)}}
const loadData=async()=>{loading.value=true;try{const params:any={page:pagination.page,page_size:pagination.pageSize};if(searchForm.status)params.status=searchForm.status;if(searchForm.keyword)params.keyword=searchForm.keyword;const r=await getWorkOrders(params);workOrders.value=r.data?.items||[];pagination.total=r.data?.total||workOrders.value.length}catch(e:any){ElMessage.error(e.message)}finally{loading.value=false}}
const loadOptions=async()=>{try{const r=await getUserList({});users.value=r.data||[]}catch(e){}}
const handleSearch=()=>{pagination.page=1;loadData()}
const handleReset=()=>{searchForm.status="";searchForm.keyword="";handleSearch()}
const statsFilter=(s:string)=>{searchForm.status=s;handleSearch()}
const handleSelectionChange=(s:any[])=>{selectedRows.value=s}

const categoryVisible=ref(false)
const categoryFormVisible=ref(false)
const categoryEdit=reactive({id:null as number|null,name:"",code:"",icon:"",sort:0})
const loadCategories=async()=>{try{const r=await getWorkOrderCategories();categories.value=r.data||[]}catch(e){console.error(e)}}
const saveCategory=async()=>{if(!categoryEdit.name){ElMessage.warning("请输入分类名称");return}submitLoading.value=true;try{const d={name:categoryEdit.name,code:categoryEdit.code,icon:categoryEdit.icon,sort:categoryEdit.sort};if(categoryEdit.id){await updateWorkOrderCategory(categoryEdit.id,d);ElMessage.success("更新成功")}else{await createWorkOrderCategory(d);ElMessage.success("创建成功")}categoryFormVisible.value=false;await loadCategories()}catch(e:any){ElMessage.error(e.message)}finally{submitLoading.value=false}}
const deleteCategory=async(id:number)=>{try{await ElMessageBox.confirm("确定删除?","提示",{type:"warning"});await deleteWorkOrderCategory(id);ElMessage.success("删除成功");await loadCategories()}catch(e:any){if(e!=="cancel")ElMessage.error(e.message)}}
const openCategoryDialog=(row?:any)=>{if(row){Object.assign(categoryEdit,{id:row.id,name:row.name,code:row.code,icon:row.icon||"",sort:row.sort||0})}else{categoryEdit.id=null;categoryEdit.name="";categoryEdit.code="";categoryEdit.icon="";categoryEdit.sort=0}categoryFormVisible.value=true}
const handleCreate=()=>{isEdit.value=false;form.id=null;form.title="";form.priority="normal";form.description="";formVisible.value=true}
const handleEdit=(row:any)=>{isEdit.value=true;Object.assign(form,{id:row.id,title:row.title,priority:row.priority,description:row.description});formVisible.value=true}
const submitForm=async()=>{try{await formRef.value.validate();submitLoading.value=true;try{if(isEdit.value){await updateWorkOrder(form.id!,form);ElMessage.success("更新成功")}else{await createWorkOrder(form);ElMessage.success("创建成功")}formVisible.value=false;loadData();loadStats()}catch(e:any){ElMessage.error(e.message)}finally{submitLoading.value=false}}catch(e){}}
const handleDetail=async(row:any)=>{currentOrder.value=row;try{const r=await getWorkOrderApi(row.id);currentOrder.value=r.data}catch(e){}detailVisible.value=true}
const openAssignDialog=()=>{assignForm.assignee_id=null;assignVisible.value=true}
const submitAssign=async()=>{if(!assignForm.assignee_id){ElMessage.warning("请选择处理人");return}submitLoading.value=true;try{await assignWorkOrder(currentOrder.value.id,assignForm);ElMessage.success("分配成功");assignVisible.value=false;await loadDetail();loadData();loadStats()}catch(e:any){ElMessage.error(e.message)}finally{submitLoading.value=false}}
const handleBatchAssign=()=>{batchAssignForm.assignee_id=null;batchAssignVisible.value=true}
const submitBatchAssign=async()=>{if(!batchAssignForm.assignee_id){ElMessage.warning("请选择处理人");return}submitLoading.value=true;try{for(const r of selectedRows.value){await assignWorkOrder(r.id,batchAssignForm)}ElMessage.success("批量分配成功");batchAssignVisible.value=false;selectedRows.value=[];loadData()}catch(e:any){ElMessage.error(e.message)}finally{submitLoading.value=false}}
const handleBatchExport=()=>{ElMessage.info("已选中 "+selectedRows.value.length+" 条数据")}
const handleDelete=async(row:any)=>{try{await ElMessageBox.confirm("确定删除?","提示",{type:"warning"});await deleteWorkOrder(row.id);ElMessage.success("删除成功");loadData();loadStats()}catch(e:any){if(e!=="cancel")ElMessage.error(e.message)}}
const handleStart=async()=>{submitLoading.value=true;try{await startWorkOrder(currentOrder.value.id);ElMessage.success("已开始");await loadDetail();loadData()}catch(e:any){ElMessage.error(e.message)}finally{submitLoading.value=false}}
const handleComplete=()=>{completeForm.result="";completeVisible.value=true}
const submitComplete=async()=>{if(!completeForm.result.trim()){ElMessage.warning("请输入结果");return}submitLoading.value=true;try{await completeWorkOrder(currentOrder.value.id,completeForm);ElMessage.success("已完成");completeVisible.value=false;await loadDetail();loadData()}catch(e:any){ElMessage.error(e.message)}finally{submitLoading.value=false}}
const handleVerify=(accept:boolean)=>{verifyForm.accept=accept;verifyForm.satisfaction=5;verifyForm.feedback="";verifyVisible.value=true}
const submitVerify=async()=>{submitLoading.value=true;try{await verifyWorkOrder(currentOrder.value.id,verifyForm);ElMessage.success(verifyForm.accept?"验收通过":"验收不通过");verifyVisible.value=false;await loadDetail();loadData()}catch(e:any){ElMessage.error(e.message)}finally{submitLoading.value=false}}
const handleClose=()=>{closeForm.remark="";closeVisible.value=true}
const submitClose=async()=>{submitLoading.value=true;try{await closeWorkOrder(currentOrder.value.id,closeForm);ElMessage.success("已关闭");closeVisible.value=false;await loadDetail();loadData()}catch(e:any){ElMessage.error(e.message)}finally{submitLoading.value=false}}
const handleAddComment=async()=>{if(!commentContent.value.trim()){ElMessage.warning("请输入评论");return}try{await addWorkOrderComment(currentOrder.value.id,{content:commentContent.value});ElMessage.success("评论成功");commentContent.value="";await loadDetail()}catch(e:any){ElMessage.error(e.message)}}
const loadDetail=async()=>{if(!currentOrder.value)return;try{const r=await getWorkOrderApi(currentOrder.value.id);currentOrder.value=r.data}catch(e){}}
const canEdit=(row:any)=>row.creator_id===userId.value&&["pending","assigned"].includes(row.status)
const canDelete=(row:any)=>row.creator_id===userId.value&&["pending","closed"].includes(row.status)
const formatDate=(d:string)=>d?new Date(d).toLocaleString("zh-CN"):"-"
const getPriorityType=(p:string)=>({low:"info",normal:"",high:"warning",urgent:"danger"})[p]||""
const getPriorityLabel=(p:string)=>({low:"低",normal:"普通",high:"高",urgent:"紧急"})[p]||p
const getStatusType=(s:string)=>({pending:"warning",assigned:"primary",processing:"warning",pending_verify:"info",completed:"success",closed:"info"})[s]||""
const getStatusLabel=(s:string)=>({pending:"待分配",assigned:"已指派",processing:"处理中",pending_verify:"待验收",completed:"已完成",closed:"已关闭"})[s]||s
onMounted(()=>{loadStats();loadData();loadOptions();loadCategories()})
</script>
<style scoped>
.work-order-container{padding:20px}.stats-row{margin-bottom:20px}.stat-card{display:flex;align-items:center;padding:20px;cursor:pointer;transition:transform .2s}.stat-card:hover{transform:translateY(-2px)}.stat-card-alert{border:2px solid #f56c6c}.stat-icon{width:56px;height:56px;border-radius:12px;display:flex;align-items:center;justify-content:center;margin-right:16px;font-size:26px;color:white}.gradient-primary{background:linear-gradient(135deg,#409eff,#66b1ff)}.gradient-warning{background:linear-gradient(135deg,#e6a23c,#ebb563)}.gradient-info{background:linear-gradient(135deg,#909399,#a6a9ad)}.gradient-success{background:linear-gradient(135deg,#67c23a,#85ce61)}.gradient-danger{background:linear-gradient(135deg,#f56c6c,#f78989)}.stat-info{flex:1}.stat-value{font-size:28px;font-weight:bold;color:#303133}.stat-label{color:#909399;margin-top:4px;font-size:13px}.search-card,.table-card{margin-bottom:20px}.search-actions{margin-top:12px;padding-top:12px;border-top:1px solid #ebeef5}.mt-2{margin-top:8px}.text-muted{color:#909399}.pagination{margin-top:20px;display:flex;justify-content:space-between;align-items:center}.pagination-info{color:#909399;font-size:13px}.detail-section{margin-top:20px;padding-top:16px;border-top:1px solid #eee}.detail-section h4{margin-bottom:12px;color:#303133}.action-buttons{margin-top:20px;padding-top:16px;border-top:1px solid #eee;display:flex;gap:10px}.comment-section{margin-top:16px;padding:12px;background:#f5f7fa;border-radius:8px}.comment-section h4{margin-bottom:10px}
</style>