<template>
  <div class="audit-logs">
    <h2>操作日志</h2>
    <el-table :data="logs" v-loading="loading">
      <el-table-column prop="created_at" label="时间" width="170"><template #default="{ row }">{{ formatDateTime(row.created_at) }}</template></el-table-column>
      <el-table-column prop="user_name" label="操作人" width="100" />
      <el-table-column prop="action" label="操作类型" width="150" />
      <el-table-column prop="target_type" label="操作对象" width="100" />
      <el-table-column prop="detail" label="详情" min-width="200" />
      <el-table-column label="操作" width="70">
        <template #default="{ row }"><el-button size="small" type="danger" plain @click="delLog(row)">删除</el-button></template>
      </el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="10" @current-change="fetchLogs" layout="total, prev, pager, next, jumper" style="margin-top:16px" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import { formatDateTime } from '@/utils/helpers'

const logs = ref([]); const loading = ref(false); const total = ref(0); const page = ref(1)

onMounted(() => fetchLogs())

async function delLog(row) {
  try {
    await ElMessageBox.confirm('确定删除此日志吗？', '确认')
    await api.post(`/api/v1/auth/logs/${row.id}/delete`)
    ElMessage.success('已删除')
    fetchLogs()
  } catch {}
}

async function fetchLogs() {
  loading.value = true
  try {
    const { data } = await api.get('/api/v1/auth/logs', { params: { page: page.value, page_size: 10 } })
    logs.value = data.items; total.value = data.total
  } catch {}
  loading.value = false
}
</script>

<style scoped>
</style>
