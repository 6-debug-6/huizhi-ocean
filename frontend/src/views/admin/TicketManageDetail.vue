<template>
  <div class="ticket-detail">
    <el-button @click="$router.back()" style="margin-bottom:16px">← 返回</el-button>
    <div v-loading="loading">
      <h2>{{ detail.ticket_no }} - {{ detail.title }}</h2>
      <p class="meta">提交人：{{ detail.creator_name }} | 状态：<el-tag :type="tag(detail.status)">{{ label(detail.status) }}</el-tag></p>

      <!-- 问题描述 -->
      <el-card header="问题描述" style="margin:16px 0"><div v-html="detail.description"></div></el-card>

      <!-- 回复链 -->
      <el-card header="回复记录" style="margin:16px 0">
        <div v-for="r in detail.replies" :key="r.id" class="reply-item">
          <div class="reply-meta">{{ r.replier_name }} · {{ r.created_at?.slice(0, 16).replace('T', ' ') }}</div>
          <div v-html="r.content" class="reply-content"></div>
        </div>
      </el-card>

      <!-- 回复表单 -->
      <el-card header="回复" style="margin:16px 0" v-if="canReply">
        <el-input v-model="replyContent" type="textarea" :rows="4" placeholder="输入回复内容..." />
        <div style="margin-top:12px;display:flex;gap:12px">
          <el-button type="primary" @click="doReply" :loading="replying">发送回复</el-button>
          <el-button v-if="detail.status==='resolved'" type="success" @click="toKnowledge" :loading="converting">转为知识条目</el-button>
          <el-button v-if="detail.status!=='closed'" type="danger" plain @click="closeTicket">关闭工单</el-button>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTicketDetail, replyTicket, updateTicketStatus, ticketToKnowledge } from '@/api/tickets'

const route = useRoute()
const detail = ref({}); const loading = ref(false); const replying = ref(false); const converting = ref(false)
const replyContent = ref('')

const canReply = computed(() => !['closed'].includes(detail.value.status))

onMounted(() => fetchDetail())

async function fetchDetail() {
  loading.value = true
  try { const { data } = await getTicketDetail(route.params.id); detail.value = data } finally { loading.value = false }
}

async function doReply() {
  if (!replyContent.value.trim()) { ElMessage.warning('请输入回复内容'); return }
  replying.value = true
  try {
    await replyTicket(detail.value.id, { content: replyContent.value })
    ElMessage.success('回复已发送')
    replyContent.value = ''
    fetchDetail()
  } finally { replying.value = false }
}

async function toKnowledge() {
  converting.value = true
  try {
    const { data } = await ticketToKnowledge(detail.value.id)
    ElMessage.success(data.message)
  } finally { converting.value = false }
}

async function closeTicket() {
  await ElMessageBox.confirm('确定关闭此工单吗？', '确认')
  await updateTicketStatus(detail.value.id, { status: 'closed' })
  ElMessage.success('工单已关闭')
  fetchDetail()
}

function tag(s) { return s === 'pending' ? 'danger' : s === 'replied' ? 'warning' : 'success' }
function label(s) { return { pending: '待处理', processing: '处理中', replied: '已回复', resolved: '已解决', closed: '已关闭' }[s] || s }
</script>

<style scoped>
.meta { color: #999; font-size: 14px; }
.reply-item { padding: 12px 0; border-bottom: 1px solid #f0f0f0; }
.reply-meta { color: #1d4ed8; font-size: 13px; margin-bottom: 8px; }
.reply-content { font-size: 14px; line-height: 1.8; }
</style>
