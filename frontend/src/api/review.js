import api from './index'

// 审核队列列表
export function getReviewList(params) {
  return api.get('/api/v1/review/', { params })
}

// 审核详情
export function getReviewDetail(id) {
  return api.get(`/api/v1/review/${id}`)
}

// 执行审核操作
export function reviewAction(id, data) {
  return api.post(`/api/v1/review/${id}/action`, data)
}
