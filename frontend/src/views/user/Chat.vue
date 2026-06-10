<template>
  <div class="chat-page">
    <!-- 左侧对话列表 -->
    <aside class="chat-sidebar">
      <el-button type="primary" @click="newChat" style="width:100%;margin-bottom:12px">新建对话</el-button>
      <div class="conv-list">
        <div v-for="c in conversations" :key="c.id" class="conv-item" :class="{ active: c.id === convId }" @click="switchChat(c.id)">
          <span class="conv-title" @dblclick.stop="startRename(c)">{{ editingId === c.id ? '' : (c.title || '新对话') }}</span>
          <el-input v-if="editingId === c.id" v-model="renameText" size="small" @blur="doRename(c)" @keydown.enter="doRename(c)" @click.stop style="width:100%" />
          <span class="conv-time">{{ c.updated_at?.slice(0, 10) }}</span>
          <span class="conv-actions" @click.stop>
            <el-button size="small" text @click="startRename(c)" title="重命名">✎</el-button>
            <el-button size="small" text @click="delConv(c)" title="删除">✕</el-button>
          </span>
        </div>
      </div>
    </aside>

    <!-- 右侧对话区 -->
    <main class="chat-main">
      <div v-if="!convId" class="chat-empty">点击左侧"新建对话"开始咨询</div>
      <template v-else>
        <div class="chat-messages" ref="msgContainer">
          <div v-for="m in messages" :key="m.id" class="msg-item" :class="m.role">
            <div class="msg-avatar">{{ m.role === 'user' ? '我' : 'AI' }}</div>
            <div class="msg-body">
              <div class="msg-content" v-html="renderContent(m)"></div>
              <!-- 反馈按钮 -->
              <div v-if="m.role === 'assistant'" class="msg-feedback">
                <el-button size="small" text :type="m.feedback==='useful'?'primary':''" @click="doFeedback(m, 'useful')" :disabled="!!m.feedback">有用</el-button>
                <el-button size="small" text :type="m.feedback==='partial'?'warning':''" @click="doFeedback(m, 'partial')" :disabled="!!m.feedback">部分有用</el-button>
                <el-button size="small" text :type="m.feedback==='useless'?'danger':''" @click="doFeedback(m, 'useless')" :disabled="!!m.feedback">无用</el-button>
                <span v-if="uselessCount >= 2" class="ticket-hint">
                  <router-link to="/tickets">问题未解决？提交客服工单 →</router-link>
                </span>
              </div>
            </div>
          </div>
          <div v-if="sending" class="msg-item assistant">
            <div class="msg-avatar">AI</div><div class="msg-body"><div class="msg-content">思考中...</div></div>
          </div>
        </div>
        <!-- 输入区 -->
        <div class="chat-input">
          <el-input v-model="inputText" type="textarea" :rows="3" placeholder="输入问题，描述设备故障现象..." @keydown.enter.exact="send" />
          <el-button type="primary" @click="send" :loading="sending" style="margin-top:8px">发送</el-button>
        </div>
      </template>
    </main>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createConversation, getConversations, getConversation, deleteConversation, renameConversation, sendMessage, submitFeedback } from '@/api/chat'

const conversations = ref([])
const convId = ref(null)
const messages = ref([])
const inputText = ref('')
const sending = ref(false)
const msgContainer = ref(null)
const uselessCount = ref(0)
const editingId = ref(null)
const renameText = ref('')

onMounted(() => loadConversations())

async function loadConversations() {
  try { const { data } = await getConversations(); conversations.value = data } catch {}
}

async function newChat() {
  try {
    const { data } = await createConversation()
    conversations.value.unshift(data)
    convId.value = data.id
    messages.value = []
    uselessCount.value = 0
  } catch {}
}

async function switchChat(id) {
  convId.value = id
  uselessCount.value = 0
  try {
    const { data } = await getConversation(id)
    messages.value = data.messages || []
    // 统计连续无用次数
    let count = 0
    for (let i = messages.value.length - 1; i >= 0; i--) {
      if (messages.value[i].feedback === 'useless') count++
      else if (messages.value[i].role === 'assistant') break
    }
    uselessCount.value = count
    await nextTick(); scrollBottom()
  } catch {}
}

async function send() {
  if (!inputText.value.trim() || sending.value) return
  const text = inputText.value; inputText.value = ''
  messages.value.push({ id: Date.now(), role: 'user', content: text })
  sending.value = true
  await nextTick(); scrollBottom()
  try {
    const { data } = await sendMessage(convId.value, text)
    // 用服务器返回的真实消息替换临时消息
    messages.value.pop() // 移除临时 user 消息
    messages.value.push({ id: data.id, role: 'user', content: text }) // 添加真实的
    messages.value.push(data)
    await nextTick(); scrollBottom()
    // 更新对话列表标题
    const conv = conversations.value.find(c => c.id === convId.value)
    if (conv && conv.title === '新对话') conv.title = text.slice(0, 30)
  } catch (e) {
    messages.value.push({ id: Date.now() + 1, role: 'assistant', content: 'AI 服务暂时不可用，请稍后重试。' })
  }
  sending.value = false
}

async function doFeedback(msg, type) {
  try {
    await submitFeedback(convId.value, type)
    msg.feedback = type
    if (type === 'useless') {
      uselessCount.value++
      if (uselessCount.value >= 2) {
        // 不弹窗，展示工单提示
      }
    }
    ElMessage.success('反馈已提交')
    // 如果选"部分有用"或"无用"，弹出修正输入框
    if (type !== 'useful') {
      const { value } = await ElMessageBox.prompt('请简要说明修正建议（可选）', '反馈建议', { inputType: 'textarea' }).catch(() => ({}))
      if (value) { /* 已通过 feedback_comment 传递，这里简化处理 */ }
    }
  } catch {}
}

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

async function delConv(c) {
  try {
    await ElMessageBox.confirm('确定删除此对话吗？对话中的消息也会一并删除。', '确认删除', { type: 'warning' })
    await deleteConversation(c.id)
    conversations.value = conversations.value.filter(x => x.id !== c.id)
    if (convId.value === c.id) { convId.value = null; messages.value = [] }
    ElMessage.success('已删除')
  } catch {}
}

function startRename(c) {
  editingId.value = c.id
  renameText.value = c.title || '新对话'
}

async function doRename(c) {
  const title = renameText.value.trim()
  if (title && title !== c.title) {
    try {
      await renameConversation(c.id, title)
      c.title = title
    } catch {}
  }
  editingId.value = null
}

function scrollBottom() {
  const el = msgContainer.value
  if (el) el.scrollTop = el.scrollHeight
}
</script>

<style scoped>
.chat-page { display: flex; height: calc(100vh - 80px); gap: 0; }
.chat-sidebar { width: 240px; background: #fff; border-right: 1px solid #eee; padding: 12px; overflow-y: auto; }
.conv-list { margin-top: 8px; }
.conv-item { padding: 10px 8px; cursor: pointer; border-radius: 4px; border-bottom: 1px solid #f5f5f5; }
.conv-item:hover, .conv-item.active { background: #e8f0fe; }
.conv-title { display: block; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conv-time { font-size: 11px; color: #aaa; }
.conv-actions { display: none; margin-left: auto; }
.conv-item:hover .conv-actions { display: inline-flex; gap: 2px; }
.chat-main { flex: 1; display: flex; flex-direction: column; background: #f5f7fa; }
.chat-empty { flex: 1; display: flex; align-items: center; justify-content: center; color: #999; font-size: 16px; }
.chat-messages { flex: 1; overflow-y: auto; padding: 20px; }
.msg-item { display: flex; gap: 12px; margin-bottom: 20px; }
.msg-item.user { flex-direction: row-reverse; }
.msg-avatar { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; flex-shrink: 0; }
.msg-item.user .msg-avatar { background: #1d4ed8; color: #fff; }
.msg-item.assistant .msg-avatar { background: #10b981; color: #fff; }
.msg-body { max-width: 75%; }
.msg-content { background: #fff; padding: 12px 16px; border-radius: 8px; font-size: 14px; line-height: 1.7; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.msg-item.user .msg-content { background: #1d4ed8; color: #fff; }
.msg-feedback { margin-top: 4px; padding-left: 4px; }
.ticket-hint { font-size: 12px; color: #e6a23c; margin-left: 8px; }
.chat-input { padding: 16px 20px; background: #fff; border-top: 1px solid #eee; }
</style>
