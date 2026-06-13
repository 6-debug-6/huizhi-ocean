<template>
  <div class="dashboard">
    <h2>管理后台仪表盘</h2>
    <el-row :gutter="20" style="margin-bottom:20px">
      <el-col :span="6"><el-card><div class="stat-num">{{ stats.knowledge_count }}</div><div class="stat-label">知识条目总数</div></el-card></el-col>
      <el-col :span="6"><el-card><div class="stat-num">{{ stats.pending_reviews }}</div><div class="stat-label">待审核案例</div></el-card></el-col>
      <el-col :span="6"><el-card><div class="stat-num">{{ stats.pending_tickets }}</div><div class="stat-label">待处理工单</div></el-card></el-col>
      <el-col :span="6"><el-card><div class="stat-num">{{ stats.active_users }}</div><div class="stat-label">活跃用户</div></el-card></el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-card header="快捷入口">
          <el-row :gutter="12">
            <el-col :span="8"><el-button style="width:100%" @click="$router.push('/admin/review')">审核队列</el-button></el-col>
            <el-col :span="8"><el-button style="width:100%" @click="$router.push('/admin/tickets')">客服工单</el-button></el-col>
            <el-col :span="8"><el-button style="width:100%" @click="$router.push('/admin/knowledge')">知识管理</el-button></el-col>
          </el-row>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card header="最近操作日志">
          <div v-for="log in recentLogs" :key="log.id" class="log-item">
            <span class="log-action">{{ log.action }}</span>
            <span class="log-time">{{ log.created_at?.slice(0, 16).replace('T', ' ') }}</span>
          </div>
          <div v-if="!recentLogs.length" class="empty">暂无日志</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getKnowledgeList } from '@/api/knowledge'
import { getReviewList } from '@/api/review'
import { getTicketList } from '@/api/tickets'
import api from '@/api'

const stats = reactive({ knowledge_count: 0, pending_reviews: 0, pending_tickets: 0, active_users: 0 })
const recentLogs = ref([])

onMounted(async () => {
  try {
    const [kl, rl, tl, logRes, userRes] = await Promise.all([
      getKnowledgeList({ page: 1, page_size: 1, status: 'all' }),
      getReviewList({ page: 1, page_size: 1, review_status: 'pending_initial' }),
      getTicketList({ page: 1, page_size: 1, status: 'pending' }),
      api.get('/api/v1/auth/logs', { params: { page: 1, page_size: 10 } }),
      api.get('/api/v1/auth/users'),
    ])
    stats.knowledge_count = kl.data.total
    stats.pending_reviews = rl.data.total
    stats.pending_tickets = tl.data.total
    stats.active_users = Array.isArray(userRes.data) ? userRes.data.filter(u => u.status === 'active').length : 1
    recentLogs.value = logRes.data?.items || []
  } catch { /* 后端可能未启动 */ }
})
</script>

<style scoped>
.stat-num { font-size: 32px; font-weight: 700; color: #1d4ed8; }
.stat-label { font-size: 13px; color: #999; margin-top: 4px; }
.log-item { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #f5f5f5; font-size: 13px; }
.log-time { color: #999; }
.empty { text-align: center; color: #999; padding: 20px; }
</style>
