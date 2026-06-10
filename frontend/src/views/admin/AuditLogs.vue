<template>
  <div class="audit-logs">
    <h2>操作日志</h2>
    <el-form :inline="true" style="margin-bottom:16px">
      <el-form-item><el-date-picker v-model="dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" /></el-form-item>
      <el-form-item><el-select v-model="actionFilter" placeholder="操作类型" clearable style="width:140px">
        <el-option label="用户审核" value="user.approve" /><el-option label="知识修改" value="knowledge.edit" /><el-option label="权限变更" value="role.change" />
      </el-select></el-form-item>
      <el-form-item><el-button @click="fetchLogs">查询</el-button></el-form-item>
      <el-form-item><el-button @click="exportLogs">导出CSV</el-button></el-form-item>
    </el-form>

    <el-table :data="logs" v-loading="loading">
      <el-table-column prop="created_at" label="时间" width="170"><template #default="{ row }">{{ row.created_at?.slice(0, 16).replace('T', ' ') }}</template></el-table-column>
      <el-table-column prop="action" label="操作类型" width="130" />
      <el-table-column prop="target_type" label="操作对象" width="130" />
      <el-table-column prop="detail" label="详情" />
      <el-table-column prop="ip_address" label="IP地址" width="130" />
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="20" @current-change="fetchLogs" layout="prev,next" style="margin-top:16px" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const logs = ref([]); const loading = ref(false); const total = ref(0); const page = ref(1)
const dateRange = ref([]); const actionFilter = ref('')

function fetchLogs() { loading.value = true; /* 待后端实现 */ loading.value = false }
function exportLogs() { ElMessage.info('导出功能实现中') }
</script>
