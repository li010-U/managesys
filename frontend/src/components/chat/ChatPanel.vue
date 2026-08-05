<template>
  <el-drawer v-model="visible" title="AI 助手" direction="rtl" size="420px" :before-close="handleClose">
    <div class="chat-container">
      <div class="conversation-list">
        <div class="conv-header">
          <span>对话历史</span>
          <el-button type="primary" size="small" text @click="newConversation">
            <el-icon><Plus /></el-icon> 新对话
          </el-button>
        </div>
        <div class="conv-items">
          <div 
            v-for="conv in conversations" 
            :key="conv.id" 
            :class="['conv-item', { active: currentConvId === conv.id }]"
            @click="selectConversation(conv.id)"
          >
            <span class="conv-title">{{ conv.title || '新对话' }}</span>
            <el-icon class="conv-delete" @click.stop="deleteConversation(conv.id)"><Delete /></el-icon>
          </div>
          <el-empty v-if="conversations.length === 0" description="暂无对话" :image-size="50" />
        </div>
      </div>
      <div class="chat-area">
        <div class="messages" ref="messagesRef">
          <transition-group name="list" tag="div">
            <div v-for="(msg, idx) in messages" :key="idx" :class="['message', msg.role]">
              <el-avatar :size="32" class="msg-avatar">{{ msg.role === "user" ? "我" : "AI" }}</el-avatar>
              <div class="msg-content">
                <div class="msg-bubble" v-html="renderMarkdown(msg.content)"></div>
                <div class="msg-time">{{ formatTime(msg.created_at) }}</div>
              </div>
            </div>
          </transition-group>
          <div v-if="sending" class="message assistant">
            <el-avatar :size="32" class="msg-avatar">AI</el-avatar>
            <div class="msg-content">
              <div class="msg-bubble thinking">
                <el-icon class="is-loading"><Loading /></el-icon> AI 思考中...
              </div>
            </div>
          </div>
        </div>
        <div class="quick-prompts" v-if="messages.length === 0 && !sending">
          <div
            v-for="(qp, qi) in QUICK_PROMPTS"
            :key="qi"
            class="quick-chip"
            @click="useQuickPrompt(qp)"
          >{{ qp }}</div>
        </div>
        <div class="proposal-banner" v-if="pendingProposal">
  <div class="proposal-title">检测到待确认操作</div>
  <div class="proposal-desc">{{ describeProposal(pendingProposal) }}</div>
  <div class="proposal-actions">
    <el-button type="primary" size="small" @click="confirmProposal">确认执行</el-button>
    <el-button size="small" @click="cancelProposal">取消</el-button>
  </div>
</div>
<div class="chat-input">
          <el-input 
            v-model="inputText" 
            type="textarea" 
            :rows="2" 
            placeholder="输入消息... (Ctrl+Enter 发送)" 
            resize="none"
            @keydown.enter.ctrl="sendMessage" 
          />
          <div class="input-actions">
            <el-button v-if="sending" type="danger" plain @click="stopGenerating" class="send-btn">
              停止
            </el-button>
            <el-button v-else type="primary" @click="sendMessage" :disabled="!inputText.trim()" class="send-btn">
              发送
            </el-button>
            <el-button
              v-if="messages.some(m => m.role === 'assistant')"
              text
              size="small"
              class="regenerate-btn"
              @click="regenerate"
              :disabled="sending"
            >
              重答
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from "vue"
import { ElMessage } from "element-plus"
import { Plus, Delete, Loading } from "@element-plus/icons-vue"
import MarkdownIt from "markdown-it"
import hljs from "highlight.js"
import {
  getConversationsApi, getMessagesApi, createConversationApi, deleteConversationApi,
  sendMessageApi, sendMessageStreamApi, executeToolApi,
  type ChatConversation, type ChatMessage, type ToolProposal
} from "../../api/chat"

const md = new MarkdownIt({ html: false, linkify: true, typographer: true })

function renderMarkdown(content: string): string {
  if (!content) return ""
  return md.render(content)
}

const visible = defineModel<boolean>({ default: false })
const conversations = ref<ChatConversation[]>([])
const messages = ref<ChatMessage[]>([])
const currentConvId = ref<number | null>(null)
const inputText = ref("")
const sending = ref(false)
const pendingProposal = ref<ToolProposal | null>(null)
let cancelStream: (() => void) | null = null
const QUICK_PROMPTS = [
  "当前机房状态如何？有无异常？",
  "报告最新的设备告警",
  "给出今天的运维建议",
  "如何处理传感器超阈值？",
]
const messagesRef = ref<HTMLElement>()

async function loadConversations() {
  try { 
    conversations.value = (await getConversationsApi()).data 
  } catch (e) { 
    console.error("加载对话列表失败", e) 
  }
}

async function selectConversation(id: number) {
  currentConvId.value = id
  try { 
    messages.value = (await getMessagesApi(id)).data; 
    scrollToBottom() 
  } catch (e) { 
    console.error("加载消息失败", e) 
  }
}

async function newConversation() {
  try { 
    const res = await createConversationApi(); 
    await loadConversations(); 
    currentConvId.value = res.data.id; 
    messages.value = [] 
  } catch (e) { 
    console.error("创建对话失败", e) 
  }
}

async function deleteConversation(id: number) {
  try {
    await deleteConversationApi(id)
    await loadConversations()
    if (currentConvId.value === id) { 
      currentConvId.value = null; 
      messages.value = [] 
    }
  } catch (e) { 
    console.error("删除对话失败", e) 
  }
}

function sendUserMessage(text: string) {
  if (!text || sending.value) return
  pendingProposal.value = null
  sending.value = true
  const userMsg: ChatMessage = { id: Date.now(), role: "user", content: text, created_at: new Date().toISOString() }
  messages.value.push(userMsg)
  scrollToBottom()
  cancelStream = sendMessageStreamApi(text, currentConvId.value as number, (chunk) => {
    const lastMsg = messages.value[messages.value.length - 1]
    if (lastMsg && lastMsg.role === "user") {
      messages.value.push({ id: Date.now() + 1, role: "assistant", content: chunk, created_at: new Date().toISOString() })
    } else if (lastMsg && lastMsg.role === "assistant") {
      lastMsg.content += chunk
    }
    scrollToBottom()
  }, () => {
    sending.value = false
    cancelStream = null
    loadConversations()
  }, (error) => {
    sending.value = false
    cancelStream = null
    ElMessage.error(error || "发送失败")
  }, (proposal) => {
    pendingProposal.value = proposal
  })
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || sending.value) return
  inputText.value = ""
  if (!currentConvId.value) {
    try {
      const res = await createConversationApi()
      await loadConversations()
      currentConvId.value = res.data.id
      messages.value = []
    } catch (e) {
      ElMessage.error("创建会话失败")
      return
    }
  }
  sendUserMessage(text)
}

function stopGenerating() {
  if (cancelStream) { cancelStream(); cancelStream = null }
  sending.value = false
}

function regenerate() {
  if (sending.value) return
  const lastUser = [...messages.value].reverse().find((m) => m.role === "user")
  if (!lastUser) return
  const idx = messages.value.findIndex((m) => m.content === lastUser.content && m.role === "user")
  if (idx >= 0 && messages.value[idx + 1] && messages.value[idx + 1].role === "assistant") {
    messages.value.splice(idx + 1, 1)
  }
  sendUserMessage(lastUser.content)
}

function useQuickPrompt(p: string) {
  if (sending.value) return
  inputText.value = p
  sendMessage()
}

function describeProposal(p: ToolProposal): string {
  if (p.tool === "create_work_order") {
    return "创建工单：“" + String(p.args.title || "") + "”"
  }
  if (p.tool === "handle_alert") {
    const m: Record<string, string> = { acknowledge: "确认", resolve: "解决", ignore: "忽略" }
    return "处理告警 #" + String(p.args.alert_id) + "（" + (m[String(p.args.action_type)] || String(p.args.action_type)) + "）"
  }
  if (p.tool === "assign_work_order") {
    return "分配工单 #" + String(p.args.order_id) + "给" + String(p.args.assignee_username || "")
  }
  if (p.tool === "close_work_order") {
    return "关闭工单 #" + String(p.args.order_id)
  }
  if (p.tool === "verify_work_order") {
    return "验收工单 #" + String(p.args.order_id) + "（" + (String(p.args.accept) === "true" ? "通过" : "驳回") + "）"
  }
  if (p.tool === "mount_device") {
    return "挂载设备 #" + String(p.args.device_id) + "到机柜 " + String(p.args.rack_id || "")
  }
  if (p.tool === "unmount_device") {
    return "卸载设备 #" + String(p.args.device_id)
  }
  if (p.tool === "create_alert_rule") {
    return "添加告警规则：" + String(p.args.name || "")
  }
  return p.tool
}async function confirmProposal() {
  if (!pendingProposal.value) return
  const proposal = pendingProposal.value
  pendingProposal.value = null
  try {
    const res = await executeToolApi(proposal.tool, proposal.args)
    const r = (res.data as { result?: Record<string, unknown> })?.result || {}
    ElMessage.success("已执行")
    messages.value.push({
      id: Date.now(),
      role: "assistant",
      content: "已确认执行。" + describeProposal(proposal) + (Object.keys(r).length ? " " + JSON.stringify(r) : ""),
      created_at: new Date().toISOString()
    })
    scrollToBottom()
    loadConversations()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "执行失败")
    pendingProposal.value = proposal
  }
}

function cancelProposal() {
  pendingProposal.value = null
}

function scrollToBottom() { 
  nextTick(() => { 
    if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight 
  }) 
}

function formatTime(timeStr: string) { 
  if (!timeStr) return ""; 
  return new Date(timeStr).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }) 
}

function handleClose() { visible.value = false }

watch(visible, (val) => { 
  if (val) { 
    loadConversations(); 
    if (currentConvId.value) selectConversation(currentConvId.value) 
  } 
})

onMounted(() => { loadConversations() })
</script>

<style scoped>
.chat-container { 
  display: flex; 
  flex-direction: column; 
  height: 100%; 
}

.conversation-list { 
  border-bottom: 1px solid var(--app-border-light); 
  padding-bottom: 12px; 
  margin-bottom: 12px; 
}

.conv-header { 
  display: flex; 
  justify-content: space-between; 
  align-items: center; 
  margin-bottom: 8px; 
  font-weight: 600;
  color: var(--app-text-primary);
}

.conv-items { 
  max-height: 150px; 
  overflow-y: auto; 
}

.conv-item { 
  display: flex; 
  justify-content: space-between; 
  align-items: center; 
  padding: 10px 12px; 
  border-radius: 10px; 
  cursor: pointer; 
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  margin: 4px 0;
}

.conv-item:hover, .conv-item.active { 
  background: var(--el-fill-color-light); 
}

.conv-item.active { 
  background: var(--el-color-primary-light-9); 
}

html.dark .conv-item.active {
  background: rgba(67, 97, 238, 0.2);
}

.conv-title { 
  flex: 1; 
  overflow: hidden; 
  text-overflow: ellipsis; 
  white-space: nowrap; 
  font-size: 13px; 
}

.conv-delete { 
  opacity: 0; 
  transition: opacity 0.2s;
  color: var(--app-text-muted);
}

.conv-item:hover .conv-delete { 
  opacity: 1; 
}

.conv-delete:hover {
  color: var(--el-color-danger);
}

.chat-area { 
  flex: 1; 
  display: flex; 
  flex-direction: column; 
  min-height: 0; 
}

.messages { 
  flex: 1; 
  overflow-y: auto; 
  padding: 8px 0; 
}

.message { 
  display: flex; 
  gap: 12px; 
  margin-bottom: 16px;
  animation: fadeInUp 0.3s ease;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message.user { 
  flex-direction: row-reverse; 
}

.msg-avatar { 
  flex-shrink: 0; 
  background: var(--app-gradient-primary);
  color: #fff;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(67, 97, 238, 0.3);
}

.message.assistant .msg-avatar { 
  background: var(--app-gradient-success);
  box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
}

.msg-content { 
  max-width: 85%; 
}

.msg-bubble { 
  padding: 12px 16px; 
  border-radius: 16px; 
  background: var(--el-fill-color-light); 
  font-size: 14px; 
  line-height: 1.6; 
  word-break: break-word;
  transition: background-color 0.3s;
}

html.dark .msg-bubble {
  background: #232338;
}

.msg-bubble :deep(p) { margin: 0 0 8px 0; }
.msg-bubble :deep(p:last-child) { margin-bottom: 0; }
.msg-bubble :deep(code) { 
  background: var(--el-fill-color); 
  padding: 2px 6px; 
  border-radius: 4px; 
  font-size: 13px; 
}

html.dark .msg-bubble :deep(code) {
  background: #1a1a2e;
}

.msg-bubble :deep(pre) { 
  background: #1e1e1e; 
  color: #d4d4d4; 
  padding: 12px; 
  border-radius: 10px; 
  overflow-x: auto; 
  margin: 8px 0; 
}

.msg-bubble :deep(ul), .msg-bubble :deep(ol) { 
  margin: 8px 0; 
  padding-left: 20px; 
}

.message.user .msg-bubble { 
  background: var(--app-gradient-primary); 
  color: #fff; 
  border-bottom-right-radius: 4px;
}

.message.assistant .msg-bubble {
  border-bottom-left-radius: 4px;
}

.msg-time { 
  font-size: 11px; 
  color: var(--app-text-muted); 
  margin-top: 6px; 
}

.message.user .msg-time { 
  text-align: right; 
}

.thinking { 
  display: flex; 
  align-items: center; 
  gap: 8px; 
  color: var(--app-text-secondary);
}

.proposal-banner {
  padding: 12px 14px;
  margin-bottom: 12px;
  border-radius: 12px;
  border: 1px solid var(--el-color-warning-light-5);
  background: var(--el-color-warning-light-9);
}
.proposal-title {
  font-weight: 600;
  font-size: 13px;
  color: var(--el-color-warning-dark-2);
  margin-bottom: 6px;
}
.proposal-desc {
  font-size: 13px;
  color: var(--app-text-primary);
  margin-bottom: 10px;
  word-break: break-all;
}
.proposal-actions {
  display: flex;
  gap: 8px;
}

.chat-input { 
  display: flex; 
  gap: 12px; 
  padding-top: 12px; 
  border-top: 1px solid var(--app-border-light);
  align-items: flex-end;
}

.chat-input .el-textarea { 
  flex: 1; 
}

.send-btn {
  height: 60px;
  border-radius: 12px;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.send-btn:not(:disabled):hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(67, 97, 238, 0.35);
}

/* List transition */
.list-enter-active {
  transition: all 0.3s ease;
}
.list-leave-active {
  transition: all 0.2s ease;
}
.list-enter-from {
  opacity: 0;
  transform: translateY(20px);
}
.list-leave-to {
  opacity: 0;
}
.quick-prompts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.quick-chip {
  padding: 6px 12px;
  border-radius: 16px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--app-border-light);
  font-size: 12px;
  color: var(--app-text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}
.quick-chip:hover {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  border-color: var(--el-color-primary-light-5);
}
.input-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.regenerate-btn {
  white-space: nowrap;
}
</style>

<style>
.hljs { background: #1e1e1e; color: #d4d4d4; }
.hljs-keyword, .hljs-selector-tag { color: #569cd6; }
.hljs-string, .hljs-attr { color: #ce9178; }
.hljs-comment { color: #6a9955; }
</style>