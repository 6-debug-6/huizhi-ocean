/**
 * useChat — 共享对话引擎 composable
 *
 * 从 Chat.vue 中抽取，封装 AI 对话的全部状态和方法。
 * 支持通过 options 注入上下文（设备型号、作业步骤、知识条目等），
 * 供 Chat.vue（全屏模式）、ChatPanel.vue（紧凑模式）和作业指引内嵌AI 共用。
 *
 * 用法：
 *   const chat = useChat({ deviceModel: 'XX型', taskStep: '拆卸轴承' })
 *   chat.send('这个步骤要注意什么？')
 */
import { ref, nextTick, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createConversation, getConversations, getConversation,
  deleteConversation, renameConversation, sendMessage, submitFeedback
} from '@/api/chat'

export function useChat(options = {}) {
  // ========== 会话状态 ==========
  const conversations = ref([])         // 历史对话列表
  const convId = ref(null)             // 当前对话 ID
  const messages = ref([])             // 当前对话的消息列表
  const sending = ref(false)           // 是否正在发送
  const uselessCount = ref(0)          // 连续无用反馈计数

  // ========== 输入状态 ==========
  const inputText = ref('')            // 输入框文本
  const selectedImage = ref(null)      // 选中图片文件
  const activeModel = ref('deepseek')  // 模型：deepseek / qwen

  // ========== 重命名状态 ==========
  const editingId = ref(null)          // 正在编辑标题的对话 ID
  const renameText = ref('')           // 重命名输入框文本

  // ========== DOM 引用 ==========
  const msgContainer = ref(null)       // 消息容器的模板引用

  // ========== 上下文（可选注入） ==========
  const contextDeviceModel = ref(options.deviceModel || '')     // 设备型号上下文
  const contextTaskStep = ref(options.taskStep || '')           // 作业步骤上下文
  const contextTaskId = ref(options.taskId || null)             // 作业任务 ID
  const contextKnowledge = ref(options.knowledgeContext || '')  // 知识条目上下文

  // ========== 方法 ==========

  /** 加载历史对话列表 */
  async function loadConversations() {
    try { const { data } = await getConversations(); conversations.value = data } catch {}
  }

  /** 创建新对话 */
  async function newChat() {
    try {
      const { data } = await createConversation()
      conversations.value.unshift(data)
      convId.value = data.id
      messages.value = []
      uselessCount.value = 0
    } catch {}
  }

  /** 切换到指定对话 */
  async function switchChat(id) {
    convId.value = id
    uselessCount.value = 0
    try {
      const { data } = await getConversation(id)
      messages.value = data.messages || []
      // 统计末尾连续无用次数
      let count = 0
      for (let i = messages.value.length - 1; i >= 0; i--) {
        if (messages.value[i].feedback === 'useless') count++
        else if (messages.value[i].role === 'assistant') break
      }
      uselessCount.value = count
      await nextTick(); scrollBottom()
    } catch {}
  }

  /** 发送消息（extraContext 被 KeyboardEvent 污染时自动忽略） */
  async function send(extraContext = '') {
    // 防御：@keydown.enter 会将 KeyboardEvent 作为参数传入，需过滤
    if (extraContext && typeof extraContext !== 'string') extraContext = ''
    if ((!inputText.value.trim() && !selectedImage.value) || sending.value) return
    const text = inputText.value; inputText.value = ''
    const image = selectedImage.value; selectedImage.value = null

    // 拼装消息前缀：注入上下文信息
    let fullMessage = text
    const ctxParts = []
    if (contextDeviceModel.value) ctxParts.push(`[当前设备：${contextDeviceModel.value}]`)
    if (contextTaskStep.value) ctxParts.push(`[当前步骤：${contextTaskStep.value}]`)
    if (contextKnowledge.value) ctxParts.push(`[参考知识：${contextKnowledge.value}]`)
    if (extraContext) ctxParts.push(`[${extraContext}]`)
    if (ctxParts.length) fullMessage = ctxParts.join(' ') + ' ' + text

    messages.value.push({ id: Date.now(), role: 'user', content: text, image: image?.name })
    sending.value = true
    await nextTick(); scrollBottom()
    try {
      const { data } = await sendMessage(convId.value, fullMessage, image, activeModel.value)
      messages.value.pop()
      messages.value.push({ id: data.id, role: 'user', content: text })
      messages.value.push(data)
      await nextTick(); scrollBottom()
      const conv = conversations.value.find(c => c.id === convId.value)
      if (conv && conv.title === '新对话') conv.title = text.slice(0, 30) || '图片对话'
    } catch {
      messages.value.push({ id: Date.now() + 1, role: 'assistant', content: 'AI 服务暂时不可用，请稍后重试。' })
    }
    sending.value = false
  }

  /** 图片上传回调（阻止自动上传，仅保存文件引用） */
  function handleImageSelect(file) {
    selectedImage.value = file
    return false
  }

  /** 提交消息反馈 */
  async function doFeedback(msg, type) {
    let comment = ''
    if (type !== 'useful') {
      const result = await ElMessageBox.prompt('请简要说明修正建议（可选）', '反馈建议', { inputType: 'textarea', confirmButtonText: '提交', cancelButtonText: '取消' }).catch(() => null)
      // 用户叉掉或点取消 → 不提交反馈
      if (!result) return
      comment = result.value || ''
    }
    try {
      await submitFeedback(convId.value, type, comment)
      msg.feedback = type
      msg.feedback_comment = comment
      if (type === 'useless') uselessCount.value++
      ElMessage.success('反馈已提交')
    } catch {}
  }

  /** 渲染消息内容（结构化回复 → HTML） */
  function renderContent(m) {
    if (m.role === 'assistant' && m.structured_reply?.analysis) {
      const r = m.structured_reply
      let html = ''
      if (r.analysis) html += `<p><b>分析：</b>${r.analysis}</p>`
      if (r.causes?.length) html += `<p><b>可能原因：</b></p><ul>${r.causes.map(c => `<li>${c}</li>`).join('')}</ul>`
      if (r.solutions?.length) html += `<p><b>方案：</b></p><ul>${r.solutions.map(s => `<li>${s}</li>`).join('')}</ul>`
      return html || m.content
    }
    return m.content?.replace(/\n/g, '<br>') || ''
  }

  /** 删除对话 */
  async function delConv(c) {
    try {
      await ElMessageBox.confirm('确定删除此对话吗？', '确认删除', { type: 'warning' })
      await deleteConversation(c.id)
      conversations.value = conversations.value.filter(x => x.id !== c.id)
      if (convId.value === c.id) { convId.value = null; messages.value = [] }
      ElMessage.success('已删除')
    } catch {}
  }

  /** 开始重命名 */
  function startRename(c) {
    editingId.value = c.id
    renameText.value = c.title || '新对话'
  }

  /** 保存重命名 */
  async function doRename(c) {
    const title = renameText.value.trim()
    if (title && title !== c.title) {
      try { await renameConversation(c.id, title); c.title = title } catch {}
    }
    editingId.value = null
  }

  /** 滚动到消息底部 */
  function scrollBottom() {
    const el = msgContainer.value
    if (el) el.scrollTop = el.scrollHeight
  }

  /** 更新上下文（外部调用，用于运行时切换上下文） */
  function setContext(ctx) {
    if (ctx.deviceModel !== undefined) contextDeviceModel.value = ctx.deviceModel
    if (ctx.taskStep !== undefined) contextTaskStep.value = ctx.taskStep
    if (ctx.taskId !== undefined) contextTaskId.value = ctx.taskId
    if (ctx.knowledgeContext !== undefined) contextKnowledge.value = ctx.knowledgeContext
  }

  return {
    // 状态
    conversations, convId, messages, inputText, sending,
    msgContainer, uselessCount, editingId, renameText,
    selectedImage, activeModel,
    contextDeviceModel, contextTaskStep, contextTaskId, contextKnowledge,
    // 方法
    loadConversations, newChat, switchChat, send,
    handleImageSelect, doFeedback, renderContent,
    delConv, startRename, doRename, scrollBottom, setContext,
  }
}
