<template>
  <div class="knowledge-manage">
    <div class="page-header">
      <h2>知识库管理</h2>
      <div>
        <el-button type="primary" @click="$router.push('/admin/knowledge/new')">新增知识</el-button>
      </div>
    </div>

    <!-- 筛选栏 -->
    <el-form :inline="true" style="margin-bottom:16px">
      <el-form-item><el-input v-model="keyword" placeholder="搜索标题/摘要" clearable @clear="fetchList" @keyup.enter="fetchList" /></el-form-item>
      <el-form-item><el-select v-model="statusFilter" placeholder="状态" clearable @change="fetchList" style="width:140px">
        <el-option label="已发布" value="published" /><el-option label="草稿" value="draft" /><el-option label="已归档" value="archived" />
      </el-select></el-form-item>
      <el-form-item><el-button @click="fetchList">搜索</el-button></el-form-item>
    </el-form>

    <el-table :data="items" v-loading="loading">
      <el-table-column prop="title" label="标题">
        <template #default="{ row }"><router-link :to="`/admin/knowledge/${row.id}/edit`">{{ row.title }}</router-link></template>
      </el-table-column>
      <el-table-column prop="source" label="来源" width="100">
        <template #default="{ row }">{{ { manual:'手动', pdf_import:'PDF导入', user_upload:'用户上传', ticket:'工单转化' }[row.source] }}</template>
      </el-table-column>
      <el-table-column prop="current_version" label="版本" width="80" />
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }"><el-tag :type="row.status==='published'?'success':row.status==='draft'?'info':'warning'" size="small">{{ { published:'已发布', draft:'草稿', archived:'已归档' }[row.status] }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button size="small" @click="$router.push(`/admin/knowledge/${row.id}/edit`)">编辑</el-button>
          <el-button size="small" @click="$router.push(`/admin/knowledge/${row.id}/versions`)">版本</el-button>
          <el-button size="small" type="danger" @click="doArchive(row)" v-if="row.status!=='archived'">归档</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="20" @current-change="fetchList" layout="prev,next" style="margin-top:16px" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getKnowledgeList, archiveKnowledge } from '@/api/knowledge'

const items = ref([]); const loading = ref(false); const total = ref(0); const page = ref(1)
const keyword = ref(''); const statusFilter = ref('')

onMounted(() => fetchList())

async function fetchList() {
  loading.value = true
  try {
    const { data } = await getKnowledgeList({ page: page.value, keyword: keyword.value, status: statusFilter.value || 'all' })
    items.value = data.items; total.value = data.total
  } finally { loading.value = false }
}

async function doArchive(row) {
  await ElMessageBox.confirm('确定归档此条目吗？归档后用户端不再可见。', '确认归档')
  await archiveKnowledge(row.id)
  ElMessage.success('已归档')
  fetchList()
}
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
</style>
