<template>
  <div class="model-config">
    <h2>大模型配置管理</h2>
    <p class="tip">支持动态配置云端 API 或本地部署的 LLM 服务。激活配置即时生效，无需重启。</p>

    <div style="margin-bottom:12px"><el-button type="primary" @click="addConfig">新增配置</el-button></div>

    <el-alert
      v-if="!configs.length && !loading"
      title="尚未配置任何大模型"
      type="warning"
      description="请点击「新增配置」添加模型。系统会自动根据模型名称识别用途（含 'deepseek' 或 '文本' → 文本对话，含 'qwen'/'vl'/'视觉' → 图文理解，含 'embed'/'bge' → 向量检索）。"
      show-icon
      style="margin-bottom:16px"
    />
    <el-table :data="configs" v-loading="loading">
      <el-table-column prop="model_name" label="模型名称" min-width="160" />
      <el-table-column prop="model_type" label="类型" width="100">
        <template #default="{ row }"><el-tag size="small">{{ row.model_type === 'cloud' ? '云端API' : '本地部署' }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="api_base" label="API 地址" min-width="220" />
      <el-table-column prop="api_key_masked" label="API Key" width="140" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '● 激活' : '○ 未激活' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="updated_at" label="更新时间" width="150">
        <template #default="{ row }">{{ row.updated_at?.slice(0,16)?.replace('T',' ') }}</template>
      </el-table-column>
      <el-table-column label="操作" width="300" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="editConfig(row)">编辑</el-button>
          <el-button size="small" @click="doTest(row)" :loading="testingId===row.id">测试</el-button>
          <el-button v-if="!row.is_active" size="small" type="primary" @click="doActivate(row)">激活</el-button>
          <el-button size="small" type="danger" @click="doDelete(row)" :disabled="row.is_active">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="showDialog" :title="editingId ? '编辑配置' : '新增配置'" width="500px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="模型名称" required>
          <el-input v-model="form.model_name" placeholder="如：deepseek-chat、qwen-vl-max、gpt-4o..." />
        </el-form-item>
        <el-form-item label="模型类型" required>
          <el-radio-group v-model="form.model_type">
            <el-radio label="cloud">云端 API</el-radio>
            <el-radio label="local">本地部署</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="API 地址" required>
          <el-input v-model="form.api_base" :placeholder="form.model_type==='cloud' ? 'https://api.deepseek.com' : 'http://localhost:8000'" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="form.api_key" type="password" show-password placeholder="sk-..." />
        </el-form-item>
        <el-divider />
        <el-form-item label="Temperature">
          <el-slider v-model="form.parameters.temperature" :min="0" :max="1" :step="0.1" show-input style="width:240px" />
        </el-form-item>
        <el-form-item label="Max Tokens">
          <el-input-number v-model="form.parameters.max_tokens" :min="512" :max="32768" :step="1024" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog=false">取消</el-button>
        <el-button type="primary" @click="saveConfig" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'

const configs = ref([]); const loading = ref(false)
const showDialog = ref(false); const editingId = ref(null); const saving = ref(false)
const testingId = ref(null)
const form = reactive({
  model_name: '', model_type: 'cloud', api_base: '', api_key: '',
  parameters: { temperature: 0.3, max_tokens: 8192 }
})

onMounted(() => loadConfigs())

async function loadConfigs() {
  loading.value = true
  try { const { data } = await api.get('/api/v1/models/configs'); configs.value = data || [] } catch {}
  loading.value = false
}

function addConfig() {
  editingId.value = null
  form.model_name = ''; form.model_type = 'cloud'
  form.api_base = ''; form.api_key = ''
  form.parameters = { temperature: 0.3, max_tokens: 8192 }
  showDialog.value = true
}

function editConfig(row) {
  editingId.value = row.id
  form.model_name = row.model_name; form.model_type = row.model_type
  form.api_base = row.api_base || ''; form.api_key = ''
  form.parameters = { ...(row.parameters || { temperature: 0.3, max_tokens: 4096 }) }
  showDialog.value = true
}

async function saveConfig() {
  if (!form.model_name || !form.api_base) { ElMessage.warning('请填写模型名称和API地址'); return }
  saving.value = true
  try {
    const payload = { ...form }
    if (!payload.api_key) delete payload.api_key  // 不提交空key
    if (editingId.value) {
      await api.put(`/api/v1/models/configs/${editingId.value}`, payload)
      ElMessage.success('已更新')
    } else {
      await api.post('/api/v1/models/configs', payload)
      ElMessage.success('已创建')
    }
    showDialog.value = false
    loadConfigs()
  } catch {}
  saving.value = false
}

async function doActivate(row) {
  try {
    await api.post(`/api/v1/models/configs/${row.id}/activate`)
    ElMessage.success(`已激活 ${row.model_name}`)
    loadConfigs()
  } catch {}
}

async function doTest(row) {
  testingId.value = row.id
  try {
    const { data } = await api.post(`/api/v1/models/configs/${row.id}/test`)
    if (data.status === 'ok') {
      ElMessage.success(data.message)
    } else {
      ElMessage.error(data.message)
    }
  } catch {}
  testingId.value = null
}

async function doDelete(row) {
  if (row.is_active) { ElMessage.warning('不能删除已激活的配置'); return }
  try {
    await ElMessageBox.confirm(`确定删除配置"${row.model_name}"吗？`, '确认删除', { type: 'warning' })
    await api.post(`/api/v1/models/configs/${row.id}/delete`)
    ElMessage.success('已删除')
    loadConfigs()
  } catch {}
}
</script>

<style scoped>
.tip { color: #999; font-size: 13px; margin-bottom: 16px; }
</style>
