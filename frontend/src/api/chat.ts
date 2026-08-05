import axios from "./index"

export interface ChatConversation {
  id: number
  title: string
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: number
  role: "user" | "assistant"
  content: string
  created_at: string
}

export function getConversationsApi() {
  return axios.get<ChatConversation[]>("/chat/conversations")
}

export function getMessagesApi(convId: number) {
  return axios.get<ChatMessage[]>("/chat/conversations/" + convId + "/messages")
}

export function createConversationApi() {
  return axios.post<{ id: number; title: string }>("/chat/conversations")
}

export function deleteConversationApi(convId: number) {
  return axios.delete("/chat/conversations/" + convId)
}

export function sendMessageApi(content: string, conversationId?: number) {
  return axios.post<ChatMessage>("/chat/messages", { content, conversation_id: conversationId })
}

export function sendMessageStreamApi(
  content: string,
  conversationId: number,
  onChunk: (content: string) => void,
  onDone: () => void,
  onError: (error: string) => void
) {
  let aborted = false
  const xhr = new XMLHttpRequest()
  xhr.open("POST", "/api/v1/chat/messages/stream")
  xhr.setRequestHeader("Content-Type", "application/json")
  const token = localStorage.getItem("access_token")
  if (token) xhr.setRequestHeader("Authorization", "Bearer " + token)

  let buffer = ""
  let doneSent = false

  xhr.onprogress = () => {
    buffer += xhr.responseText.slice(buffer.length)
    const lines = buffer.split("\n")
    buffer = lines.pop() || ""
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const data = line.slice(6)
        if (data === "[DONE]") {
          if (!doneSent) { doneSent = true; onDone() }
        } else if (data === "[ERROR]") {
          if (!doneSent) { doneSent = true; onError("AI ????????") }
        } else if (data.trim()) {
          onChunk(data)
        }
      }
    }
  }

  xhr.onload = () => {
    if (aborted) return
    if (xhr.status >= 200 && xhr.status < 300) {
      if (!doneSent) { doneSent = true; onDone() }
    } else {
      try {
        const resp = JSON.parse(xhr.responseText)
        onError(resp.detail || "????")
      } catch {
        onError("????")
      }
    }
  }
  xhr.onerror = () => {
    if (aborted) return
    onError("????")
  }

  try {
    xhr.send(JSON.stringify({ content, conversation_id: conversationId }))
  } catch {
    onError("????")
  }

  // 返回取消函数：停止生成
  return function cancel() {
    aborted = true
    try { xhr.abort() } catch { /* ignore */ }
  }
}
