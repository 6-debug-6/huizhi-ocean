<template>
  <div class="ticket-manage">
    <h2>客服工单管理</h2>
    <el-radio-group v-model="statusFilter" @change="fetchList" style="margin-bottom:16px">
      <el-radio-button value="">全部</el-radio-button>
      <el-radio-button value="pending">待处理</el-radio-button>
      <el-radio-button value="processing">处理中</el-radio-button>
      <el-radio-button value="replied">已回复</el-radio-button>
      <el-radio-button value="resolved">已解决</el-radio-button>
    </el-radio-group>

    <el-table :data="tickets" v-loading="loading" @row-click="goDetail" style="cursor:pointer">
      <el-table-column prop="ticket_no" label="工单号" width="180" />
      <el-table-column prop="title" label="标题" />
      <el-table-column prop="creator_name" label="提交人" width="100" />
      <el-table-column prop="assignee_name" label="处理人" width="100" />
      <el-table-column prop="reply_count" label="回复" width="60" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="tag(row.status)">{{ label(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="提交时间" width="170">
        <template #default="{ row }">{{ row.created_at?.slice(0, 16).replace('T', ' ') }}</template>
      </el-table-column>
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="danger" @click.stop="delTicket(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="20" @current-change="fetchList" layout="prev,next" style="margin-top:16px" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTicketList, deleteTicket } from '@/api/tickets'

const router = useRouter()
const tickets = ref([]); const loading = ref(false); const total = ref(0); const page = ref(1); const statusFilter = ref('pending')

onMounted(() => fetchList())

async function fetchList() {
  loading.value = true
  try {
    const { data } = await getTicketList({ page: page.value, status: statusFilter.value })
    tickets.value = data.items; total.value = data.total
  } finally { loading.value = false }
}

function goDetail(row) { router.push(`/admin/tickets/${row.id}`) }

async function delTicket(row) {
  try {
    await ElMessageBox.confirm(`确定删除工单"${row.ticket_no}"吗？所有回复也将被删除，此操作不可撤销。`, '确认删除', { type: 'warning' })
    await deleteTicket(row.id)
    ElMessage.success('工单已删除')
    fetchList()
  } catch {}
}
function tag(s) { return s === 'pending' ? 'danger' : s === 'replied' ? 'warning' : 'success' }
function label(s) { return { pending: '待处理', processing: '处理中', replied: '已回复', resolved: '已解决', closed: '已关闭' }[s] || s }
</script>
