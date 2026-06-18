import api from './index'

export function createConversation() {
  return api.post('/api/v1/conversations')
}

export function getConversations() {
  return api.get('/api/v1/conversations')
}

export function getConversation(id) {
  return api.get(`/api/v1/conversations/${id}`)
}

export function deleteConversation(id) {
  return api.post(`/api/v1/conversations/${id}/delete`)
}

export function renameConversation(id, title) {
  const form = new FormData()
  form.append('title', title)
  return api.put(`/api/v1/conversations/${id}`, form)
}

export function sendMessage(conversationId, message, image = null, model = 'deepseek', chatMode = 'rag') {
  const form = new FormData()
  form.append('conversation_id', conversationId)
  form.append('message', message || '')
  if (image) form.append('image', image)
  form.append('model', model)  // deepseek 或 qwen
  form.append('chat_mode', chatMode)  // rag 或 casual
  return api.post('/api/v1/chat', form)
}

export function submitFeedback(convId, feedback, comment = '') {
  return api.post(`/api/v1/conversations/${convId}/feedback`, { feedback, comment })
}
