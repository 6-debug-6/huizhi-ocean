<template>
  <div class="device-manage">
    <h2>设备型号与故障标签管理</h2>
    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <!-- 设备型号 -->
      <el-tab-pane label="设备型号" name="devices">
        <div style="margin-bottom:12px"><el-button type="primary" @click="addDevice">新增设备型号</el-button></div>
        <el-table :data="devices" v-loading="loadingDevices">
          <el-table-column prop="name" label="型号名称" />
          <el-table-column prop="production_line" label="产线" />
          <el-table-column prop="category" label="分类" />
          <el-table-column prop="status" label="状态" width="80">
            <template #default="{ row }"><el-tag :type="row.status==='active'?'success':'info'" size="small">{{ row.status==='active'?'启用':'已归档' }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-button size="small" @click="editDevice(row)">编辑</el-button>
              <el-button v-if="row.status==='active'" size="small" @click="archiveDevice(row)">归档</el-button>
              <el-button size="small" type="danger" @click="delDevice(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 故障标签（扁平表格） -->
      <el-tab-pane label="故障标签" name="faults">
        <div style="margin-bottom:12px"><el-button type="primary" @click="addFaultTag">新增标签</el-button></div>
        <el-table :data="faultTags" v-loading="loadingFaults">
          <el-table-column prop="name" label="标签名称" />
          <el-table-column label="使用次数" width="120">
            <template #default="{ row }">
              <el-tag size="small" :type="row.usage_count > 0 ? '' : 'info'">{{ row.usage_count || 0 }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160">
            <template #default="{ row }">
              <el-button size="small" @click="editFaultTag(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="delFaultTag(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 设备型号编辑对话框 -->
    <el-dialog v-model="showDeviceDialog" :title="editingDeviceId ? '编辑设备型号' : '新增设备型号'" width="440px">
      <el-form :model="deviceForm" label-width="80px">
        <el-form-item label="型号名称" required><el-input v-model="deviceForm.name" /></el-form-item>
        <el-form-item label="产线"><el-input v-model="deviceForm.production_line" /></el-form-item>
        <el-form-item label="分类"><el-input v-model="deviceForm.category" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDeviceDialog=false">取消</el-button>
        <el-button type="primary" @click="saveDevice" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <!-- 故障标签编辑对话框 -->
    <el-dialog v-model="showFaultDialog" :title="editingFaultId ? '编辑标签' : '新增标签'" width="400px">
      <el-form :model="faultForm" label-width="80px">
        <el-form-item label="标签名称" required><el-input v-model="faultForm.name" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showFaultDialog=false">取消</el-button>
        <el-button type="primary" @click="saveFaultTag" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'

const activeTab = ref('devices')
const devices = ref([]); const loadingDevices = ref(false)
const faultTags = ref([]); const loadingFaults = ref(false)
const saving = ref(false)

// ========== 设备型号 ==========
const showDeviceDialog = ref(false); const editingDeviceId = ref(null)
const deviceForm = reactive({ name: '', production_line: '', category: '' })

onMounted(() => loadDevices())

function addDevice() {
  editingDeviceId.value = null
  showDeviceDialog.value = true
  // 使用 Object.assign 而非赋值，保持 reactive 响应性
  Object.assign(deviceForm, { name: '', production_line: '', category: '' })
}

async function loadDevices() {
  loadingDevices.value = true
  try {
    const { data } = await api.get('/api/v1/config/device-models', { params: { status_filter: 'all' } })
    devices.value = Array.isArray(data) ? data : []
  } catch {}
  loadingDevices.value = false
}

function editDevice(row) {
  editingDeviceId.value = row.id
  deviceForm.name = row.name
  deviceForm.production_line = row.production_line || ''
  deviceForm.category = row.category || ''
  showDeviceDialog.value = true
}

async function saveDevice() {
  if (!deviceForm.name.trim()) { ElMessage.warning('请输入型号名称'); return }
  saving.value = true
  try {
    if (editingDeviceId.value) {
      await api.put(`/api/v1/config/device-models/${editingDeviceId.value}`, { ...deviceForm })
      ElMessage.success('已更新')
    } else {
      await api.post('/api/v1/config/device-models', { ...deviceForm })
      ElMessage.success('已创建')
    }
    showDeviceDialog.value = false
    loadDevices()
  } catch {}
  saving.value = false
}

async function archiveDevice(row) {
  try {
    await api.put(`/api/v1/config/device-models/${row.id}`, { status: 'archived' })
    ElMessage.success('已归档')
    loadDevices()
  } catch {}
}

async function delDevice(row) {
  try {
    await ElMessageBox.confirm(`确定删除"${row.name}"吗？`, '确认删除', { type: 'warning' })
    await api.post(`/api/v1/config/device-models/${row.id}/delete`)
    ElMessage.success('已删除')
    loadDevices()
  } catch {}
}

// ========== 故障标签 ==========
const showFaultDialog = ref(false); const editingFaultId = ref(null)
const faultForm = reactive({ name: '' })

async function loadFaultTags() {
  loadingFaults.value = true
  try {
    const { data } = await api.get('/api/v1/config/fault-tags')
    faultTags.value = Array.isArray(data) ? data : []
  } catch {}
  loadingFaults.value = false
}

function addFaultTag() {
  editingFaultId.value = null
  faultForm.name = ''
  showFaultDialog.value = true
}

function editFaultTag(row) {
  editingFaultId.value = row.id
  faultForm.name = row.name
  showFaultDialog.value = true
}

async function saveFaultTag() {
  if (!faultForm.name.trim()) { ElMessage.warning('请输入标签名称'); return }
  saving.value = true
  try {
    if (editingFaultId.value) {
      await api.put(`/api/v1/config/fault-tags/${editingFaultId.value}`, { name: faultForm.name })
      ElMessage.success('已更新')
    } else {
      await api.post('/api/v1/config/fault-tags', { name: faultForm.name })
      ElMessage.success('已创建')
    }
    showFaultDialog.value = false
    loadFaultTags()
  } catch {}
  saving.value = false
}

async function delFaultTag(row) {
  try {
    await ElMessageBox.confirm(`确定删除标签"${row.name}"吗？`, '确认删除', { type: 'warning' })
    await api.post(`/api/v1/config/fault-tags/${row.id}/delete`)
    ElMessage.success('已删除')
    loadFaultTags()
  } catch {}
}

function onTabChange(name) {
  if (name === 'faults') loadFaultTags()
  else if (name === 'devices') loadDevices()
}
</script>

<style scoped>
</style>
