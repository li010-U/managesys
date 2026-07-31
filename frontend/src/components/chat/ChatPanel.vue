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
          <div v-for="conv in conversations" :key="conv.id" :class="['conv-item', { active: currentConvId === conv.id }]" @click="selectConversation(conv.id)">
            <span class="conv-title">{{ conv.title || '新对话' }}</span>
            <el-icon class="conv-delete" @click.stop="deleteConversation(conv.id)"><Delete /></el-icon>
          </div>
          <el-empty v-if="conversations.length === 0" description="暂无对话" :image-size="50" />
        </div>
      </div>
      <div class="chat-area">
        <div class="messages" ref="messagesRef">
          <div v-for="(msg, idx) in messages" :key="idx" :class="['message', msg.role]">
            <el-avatar :size="32" class="msg-avatar">{{ msg.role === "user" ? "我" : "AI" }}</el-avatar>
            <div class="msg-content">
              <div class="msg-bubble" v-html="renderMarkdown(msg.content)"></div>
              <div class="msg-time">{{ formatTime(msg.created_at) }}</div>
            </div>
          </div>
          <div v-if="sending" class="message assistant">
            <el-avatar :size="32" class="msg-avatar">AI</el-avatar>
            <div class="msg-content">
              <div class="msg-bubble thinking"><el-icon class="is-loading"><Loading /></el-icon> AI 思考中...</div>
            </div>
          </div>
        </div>
        <div class="chat-input">
          <el-input v-model="inputText" type="textarea" :rows="2" placeholder="输入消息... (Ctrl+Enter 发送)" @keydown.enter.ctrl="sendMessage" />
          <el-button type="primary" :loading="sending" @click="sendMessage" :disabled="!inputText.trim()">发送</el-button>
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
  sendMessageApi, sendMessageStreamApi, type ChatConversation, type ChatMessage
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
const messagesRef = ref<HTMLElement>()

async function loadConversations() {
  try { conversations.value = (await getConversationsApi()).data } catch (e) { console.error("加载对话列表失败", e) }
}
async function selectConversation(id: number) {
  currentConvId.value = id
  try { messages.value = (await getMessagesApi(id)).data; scrollToBottom() } catch (e) { console.error("加载消息失败", e) }
}
async function newConversation() {
  try { const res = await createConversationApi(); await loadConversations(); currentConvId.value = res.data.id; messages.value = [] } catch (e) { console.error("创建对话失败", e) }
}
async function deleteConversation(id: number) {
  try {
    await deleteConversationApi(id)
    await loadConversations()
    if (currentConvId.value === id) { currentConvId.value = null; messages.value = [] }
  } catch (e) { console.error("删除对话失败", e) }
}
async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || sending.value) return
  if (!currentConvId.value) await newConversation()
  sending.value = true
  inputText.value = ""
  const userMsg: ChatMessage = { id: Date.now(), role: "user", content: text, created_at: new Date().toISOString() }
  messages.value.push(userMsg)
  scrollToBottom()
  try {
    await sendMessageStreamApi(text, currentConvId.value!, (chunk) => {
      const lastMsg = messages.value[messages.value.length - 1]
      if (lastMsg && lastMsg.role === "user") messages.value.push({ id: Date.now() + 1, role: "assistant", content: chunk, created_at: new Date().toISOString() })
      else if (lastMsg && lastMsg.role === "assistant") lastMsg.content += chunk
      scrollToBottom()
    }, () => { sending.value = false; loadConversations() }, (error) => { sending.value = false; ElMessage.error(error || "发送失败") })
  } catch (e: any) { sending.value = false; ElMessage.error(e.message || "发送失败") }
}
function scrollToBottom() { nextTick(() => { if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight }) }
function formatTime(timeStr: string) { if (!timeStr) return ""; return new Date(timeStr).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }) }
function handleClose() { visible.value = false }
watch(visible, (val) => { if (val) { loadConversations(); if (currentConvId.value) selectConversation(currentConvId.value) } })
onMounted(() => { loadConversations() })
</script>

<style scoped>
.chat-container { display: flex; flex-direction: column; height: 100%; }
.conversation-list { border-bottom: 1px solid var(--el-border-color-lighter); padding-bottom: 12px; margin-bottom: 12px; }
.conv-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; font-weight: 600; }
.conv-items { max-height: 150px; overflow-y: auto; }
.conv-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; border-radius: 6px; cursor: pointer; transition: background 0.2s; }
.conv-item:hover, .conv-item.active { background: var(--el-fill-color-light); }
.conv-item.active { background: var(--el-color-primary-light-9); }
.conv-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
.conv-delete { opacity: 0; transition: opacity 0.2s; }
.conv-item:hover .conv-delete { opacity: 1; }
.chat-area { flex: 1; display: flex; flex-direction: column; min-height: 0; }
.messages { flex: 1; overflow-y: auto; padding: 8px 0; }
.message { display: flex; gap: 10px; margin-bottom: 16px; }
.message.user { flex-direction: row-reverse; }
.msg-avatar { flex-shrink: 0; background: var(--el-color-primary-light-5); }
.message.assistant .msg-avatar { background: var(--el-color-success-light-5); }
.msg-content { max-width: 85%; }
.msg-bubble { padding: 10px 14px; border-radius: 12px; background: var(--el-fill-color-light); font-size: 14px; line-height: 1.6; word-break: break-word; }
.msg-bubble :deep(p) { margin: 0 0 8px 0; }
.msg-bubble :deep(p:last-child) { margin-bottom: 0; }
.msg-bubble :deep(code) { background: var(--el-fill-color); padding: 2px 6px; border-radius: 4px; font-size: 13px; }
.msg-bubble :deep(pre) { background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 8px; overflow-x: auto; margin: 8px 0; }
.msg-bubble :deep(ul), .msg-bubble :deep(ol) { margin: 8px 0; padding-left: 20px; }
.message.user .msg-bubble { background: var(--el-color-primary); color: #fff; }
.msg-time { font-size: 11px; color: var(--el-text-color-secondary); margin-top: 4px; }
.message.user .msg-time { text-align: right; }
.thinking { display: flex; align-items: center; gap: 8px; }
.chat-input { display: flex; gap: 8px; padding-top: 12px; border-top: 1px solid var(--el-border-color-lighter); }
.chat-input .el-textarea { flex: 1; }
</style>

<style>
.hljs { background: #1e1e1e; color: #d4d4d4; }
.hljs-keyword, .hljs-selector-tag { color: #569cd6; }
.hljs-string, .hljs-attr { color: #ce9178; }
.hljs-comment { color: #6a9955; }
</style>