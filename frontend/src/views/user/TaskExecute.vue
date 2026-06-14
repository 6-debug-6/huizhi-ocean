<template>
  <div class="task-execute" v-loading="loading">
    <!-- 顶部信息栏 -->
    <div class="te-header">
      <el-button @click="$router.push('/task')">← 返回</el-button>
      <div class="te-info">
        <h2>{{ task.title }}</h2>
        <span class="te-meta">{{ task.device_model }} · {{ task.maintenance_level }} · 进度 {{ task.current_step }}/{{ task.total_steps }}</span>
      </div>
      <div class="te-actions">
        <el-button v-if="task.status==='in_progress'" type="warning" @click="doPause">暂停</el-button>
        <el-button v-if="task.status==='paused'" type="success" @click="doResume">恢复</el-button>
        <el-button @click="showHandover=true">交接</el-button>
        <el-button v-if="task.status!=='completed'" type="success" @click="doComplete">✓ 提前完成</el-button>
        <el-button type="primary" plain @click="openAIChat">🤖 智能问答</el-button>
      </div>
    </div>

    <!-- 进度条 -->
    <el-progress :percentage="progress" :status="task.status==='completed'?'success':''" style="margin-bottom:20px" />

    <!-- 暂停原因 -->
    <el-alert v-if="task.status==='paused'" :title="'已暂停：' + (task.pause_reason || '手动暂停')" type="warning" show-icon style="margin-bottom:16px" />

    <!-- 交接说明 -->
    <el-alert v-if="task.handover_note" :title="'交接说明：' + task.handover_note" type="info" show-icon style="margin-bottom:16px" closable />

    <div class="te-body">
      <!-- 左侧步骤导航 -->
      <div class="te-sidebar">
        <div v-for="(step, i) in task.steps" :key="i" class="step-nav-item"
          :class="{ active: i === task.current_step && task.status !== 'completed', done: task.confirmed_step_nums?.includes(i+1), locked: i > task.current_step && task.status !== 'completed' }"
          @click="i <= task.current_step && (currentDetail = i)">
          <div class="sn-badge">{{ task.confirmed_step_nums?.includes(i+1) ? '✓' : i+1 }}</div>
          <div class="sn-info">
            <div class="sn-phase">{{ step.phase || '步骤' }}</div>
            <div class="sn-title">{{ step.title }}</div>
          </div>
        </div>
      </div>

      <!-- 右侧步骤详情 -->
      <div class="te-detail">
        <template v-if="task.status === 'completed'">
          <el-result icon="success" title="全部步骤已完成" sub-title="作业记录已存档，可在审计日志中查看详情" />
        </template>
        <template v-else-if="task.steps[currentDetail] !== undefined">
          <el-card>
            <template #header>
              <span>步骤 {{ currentDetail + 1 }}：{{ task.steps[currentDetail]?.title }}</span>
              <el-tag v-if="task.confirmed_step_nums?.includes(currentDetail+1)" type="success" size="small" style="margin-left:8px">已确认</el-tag>
            </template>

            <!-- 步骤说明 -->
            <div class="step-content" v-if="task.steps[currentDetail]?.content">
              {{ task.steps[currentDetail]?.content }}
            </div>

            <!-- 合规校验项 -->
            <div v-if="task.steps[currentDetail]?.compliance_items?.length" class="compliance-section">
              <div class="compliance-title">⚠ 合规校验（必须全部确认后方可继续）</div>
              <el-checkbox-group v-model="complianceChecked">
                <el-checkbox v-for="(item, ci) in task.steps[currentDetail]?.compliance_items" :key="ci" :label="ci" :disabled="isCurrentStepConfirmed">{{ item }}</el-checkbox>
              </el-checkbox-group>
            </div>

            <!-- 确认按钮 -->
            <div style="margin-top:20px;text-align:center">
              <el-button v-if="!isCurrentStepConfirmed" type="primary" size="large" @click="confirmStep" :loading="acting"
                :disabled="!canConfirmCurrentStep">
                确认并进入下一步
              </el-button>
              <span v-else class="confirmed-text">✓ 此步骤已确认</span>
            </div>
          </el-card>
        </template>
      </div>
    </div>

    <!-- 交接对话框 -->
    <el-dialog v-model="showHandover" title="交接任务" width="400px">
      <el-form label-width="70px">
        <el-form-item label="接收人">
          <el-select v-model="handoverTo" filterable placeholder="选择同班组人员" style="width:100%">
            <el-option v-for="u in userList" :key="u.id" :label="`${u.name} (${u.team})`" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明"><el-input v-model="handoverNote" type="textarea" :rows="2" placeholder="简述当前进展和注意事项" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showHandover=false">取消</el-button>
        <el-button type="primary" @click="doHandover" :loading="acting">确认交接</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'

const route = useRoute(); const router = useRouter()
const task = ref({ steps: [], confirmed_step_nums: [], status: '', pause_reason: '', handover_note: '' })
const loading = ref(false); const acting = ref(false)
const currentDetail = ref(0)
const complianceChecked = ref([])
const showHandover = ref(false); const handoverTo = ref(null); const handoverNote = ref('')
const userList = ref([])

const progress = computed(() => {
  if (!task.value.total_steps) return 0
  return Math.round((task.value.confirmed_step_nums?.length || 0) / task.value.total_steps * 100)
})

const isCurrentStepConfirmed = computed(() => {
  return task.value.confirmed_step_nums?.includes(currentDetail.value + 1)
})

const canConfirmCurrentStep = computed(() => {
  // 只有当前活跃步骤可以确认，且合规项全部勾选
  if (currentDetail.value !== task.value.current_step) return false
  const items = task.value.steps[currentDetail.value]?.compliance_items || []
  return complianceChecked.value.length >= items.length
})

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await api.get(`/api/v1/tasks/${route.params.id}`)
    task.value = data
    // 显示当前步骤（已完成则显示最后一步）
    currentDetail.value = data.status === 'completed' ? Math.max(0, data.total_steps - 1) : data.current_step
    // 加载合规勾选状态
    if (data.confirmed_step_nums?.includes(data.current_step + 1)) {
      const items = data.steps[data.current_step]?.compliance_items || []
      complianceChecked.value = items.map((_, i) => i)
    }
  } catch {}
  loading.value = false
  // 加载用户列表（用于交接）
  try { const { data } = await api.get('/api/v1/auth/users'); userList.value = Array.isArray(data) ? data.filter(u => u.id !== task.value.assignee_id) : [] } catch {}
})

async function confirmStep() {
  if (!canConfirmCurrentStep.value) return
  acting.value = true
  try {
    await api.post(`/api/v1/tasks/${task.value.id}/step`)
    ElMessage.success('步骤确认成功')
    // 刷新任务状态
    const { data } = await api.get(`/api/v1/tasks/${route.params.id}`)
    task.value = data
    // 完成后 current_step == total_steps，保持显示最后一步
    currentDetail.value = data.status === 'completed' ? data.total_steps - 1 : data.current_step
    complianceChecked.value = []
    if (data.status === 'completed') {
      ElMessage.success('全部步骤已完成！')
    }
  } catch {}
  finally { acting.value = false }
}

async function doPause() {
  const { value: reason } = await ElMessageBox.prompt('暂停原因（可选）', '暂停任务').catch(() => ({}))
  acting.value = true
  try {
    await api.post(`/api/v1/tasks/${task.value.id}/pause?reason=${encodeURIComponent(reason || '')}`)
    task.value.status = 'paused'
    task.value.pause_reason = reason || '手动暂停'
    ElMessage.success('任务已暂停')
  } catch {}
  finally { acting.value = false }
}

async function doResume() {
  acting.value = true
  try {
    await api.post(`/api/v1/tasks/${task.value.id}/resume`)
    task.value.status = 'in_progress'
    task.value.pause_reason = ''
    ElMessage.success('任务已恢复')
  } catch {}
  finally { acting.value = false }
}

async function doComplete() {
  await ElMessageBox.confirm('确定提前完成任务吗？剩余步骤将标记为跳过。', '确认')
  acting.value = true
  try {
    await api.post(`/api/v1/tasks/${task.value.id}/complete`)
    task.value.status = 'completed'
    task.value.current_step = task.value.total_steps
    currentDetail.value = Math.max(0, task.value.total_steps - 1)
    ElMessage.success('任务已完成')
  } catch {}
  finally { acting.value = false }
}

async function doHandover() {
  if (!handoverTo.value) { ElMessage.warning('请选择接收人'); return }
  acting.value = true
  try {
    await api.post(`/api/v1/tasks/${task.value.id}/handover`, { to_user_id: handoverTo.value, note: handoverNote.value })
    ElMessage.success('任务已交接')
    router.push('/task')
  } catch {}
  finally { acting.value = false }
}

function openAIChat() {
  router.push({ name: 'Chat', query: { task_id: task.value.id, device_model: task.value.device_model, task_step: task.value.steps[task.value.current_step]?.title || '' } })
}
</script>

<style scoped>
.te-header { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
.te-info { flex: 1; }
.te-info h2 { margin: 0; font-size: 18px; }
.te-meta { font-size: 13px; color: #999; }
.te-actions { display: flex; gap: 8px; }
.te-body { display: flex; gap: 16px; min-height: 500px; }
.te-sidebar { width: 260px; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.step-nav-item { display: flex; gap: 10px; padding: 14px 16px; cursor: pointer; border-bottom: 1px solid #f5f5f5; transition: background 0.2s; }
.step-nav-item:hover { background: #f0f7ff; }
.step-nav-item.active { background: #e8f0fe; border-left: 3px solid #1d4ed8; }
.step-nav-item.done { background: #f6fff6; }
.step-nav-item.locked { opacity: 0.5; cursor: not-allowed; }
.sn-badge { width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 600; flex-shrink: 0; }
.step-nav-item.active .sn-badge { background: #1d4ed8; color: #fff; }
.step-nav-item.done .sn-badge { background: #10b981; color: #fff; }
.step-nav-item:not(.active):not(.done) .sn-badge { background: #e5e7eb; color: #666; }
.sn-phase { font-size: 11px; color: #999; }
.sn-title { font-size: 14px; }
.te-detail { flex: 1; }
.step-content { font-size: 14px; line-height: 1.8; padding: 12px 0; color: #333; }
.compliance-section { margin-top: 16px; padding: 16px; background: #fef3c7; border-radius: 6px; }
.compliance-title { font-size: 14px; font-weight: 600; color: #d97706; margin-bottom: 12px; }
.confirmed-text { color: #10b981; font-weight: 600; }
</style>
