import api from './index'

// 知识条目列表
export function getKnowledgeList(params) {
  return api.get('/api/v1/knowledge/', { params })
}

// 知识条目详情
export function getKnowledgeDetail(id) {
  return api.get(`/api/v1/knowledge/${id}`)
}

// 创建知识条目
export function createKnowledge(data) {
  return api.post('/api/v1/knowledge/', data)
}

// 更新知识条目
export function updateKnowledge(id, data) {
  return api.put(`/api/v1/knowledge/${id}`, data)
}

// 归档知识条目
export function archiveKnowledge(id) {
  return api.put(`/api/v1/knowledge/${id}/archive`)
}

// 版本历史
export function getVersions(id) {
  return api.get(`/api/v1/knowledge/${id}/versions`)
}

// 回滚版本
export function rollbackVersion(entryId, versionId) {
  return api.post(`/api/v1/knowledge/${entryId}/versions/${versionId}/rollback`)
}
