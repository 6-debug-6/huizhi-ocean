import api from './index'

// 用户端：提交工单
export function createTicket(data) {
  return api.post('/api/v1/tickets/', data)
}

// 用户端/管理端：工单列表
export function getTicketList(params) {
  return api.get('/api/v1/tickets/', { params })
}

// 工单详情（含回复链）
export function getTicketDetail(id) {
  return api.get(`/api/v1/tickets/${id}`)
}

// 管理员：回复工单
export function replyTicket(id, data) {
  return api.post(`/api/v1/tickets/${id}/reply`, data)
}

// 更新工单状态
export function updateTicketStatus(id, data) {
  return api.put(`/api/v1/tickets/${id}/status`, data)
}

// 管理员：工单转知识条目
export function ticketToKnowledge(id) {
  return api.post(`/api/v1/tickets/${id}/to-knowledge`)
}

// 管理员：删除工单
export function deleteTicket(id) {
  return api.post(`/api/v1/tickets/${id}/delete`)
}
