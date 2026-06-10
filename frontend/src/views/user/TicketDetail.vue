<template>
  <div class="ticket-detail-page">
    <el-button @click="$router.back()" style="margin-bottom:16px">← 返回列表</el-button>
    <div v-loading="loading">
      <h2>{{ detail.ticket_no }} - {{ detail.title }}</h2>
      <p class="meta">提交人：{{ detail.creator_name }} | 状态：<el-tag :type="statusTag(detail.status)">{{ statusLabel(detail.status) }}</el-tag> | {{ detail.created_at?.slice(0, 16) }}</p>

      <!-- 问题描述 -->
      <el-card header="问题描述" style="margin:16px 0"><div v-html="detail.description"></div></el-card>

      <!-- 回复列表 -->
      <el-card header="回复记录" style="margin:16px 0">
        <div v-if="!detail.replies?.length" class="empty">暂无回复，请耐心等待</div>
        <div v-for="r in detail.replies" :key="r.id" class="reply-item">
          <div class="reply-meta">{{ r.replier_name }} · {{ r.created_at?.slice(0, 16) }}</div>
          <div class="reply-content" v-html="r.content"></div>
        </div>
      </el-card>

      <!-- 确认解决 -->
      <div v-if="detail.status === 'replied'" style="text-align:center;margin:16px 0">
        <el-button type="success" @click="markResolved" :loading="actionLoading">确认已解决</el-button>
        <span style="color:#999;margin-left:12px">如果回复解决了您的问题，请点击确认</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getTicketDetail, updateTicketStatus } from '@/api/tickets'

const route = useRoute()
const detail = ref({})
const loading = ref(false)
const actionLoading = ref(false)

onMounted(() => fetchDetail())

async function fetchDetail() {
  loading.value = true
  try {
    const { data } = await getTicketDetail(route.params.id)
    detail.value = data
  } finally { loading.value = false }
}

async function markResolved() {
  actionLoading.value = true
  try {
    await updateTicketStatus(detail.value.id, { status: 'resolved' })
    ElMessage.success('已标记为已解决')
    fetchDetail()
  } finally { actionLoading.value = false }
}

function statusTag(s) { return s === 'pending' ? 'danger' : s === 'replied' ? 'warning' : 'success' }
function statusLabel(s) { return { pending: '待处理', processing: '处理中', replied: '已回复', resolved: '已解决', closed: '已关闭' }[s] || s }
</script>

<style scoped>
.meta { color: #999; font-size: 14px; }
.reply-item { padding: 12px 0; border-bottom: 1px solid #f0f0f0; }
.reply-meta { color: #1d4ed8; font-size: 13px; margin-bottom: 8px; }
.reply-content { font-size: 14px; line-height: 1.8; }
.empty { text-align: center; color: #999; padding: 40px; }
</style>
