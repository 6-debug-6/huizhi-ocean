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
  return api.delete(`/api/v1/conversations/${id}`)
}

export function renameConversation(id, title) {
  const form = new FormData()
  form.append('title', title)
  return api.put(`/api/v1/conversations/${id}`, form)
}

export function sendMessage(conversationId, message, image = null) {
  const form = new FormData()
  form.append('conversation_id', conversationId)
  form.append('message', message)
  if (image) form.append('image', image)
  return api.post('/api/v1/chat', form)
}

export function submitFeedback(convId, feedback, comment = '') {
  return api.post(`/api/v1/conversations/${convId}/feedback`, { feedback, comment })
}
