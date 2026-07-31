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
  return new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open("POST", "/api/v1/chat/messages/stream")
    xhr.setRequestHeader("Content-Type", "application/json")
    const token = localStorage.getItem("access_token")
    if (token) xhr.setRequestHeader("Authorization", "Bearer " + token)

    let buffer = ""

    xhr.onprogress = () => {
      buffer += xhr.responseText.slice(buffer.length)
      const lines = buffer.split("\n")
      buffer = lines.pop() || ""

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6)
          if (data === "[DONE]") onDone()
          else if (data.trim()) onChunk(data)
        }
      }
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        onDone()
        resolve()
      } else {
        try {
          const resp = JSON.parse(xhr.responseText)
          onError(resp.detail || "请求失败")
        } catch {
          onError("请求失败")
        }
        reject(new Error(xhr.statusText))
      }
    }

    xhr.onerror = () => {
      onError("网络错误")
      reject(new Error("Network error"))
    }

    xhr.send(JSON.stringify({ content, conversation_id: conversationId }))
  })
}