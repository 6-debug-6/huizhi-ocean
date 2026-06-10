<template>
  <div class="ticket-list-page">
    <div class="page-header">
      <h2>我的客服工单</h2>
      <el-button type="primary" @click="showCreate = true">提交工单</el-button>
    </div>

    <!-- 状态筛选 -->
    <el-radio-group v-model="statusFilter" @change="fetchList" style="margin-bottom:16px">
      <el-radio-button value="">全部</el-radio-button>
      <el-radio-button value="pending">待处理</el-radio-button>
      <el-radio-button value="replied">已回复</el-radio-button>
      <el-radio-button value="resolved">已解决</el-radio-button>
    </el-radio-group>

    <!-- 工单列表 -->
    <el-table :data="tickets" v-loading="loading" @row-click="goDetail" style="cursor:pointer">
      <el-table-column prop="ticket_no" label="工单号" width="180" />
      <el-table-column prop="title" label="问题标题" />
      <el-table-column prop="reply_count" label="回复数" width="80" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status)">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="提交时间" width="180">
        <template #default="{ row }">{{ row.created_at?.slice(0, 16) }}</template>
      </el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="20" @current-change="fetchList" layout="prev,next" style="margin-top:16px" />

    <!-- 提交工单对话框 -->
    <el-dialog v-model="showCreate" title="提交工单" width="500px" @closed="resetForm">
      <el-form :model="form" label-width="80px">
        <el-form-item label="问题标题" required>
          <el-input v-model="form.title" placeholder="请简要描述问题" />
        </el-form-item>
        <el-form-item label="详细描述" required>
          <el-input v-model="form.description" type="textarea" :rows="5" placeholder="请详细描述遇到的问题" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="submitTicket" :loading="submitting">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getTicketList, createTicket } from '@/api/tickets'

const router = useRouter()
const tickets = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const statusFilter = ref('')
const showCreate = ref(false)
const submitting = ref(false)
const form = ref({ title: '', description: '' })

onMounted(() => fetchList())

async function fetchList() {
  loading.value = true
  try {
    const { data } = await getTicketList({ page: page.value, status: statusFilter.value })
    tickets.value = data.items; total.value = data.total
  } finally { loading.value = false }
}

async function submitTicket() {
  if (!form.value.title || !form.value.description) {
    ElMessage.warning('请填写标题和描述'); return
  }
  submitting.value = true
  try {
    await createTicket(form.value)
    ElMessage.success('工单已提交')
    showCreate.value = false
    fetchList()
  } finally { submitting.value = false }
}

function resetForm() { form.value = { title: '', description: '' } }
function goDetail(row) { router.push(`/tickets/${row.id}`) }
function statusTag(s) { return s === 'pending' ? 'danger' : s === 'replied' ? 'warning' : 'success' }
function statusLabel(s) { return { pending: '待处理', processing: '处理中', replied: '已回复', resolved: '已解决', closed: '已关闭' }[s] || s }
</script>
