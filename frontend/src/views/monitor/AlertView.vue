<template>
  <div class="alert-page">
    <div class="page-header">
      <div>
        <h3 class="page-title">告警管理</h3>
        <p class="page-desc">告警规则配置、告警列表查看与处理</p>
      </div>
    </div>
    <el-tabs v-model="activeTab" class="alert-tabs">
      <el-tab-pane label="告警规则" name="rules">
        <el-card shadow="never" class="toolbar-card">
          <div class="toolbar-bar">
            <div class="toolbar-left">
              <el-input v-model="ruleSearch" placeholder="搜索规则..." :prefix-icon="Search" clearable size="small" style="width:200px" @input="loadRules" />
              <el-select v-model="ruleEnabled" placeholder="状态" clearable size="small" style="width:120px" @change="loadRules">
                <el-option label="已启用" :value="true" />
                <el-option label="已禁用" :value="false" />
              </el-select>
            </div>
            <div class="toolbar-right">
              <el-button type="primary" :icon="Plus" size="small" @click="openRuleDialog()">新增规则</el-button>
            </div>
          </div>
        </el-card>
        <el-card shadow="never" class="table-card">
          <el-table :data="ruleList" stripe border size="small" v-loading="ruleLoading">
            <el-table-column prop="name" label="规则名称" min-width="140" />
            <el-table-column prop="code" label="规则编码" width="120" />
            <el-table-column prop="metric" label="指标" width="100">
              <template #default="{ row }"><el-tag size="small" type="info">{{ metricLabel(row.metric) }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="condition" label="条件" width="80"><template #default="{ row }">{{ conditionLabel(row.condition) }}</template></el-table-column>
            <el-table-column prop="threshold" label="阈值" width="80"><template #default="{ row }">{{ row.threshold }}{{ metricUnit(row.metric) }}</template></el-table-column>
            <el-table-column prop="alert_level" label="级别" width="90">
              <template #default="{ row }"><el-tag size="small" :type="levelType(row.alert_level)">{{ levelLabel(row.alert_level) }}</el-tag></template>
            </el-table-column>
            <el-table-column label="启用" width="80">
              <template #default="{ row }"><el-switch :model-value="row.enabled" size="small" @change="toggleRule(row)" /></template>
            </el-table-column>
            <el-table-column label="触发" width="80" align="center"><template #default="{ row }"><span style="font-weight:600">{{ row.alert_count }}</span></template></el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button :icon="Edit" size="small" text @click="openRuleDialog(row)">编辑</el-button>
                <el-button :icon="Delete" size="small" text type="danger" @click="deleteRule(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination v-model:current-page="rulePage" v-model:page-size="rulePageSize" :total="ruleTotal" :page-sizes="[10,20,50]" layout="total, sizes, prev, pager, next" small style="margin-top:12px;justify-content:center" />
        </el-card>
      </el-tab-pane>
      <el-tab-pane label="告警列表" name="alerts">
        <el-card shadow="never" class="toolbar-card">
          <div class="toolbar-bar">
            <div class="toolbar-left">
              <el-input v-model="alertSearch" placeholder="搜索告警..." :prefix-icon="Search" clearable size="small" style="width:200px" @input="loadAlerts" />
              <el-select v-model="alertLevel" placeholder="级别" clearable size="small" style="width:110px" @change="loadAlerts">
                <el-option label="一般" value="general" /><el-option label="严重" value="serious" /><el-option label="紧急" value="emergency" />
              </el-select>
              <el-select v-model="alertStatus" placeholder="状态" clearable size="small" style="width:110px" @change="loadAlerts">
                <el-option label="新建" value="new" /><el-option label="已确认" value="acknowledged" /><el-option label="已解决" value="resolved" /><el-option label="已忽略" value="ignored" />
              </el-select>
            </div>
            <div class="toolbar-right">
              <el-button :icon="Refresh" size="small" @click="loadAlerts">刷新</el-button>
            </div>
          </div>
        </el-card>
        <el-row :gutter="12" class="stats-row" v-if="alertStats">
          <el-col :span="6"><div class="mini-stat"><div class="mini-stat-icon" style="background:#ffebee"><el-icon color="#e74c3c"><Bell /></el-icon></div><div class="mini-stat-body"><span class="mini-stat-val" style="color:#e74c3c">{{ alertStats.total }}</span><span class="mini-stat-lbl">总计</span></div></div></el-col>
          <el-col :span="6"><div class="mini-stat"><div class="mini-stat-icon" style="background:#fff3e0"><el-icon color="#e67e22"><Warning /></el-icon></div><div class="mini-stat-body"><span class="mini-stat-val" style="color:#e67e22">{{ alertStats.new }}</span><span class="mini-stat-lbl">新建</span></div></div></el-col>
          <el-col :span="6"><div class="mini-stat"><div class="mini-stat-icon" style="background:#e3f2fd"><el-icon color="#1976d2"><Clock /></el-icon></div><div class="mini-stat-body"><span class="mini-stat-val" style="color:#1976d2">{{ alertStats.acknowledged }}</span><span class="mini-stat-lbl">已确认</span></div></div></el-col>
          <el-col :span="6"><div class="mini-stat"><div class="mini-stat-icon" style="background:#e8f5e9"><el-icon color="#27ae60"><CircleCheck /></el-icon></div><div class="mini-stat-body"><span class="mini-stat-val" style="color:#27ae60">{{ alertStats.resolved }}</span><span class="mini-stat-lbl">已解决</span></div></div></el-col>
        </el-row>
        <el-card shadow="never" class="table-card">
          <el-table :data="alertList" stripe border size="small" v-loading="alertLoading">
            <el-table-column label="级别" width="80" align="center"><template #default="{ row }"><el-tag size="small" :type="levelType(row.level)" effect="dark">{{ levelLabel(row.level) }}</el-tag></template></el-table-column>
            <el-table-column prop="title" label="告警标题" min-width="200" />
            <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="90" align="center"><template #default="{ row }"><el-tag size="small" :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
            <el-table-column prop="rule_name" label="触发规则" width="130" show-overflow-tooltip />
            <el-table-column prop="target_type" label="对象类型" width="100"><template #default="{ row }">{{ targetTypeLabel(row.target_type) }}</template></el-table-column>
            <el-table-column prop="created_at" label="发生时间" width="160"><template #default="{ row }">{{ fmtTime(row.created_at) }}</template></el-table-column>
            <el-table-column label="操作" width="120" fixed="right"><template #default="{ row }"><el-button size="small" text type="primary" @click="openHandleDialog(row)">处理</el-button></template></el-table-column>
          </el-table>
          <el-pagination v-model:current-page="alertPage" v-model:page-size="alertPageSize" :total="alertTotal" :page-sizes="[10,20,50]" layout="total, sizes, prev, pager, next" small style="margin-top:12px;justify-content:center" />
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 规则弹窗 -->
    <el-dialog v-model="ruleDialog.visible" :title="ruleDialog.isEdit?'编辑告警规则':'新增告警规则'" width="500px" :close-on-click-modal="false" destroy-on-close>
      <el-form ref="ruleFormRef" :model="ruleForm" :rules="ruleRules" label-width="100px" size="small">
        <el-form-item label="规则名称" prop="name"><el-input v-model="ruleForm.name" placeholder="如：温度超阈值告警" /></el-form-item>
        <el-form-item label="规则编码" prop="code"><el-input v-model="ruleForm.code" placeholder="如：TEMP_OVER_THRESHOLD" /></el-form-item>
        <el-form-item label="监控指标" prop="metric"><el-select v-model="ruleForm.metric" style="width:100%"><el-option label="温度 (temperature)" value="temperature" /><el-option label="湿度 (humidity)" value="humidity" /><el-option label="CPU使用率 (cpu)" value="cpu" /><el-option label="内存使用率 (memory)" value="memory" /><el-option label="磁盘使用率 (disk)" value="disk" /></el-select></el-form-item>
        <el-form-item label="条件" prop="condition"><el-select v-model="ruleForm.condition" style="width:100%"><el-option label="大于 (>)" value="gt" /><el-option label="小于 (<)" value="lt" /><el-option label="大于等于 (>=" value="gte" /><el-option label="小于等于 (<=)" value="lte" /><el-option label="等于 (=)" value="eq" /></el-select></el-form-item>
        <el-form-item label="阈值" prop="threshold"><el-input-number v-model="ruleForm.threshold" :step="1" style="width:100%" /></el-form-item>
        <el-form-item label="告警级别" prop="alert_level"><el-select v-model="ruleForm.alert_level" style="width:100%"><el-option label="一般 (general)" value="general" /><el-option label="严重 (serious)" value="serious" /><el-option label="紧急 (emergency)" value="emergency" /></el-select></el-form-item>
        <el-form-item label="启用"><el-switch v-model="ruleForm.enabled" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="ruleDialog.visible=false">取消</el-button><el-button type="primary" :loading="ruleSubmitting" @click="submitRule">{{ ruleDialog.isEdit?'保存':'创建' }}</el-button></template>
    </el-dialog>

    <!-- 告警处理弹窗 -->
    <el-dialog v-model="handleDialog.visible" title="告警处理" width="480px" :close-on-click-modal="false" destroy-on-close>
      <div v-if="handleDialog.alert" class="alert-detail-box">
        <el-alert :title="handleDialog.alert.title" :type="levelType(handleDialog.alert.level)" :closable="false" show-icon style="margin-bottom:16px" />
        <p style="color:#666;font-size:13px;margin-bottom:12px">{{ handleDialog.alert.description }}</p>
        <el-form :model="handleForm" label-width="90px" size="small">
          <el-form-item label="处理操作" required>
            <el-radio-group v-model="handleForm.action_type">
              <el-radio value="acknowledge">确认告警</el-radio>
              <el-radio value="resolve">标记已解决</el-radio>
              <el-radio value="ignore">忽略告警</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="处理备注"><el-input v-model="handleForm.remark" type="textarea" :rows="3" placeholder="填写处理措施..." /></el-form-item>
          <el-form-item label="根因分析"><el-input v-model="handleForm.root_cause" type="textarea" :rows="2" placeholder="可选：分析问题根因" /></el-form-item>
        </el-form>
      </div>
      <template #footer><el-button @click="handleDialog.visible=false">取消</el-button><el-button type="primary" :loading="handleSubmitting" @click="submitHandle">提交处理</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, Refresh, Search, Bell, Warning, Clock, CircleCheck } from '@element-plus/icons-vue'
import { getAlertRulesApi, createAlertRuleApi, updateAlertRuleApi, deleteAlertRuleApi, getAlertsApi, getAlertStatsApi, handleAlertApi } from '../../api/alert'

const activeTab = ref('rules')
const ruleList = ref<any[]>([])
const ruleLoading = ref(false)
const ruleSearch = ref('')
const ruleEnabled = ref<boolean | null>(null)
const rulePage = ref(1)
const rulePageSize = ref(10)
const ruleTotal = ref(0)
const ruleSubmitting = ref(false)
const ruleFormRef = ref<any>(null)
const ruleDialog = reactive({ visible: false, isEdit: false, id: 0 })
const ruleForm = ref<any>({ name: '', code: '', metric: 'temperature', condition: 'gt', threshold: 30, alert_level: 'general', enabled: true })
const ruleRules = { name: [{ required: true, message: '请输入规则名称', trigger: 'blur' }], code: [{ required: true, message: '请输入规则编码', trigger: 'blur' }], metric: [{ required: true, message: '请选择监控指标', trigger: 'change' }], condition: [{ required: true, message: '请选择条件', trigger: 'change' }], threshold: [{ required: true, message: '请输入阈值', trigger: 'blur' }] }

async function loadRules() { ruleLoading.value = true; try { const r = await getAlertRulesApi({ page: rulePage.value, page_size: rulePageSize.value, keyword: ruleSearch.value || undefined, enabled: ruleEnabled.value }); ruleList.value = r.data.items; ruleTotal.value = r.data.total } catch { ruleList.value = [] } finally { ruleLoading.value = false } }
function openRuleDialog(rule?: any) { ruleDialog.visible = true; ruleDialog.isEdit = !!rule; ruleDialog.id = rule?.id || 0; if (rule) { ruleForm.value = { name: rule.name, code: rule.code, metric: rule.metric, condition: rule.condition, threshold: rule.threshold, alert_level: rule.alert_level, enabled: rule.enabled } } else { ruleForm.value = { name: '', code: '', metric: 'temperature', condition: 'gt', threshold: 30, alert_level: 'general', enabled: true } } setTimeout(() => ruleFormRef.value?.clearValidate(), 0) }
async function submitRule() { const valid = await ruleFormRef.value?.validate().catch(() => false); if (!valid) return; ruleSubmitting.value = true; try { if (ruleDialog.isEdit) { await updateAlertRuleApi(ruleDialog.id, ruleForm.value); ElMessage.success('规则已更新') } else { await createAlertRuleApi(ruleForm.value); ElMessage.success('规则已创建') } ruleDialog.visible = false; await loadRules() } catch { /* interceptor */ } finally { ruleSubmitting.value = false } }
async function toggleRule(rule: any) { try { await updateAlertRuleApi(rule.id, { enabled: !rule.enabled }); ElMessage.success(rule.enabled ? '规则已禁用' : '规则已启用'); await loadRules() } catch { /* interceptor */ } }
async function deleteRule(rule: any) { try { await ElMessageBox.confirm('确定删除规则「' + rule.name + '」？', '确认删除', { type: 'warning' }); await deleteAlertRuleApi(rule.id); ElMessage.success('已删除'); await loadRules() } catch { /* cancelled */ } }

const alertList = ref<any[]>([])
const alertLoading = ref(false)
const alertStats = ref<any>(null)
const alertSearch = ref('')
const alertLevel = ref('')
const alertStatus = ref('')
const alertPage = ref(1)
const alertPageSize = ref(10)
const alertTotal = ref(0)
const handleSubmitting = ref(false)
const handleDialog = reactive({ visible: false, alert: null as any })
const handleForm = ref({ action_type: 'acknowledge', remark: '', root_cause: '' })

async function loadAlerts() { alertLoading.value = true; try { const [a, s] = await Promise.all([getAlertsApi({ page: alertPage.value, page_size: alertPageSize.value, keyword: alertSearch.value || undefined, level: alertLevel.value || undefined, status: alertStatus.value || undefined }), getAlertStatsApi()]); alertList.value = a.data.items; alertTotal.value = a.data.total; alertStats.value = s.data } catch { alertList.value = [] } finally { alertLoading.value = false } }
function openHandleDialog(alert: any) { handleDialog.visible = true; handleDialog.alert = alert; handleForm.value = { action_type: 'acknowledge', remark: '', root_cause: '' } }
async function submitHandle() { if (!handleForm.value.action_type) { ElMessage.warning('请选择处理操作'); return } handleSubmitting.value = true; try { await handleAlertApi(handleDialog.alert.id, handleForm.value); ElMessage.success('处理成功'); handleDialog.visible = false; await loadAlerts() } catch { /* interceptor */ } finally { handleSubmitting.value = false } }

function metricLabel(m: string) { const map: Record<string,string> = { temperature:'温度', humidity:'湿度', cpu:'CPU', memory:'内存', disk:'磁盘' }; return map[m] || m }
function metricUnit(m: string) { const map: Record<string,string> = { temperature:'C', humidity:'%', cpu:'%', memory:'%', disk:'%' }; return map[m] || '' }
function conditionLabel(c: string) { const map: Record<string,string> = { gt:'>', lt:'<', gte:'>=', lte:'<=', eq:'=' }; return map[c] || c }
function levelLabel(l: string) { const map: Record<string,string> = { general:'一般', serious:'严重', emergency:'紧急' }; return map[l] || l }
function levelType(l: string) { const map: Record<string,string> = { general:'warning', serious:'danger', emergency:'danger' }; return map[l] || 'info' }
function statusLabel(s: string) { const map: Record<string,string> = { new:'新建', acknowledged:'已确认', resolved:'已解决', ignored:'已忽略' }; return map[s] || s }
function statusType(s: string) { const map: Record<string,string> = { new:'danger', acknowledged:'warning', resolved:'success', ignored:'info' }; return map[s] || 'info' }
function targetTypeLabel(t: string) { const map: Record<string,string> = { device:'设备', sensor:'传感器', system:'系统' }; return map[t] || t }
function fmtTime(ts: string) { if (!ts) return '--'; return new Date(ts).toLocaleString('zh-CN') }

watch([rulePage, rulePageSize], loadRules)
watch([alertPage, alertPageSize], loadAlerts)
onMounted(() => { loadRules(); loadAlerts() })
</script>

<style scoped>
.page-header { margin-bottom: 16px; }
.page-title { font-size: 20px; font-weight: 700; margin: 0; background: linear-gradient(135deg, #e74c3c, #c0392b); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.page-desc { font-size: 13px; color: var(--app-text-muted); margin: 4px 0 0; }
.alert-tabs { }
.toolbar-card { margin-bottom: 12px; border-radius: 12px; }
.toolbar-bar { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.toolbar-left, .toolbar-right { display: flex; align-items: center; gap: 8px; }
.table-card { border-radius: 12px; }
.stats-row { margin-bottom: 12px; }
.mini-stat { display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: var(--el-bg-color); border-radius: 10px; border: 1px solid var(--app-border); }
.mini-stat-icon { width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.mini-stat-body { display: flex; flex-direction: column; }
.mini-stat-val { font-size: 18px; font-weight: 700; line-height: 1.2; }
.mini-stat-lbl { font-size: 11px; color: var(--app-text-muted); }
.alert-detail-box { }
</style>
