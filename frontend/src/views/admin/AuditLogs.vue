<template>
  <div class="audit-logs">
    <h2>操作日志</h2>
    <el-table :data="logs" v-loading="loading">
      <el-table-column prop="created_at" label="时间" width="170"><template #default="{ row }">{{ row.created_at?.slice(0, 16).replace('T', ' ') }}</template></el-table-column>
      <el-table-column prop="user_name" label="操作人" width="100" />
      <el-table-column prop="action" label="操作类型" width="150" />
      <el-table-column prop="target_type" label="操作对象" width="100" />
      <el-table-column prop="detail" label="详情" min-width="200" />
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="20" @current-change="fetchLogs" layout="prev,next" style="margin-top:16px" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/api'

const logs = ref([]); const loading = ref(false); const total = ref(0); const page = ref(1)

onMounted(() => fetchLogs())

async function fetchLogs() {
  loading.value = true
  try {
    const { data } = await api.get('/api/v1/auth/logs', { params: { page: page.value, page_size: 20 } })
    logs.value = data.items; total.value = data.total
  } catch {}
  loading.value = false
}
</script>

<style scoped>
</style>
