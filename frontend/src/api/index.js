import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const api = axios.create({
  baseURL: '',
  timeout: 20000,  // 20秒超时，避免请求堆积
})

// 请求去重：短时间内相同URL+参数的请求合并
const pendingRequests = new Map()

function getRequestKey(config) {
  const { method, url, params, data } = config
  return [method, url, JSON.stringify(params), JSON.stringify(data)].join('&')
}

function addPending(config) {
  const key = getRequestKey(config)
  if (pendingRequests.has(key)) {
    // 已有相同请求进行中，取消本次请求
    const cancel = pendingRequests.get(key)
    cancel && cancel()
    pendingRequests.delete(key)
  }
  config.cancelToken = new axios.CancelToken((cancel) => {
    pendingRequests.set(key, cancel)
  })
}

function removePending(config) {
  const key = getRequestKey(config)
  pendingRequests.delete(key)
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  // GET 请求去重（POST/PUT/DELETE 不合并）
  if (config.method === 'get') {
    addPending(config)
  }
  return config
})

// 错误消息节流：3秒内同一消息不重复弹出
let lastErrorTime = 0
let lastErrorMessage = ''

api.interceptors.response.use(
  (response) => {
    removePending(response.config)
    return response
  },
  (error) => {
    if (axios.isCancel(error)) {
      // 被取消的请求静默丢弃
      return Promise.resolve({ data: null })
    }
    removePending(error.config || {})
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      router.push({ name: 'Login' })
      ElMessage.error('登录已过期，请重新登录')
    } else if (error.response?.status === 403) {
      router.push({ name: 'Forbidden' })
    } else if (error.code === 'ECONNABORTED') {
      // 超时不弹窗（页面会自动显示空数据/错误状态）
      console.warn('请求超时:', error.config?.url)
    } else if (error.response?.status === 502 || error.response?.status === 504) {
      // 代理错误节流
      const now = Date.now()
      const msg = '服务繁忙，请稍后刷新'
      if (now - lastErrorTime > 3000 || lastErrorMessage !== msg) {
        ElMessage.warning(msg)
        lastErrorTime = now
        lastErrorMessage = msg
      }
    } else {
      // 其他错误节流
      const now = Date.now()
      const msg = error.response?.data?.detail || '请求失败'
      if (now - lastErrorTime > 3000 || lastErrorMessage !== msg) {
        ElMessage.error(msg)
        lastErrorTime = now
        lastErrorMessage = msg
      }
    }
    return Promise.reject(error)
  }
)

export default api
