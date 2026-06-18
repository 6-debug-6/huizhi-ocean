<template>
  <div class="template-manage">
    <h2>检修流程模板管理</h2>
    <div style="margin-bottom:12px"><el-button type="primary" @click="addTemplate">新增模板</el-button></div>
    <el-table :data="templates" v-loading="loading">
      <el-table-column prop="name" label="模板名称" />
      <el-table-column prop="maintenance_level" label="检修等级" width="100" />
      <el-table-column label="设备型号" min-width="200">
        <template #default="{ row }">
          <el-tag v-for="dm in row.device_models" :key="dm" size="small" style="margin-right:4px">{{ dm }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="step_count" label="步骤数" width="80" />
      <el-table-column prop="version" label="版本" width="80" />
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }"><el-tag :type="row.status==='published'?'success':'info'" size="small">{{ { published:'已发布', draft:'草稿' }[row.status] }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="220">
        <template #default="{ row }">
          <el-button size="small" @click="editTemplate(row)">编辑</el-button>
          <el-button size="small" type="primary" @click="editSteps(row)">步骤</el-button>
          <el-button size="small" type="danger" @click="delTemplate(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 模板基本信息编辑对话框 -->
    <el-dialog v-model="showDialog" :title="editingId ? '编辑模板' : '新增模板'" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="模板名称" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="检修等级">
          <el-select v-model="form.maintenance_level" style="width:100%">
            <el-option label="日常检修" value="日常" />
            <el-option label="定修" value="定修" />
            <el-option label="大修" value="大修" />
          </el-select>
        </el-form-item>
        <el-form-item label="设备型号">
          <el-select v-model="form.device_models" multiple filterable allow-create placeholder="选择或输入设备型号" style="width:100%">
            <el-option v-for="dm in deviceOptions" :key="dm" :label="dm" :value="dm" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog=false">取消</el-button>
        <el-button type="primary" @click="saveTemplate" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 步骤编辑器对话框 -->
    <el-dialog v-model="showSteps" title="步骤编辑" width="700px" destroy-on-close>
      <div v-for="(step, i) in stepsForm.steps" :key="i" class="step-editor-item">
        <div class="step-header">
          <strong>步骤 {{ i + 1 }}</strong>
          <el-button size="small" type="danger" text @click="removeStep(i)">删除</el-button>
        </div>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-input v-model="step.phase" placeholder="阶段（如：拆卸）" size="small" />
          </el-col>
          <el-col :span="16">
            <el-input v-model="step.title" placeholder="步骤名称" size="small" />
          </el-col>
        </el-row>
        <el-input v-model="step.content" placeholder="操作说明" type="textarea" :rows="2" size="small" style="margin-top:6px" />
        <div style="margin-top:6px">
          <span style="font-size:12px;color:#666">合规校验项：</span>
          <el-tag v-for="(ci, j) in (step.compliance_items || [])" :key="j" closable size="small" @close="step.compliance_items.splice(j,1)" style="margin-right:4px">{{ ci }}</el-tag>
          <el-button size="small" text @click="addComplianceItem(step)">+添加</el-button>
        </div>
      </div>
      <el-button type="primary" plain @click="addStep" style="margin-top:12px">+ 添加步骤</el-button>
      <template #footer>
        <el-button @click="showSteps=false">取消</el-button>
        <el-button type="primary" @click="saveSteps" :loading="savingSteps">保存步骤</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'

const templates = ref([]); const loading = ref(false)
const showDialog = ref(false); const editingId = ref(null); const saving = ref(false)
const form = reactive({ name: '', maintenance_level: '日常', device_models: [] })
const deviceOptions = ref([])
const showSteps = ref(false); const savingSteps = ref(false)
const stepsForm = reactive({ id: null, steps: [] })

onMounted(() => {
  loadTemplates()
  loadDeviceOptions()
})

async function loadTemplates() {
  loading.value = true
  try {
    const { data } = await api.get('/api/v1/tasks/templates')
    templates.value = data.items || []
  } catch {}
  loading.value = false
}

async function loadDeviceOptions() {
  try {
    const { data } = await api.get('/api/v1/knowledge/tags')
    deviceOptions.value = data.device_models || []
  } catch {}
}

function addTemplate() {
  editingId.value = null
  form.name = ''; form.maintenance_level = '日常'; form.device_models = []
  showDialog.value = true
}

function editTemplate(row) {
  editingId.value = row.id
  form.name = row.name; form.maintenance_level = row.maintenance_level; form.device_models = row.device_models || []
  showDialog.value = true
}

async function saveTemplate() {
  if (!form.name.trim()) { ElMessage.warning('请输入模板名称'); return }
  saving.value = true
  try {
    if (editingId.value) {
      await api.put(`/api/v1/tasks/templates/${editingId.value}`, { ...form })
      ElMessage.success('已更新')
    } else {
      await api.post('/api/v1/tasks/templates', { ...form })
      ElMessage.success('已创建')
    }
    showDialog.value = false
    loadTemplates()
  } catch {}
  saving.value = false
}

async function delTemplate(row) {
  try {
    await ElMessageBox.confirm(`确定删除模板"${row.name}"吗？`, '确认删除', { type: 'warning' })
    await api.delete(`/api/v1/tasks/templates/${row.id}`).catch(() =>
      api.post(`/api/v1/tasks/templates/${row.id}/delete`)
    )
    ElMessage.success('已删除')
    loadTemplates()
  } catch {}
}

async function editSteps(row) {
  stepsForm.id = row.id
  // 优先使用列表中的 steps（后端已返回），若为空则从详情接口拉取
  const steps = row.steps
  if (steps && steps.length) {
    stepsForm.steps = JSON.parse(JSON.stringify(steps))
  } else {
    // 列表 steps 为空时，尝试通过详情接口获取（防止数据不一致）
    try {
      const { data } = await api.get(`/api/v1/tasks/templates/${row.id}`)
      stepsForm.steps = JSON.parse(JSON.stringify(data.steps || []))
    } catch {
      stepsForm.steps = []
    }
  }
  showSteps.value = true
}

function addStep() {
  stepsForm.steps.push({ phase: '', title: '', content: '', compliance_items: [], step_num: stepsForm.steps.length + 1 })
}

function removeStep(i) {
  stepsForm.steps.splice(i, 1)
  // 重新编号
  stepsForm.steps.forEach((s, idx) => s.step_num = idx + 1)
}

function addComplianceItem(step) {
  ElMessageBox.prompt('请输入合规校验项', '添加').then(({ value }) => {
    if (value && value.trim()) {
      if (!step.compliance_items) step.compliance_items = []
      step.compliance_items.push(value.trim())
    }
  }).catch(() => {})
}

async function saveSteps() {
  savingSteps.value = true
  try {
    await api.put(`/api/v1/tasks/templates/${stepsForm.id}`, { steps: stepsForm.steps })
    ElMessage.success('步骤已保存')
    showSteps.value = false
    loadTemplates()
  } catch {}
  savingSteps.value = false
}
</script>

<style scoped>
.step-editor-item { padding: 12px; margin-bottom: 12px; background: #f9fafb; border-radius: 6px; border: 1px solid #e5e7eb; }
.step-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
</style>
