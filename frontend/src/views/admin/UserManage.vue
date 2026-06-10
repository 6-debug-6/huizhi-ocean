<template>
  <div class="user-manage">
    <h2>用户管理</h2>
    <el-table :data="users" v-loading="loading">
      <el-table-column prop="username" label="用户名" width="120" />
      <el-table-column prop="name" label="姓名" width="100" />
      <el-table-column prop="employee_id" label="工号" width="100" />
      <el-table-column prop="team" label="班组" width="120" />
      <el-table-column prop="role" label="角色" width="80">
        <template #default="{ row }"><el-tag size="small">{{ { worker:'一线', admin:'管理员', expert:'专家' }[row.role] }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }"><el-tag :type="row.status==='active'?'success':row.status==='pending'?'warning':'danger'" size="small">{{ { pending:'待审核', active:'正常', disabled:'已禁用' }[row.status] }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" min-width="200">
        <template #default="{ row }">
          <el-button v-if="row.status==='pending'" size="small" type="success" @click="approveUser(row)" :loading="acting===row.id">审核通过</el-button>
          <el-button v-if="row.status==='active'" size="small" type="danger" @click="disableUser(row)" :loading="acting===row.id">禁用</el-button>
          <el-button v-if="row.status==='disabled'" size="small" @click="enableUser(row)" :loading="acting===row.id">启用</el-button>
          <el-button size="small" @click="resetPwd(row)">重置密码</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'

const users = ref([]); const loading = ref(false); const acting = ref(null)

onMounted(() => fetchUsers())

async function fetchUsers() {
  loading.value = true
  try {
    const { data } = await api.get('/api/v1/auth/users')
    users.value = data
  } catch { /* error handled by interceptor */ }
  finally { loading.value = false }
}

async function approveUser(row) {
  acting.value = row.id
  try {
    await api.put(`/api/v1/auth/users/${row.id}/status?status=active`)
    ElMessage.success('用户已审核通过')
    fetchUsers()
  } finally { acting.value = null }
}

async function disableUser(row) {
  await ElMessageBox.confirm('确定禁用此用户吗？', '确认')
  acting.value = row.id
  try {
    await api.put(`/api/v1/auth/users/${row.id}/status?status=disabled`)
    ElMessage.success('用户已禁用')
    fetchUsers()
  } finally { acting.value = null }
}

async function enableUser(row) {
  acting.value = row.id
  try {
    await api.put(`/api/v1/auth/users/${row.id}/status?status=active`)
    ElMessage.success('用户已启用')
    fetchUsers()
  } finally { acting.value = null }
}

async function resetPwd(row) {
  const { value } = await ElMessageBox.prompt('请输入新密码', '重置密码', { inputType: 'password' })
  if (value) {
    try {
      await api.post(`/api/v1/auth/users/${row.id}/reset-password`, { new_password: value })
      ElMessage.success('密码已重置')
    } catch { /* error handled by interceptor */ }
  }
}
</script>
