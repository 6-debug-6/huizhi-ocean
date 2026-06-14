<template>
  <div class="knowledge-manage">
    <div class="page-header">
      <h2>知识库管理</h2>
      <div style="display:flex;gap:8px">
        <el-button type="primary" @click="$router.push('/admin/knowledge/new')">新增知识</el-button>
        <el-button @click="showImport=true">导入 PDF</el-button>
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
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="$router.push(`/admin/knowledge/${row.id}/edit`)">编辑</el-button>
          <el-dropdown trigger="click" style="margin-left:8px">
            <el-button size="small">更多 ▾</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="$router.push(`/admin/knowledge/${row.id}/versions`)">版本历史</el-dropdown-item>
                <el-dropdown-item v-if="row.status!=='archived'" @click="doArchive(row)">归档</el-dropdown-item>
                <el-dropdown-item divided @click="doDelete(row)" style="color:#dc2626">删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="20" @current-change="fetchList" layout="prev,next" style="margin-top:16px" />

    <!-- PDF 导入对话框 -->
    <el-dialog v-model="showImport" title="导入 PDF 手册" width="480px" @close="resetImport">
      <el-form :model="importForm" label-width="80px">
        <el-form-item label="PDF 文件" required>
          <el-upload :auto-upload="false" :limit="1" accept=".pdf" :on-change="onPdfChange" :file-list="importForm.pdfList">
            <el-button type="primary">选择文件</el-button>
            <template #tip><div style="font-size:12px;color:#999">支持 PDF 格式，最大 50MB</div></template>
          </el-upload>
        </el-form-item>
        <el-form-item label="设备型号">
          <el-input v-model="importForm.deviceModel" placeholder="如：XX型柴油发动机" />
        </el-form-item>
      </el-form>
      <div v-if="importResult" class="import-result">
        <el-divider />
        <p v-html="importResult"></p>
      </div>
      <template #footer>
        <el-button @click="showImport=false">关闭</el-button>
        <el-button type="primary" @click="doImport" :loading="importing">开始导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import { getKnowledgeList, archiveKnowledge, deleteKnowledge } from '@/api/knowledge'

const items = ref([]); const loading = ref(false); const total = ref(0); const page = ref(1)
const keyword = ref(''); const statusFilter = ref('')

// ========== PDF 导入 ==========
const showImport = ref(false)
const importing = ref(false)
const importResult = ref('')
const importForm = reactive({ pdfList: [], deviceModel: '', file: null })

function onPdfChange(file) {
  importForm.file = file.raw
  importForm.pdfList = [file]
}

function resetImport() {
  importForm.pdfList = []
  importForm.deviceModel = ''
  importForm.file = null
  importResult.value = ''
}

async function doImport() {
  if (!importForm.file) { ElMessage.warning('请选择PDF文件'); return }
  importing.value = true
  importResult.value = ''
  try {
    const fd = new FormData()
    fd.append('file', importForm.file)
    if (importForm.deviceModel) fd.append('device_model', importForm.deviceModel)
    const { data } = await api.post('/api/v1/import/pdf', fd)
    importResult.value = `
      <b>导入成功！</b><br>
      知识条目 ID：${data.entry_id}<br>
      片段总数：${data.chunks_total}<br>
      向量化：${data.chunks_vectorized}<br>
      ${data.images_described ? `图片描述：${data.images_described} 张<br>` : ''}
      <a href="/admin/knowledge/${data.entry_id}/edit">点击编辑此条目 →</a>
    `
    fetchList()
  } catch (e) {
    importResult.value = `<span style="color:#dc2626">导入失败：${e.response?.data?.detail || e.message}</span>`
  }
  importing.value = false
}

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

async function doDelete(row) {
  await ElMessageBox.confirm('确定永久删除此条目吗？所有版本也将被删除，此操作不可撤销。', '确认删除', { type: 'error' })
  await deleteKnowledge(row.id)
  ElMessage.success('已删除')
  fetchList()
}
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.import-result { font-size: 13px; line-height: 1.8; }
.import-result :deep(a) { color: #1d4ed8; }
</style>
