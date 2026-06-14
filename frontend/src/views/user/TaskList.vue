<template>
  <div class="task-list-page">
    <div class="header"><h2>我的任务</h2><el-button type="primary" @click="openCreate">新建任务</el-button></div>

    <!-- 任务列表 -->
    <div v-if="tasks.length" class="task-cards">
      <el-card v-for="t in tasks" :key="t.id" class="task-card" :class="t.status">
        <div class="tc-title">{{ t.title }}</div>
        <div class="tc-meta">{{ t.device_model }} · {{ t.maintenance_level }} · 开始: {{ t.started_at?.slice(0,10) }}</div>
        <div class="tc-progress">
          <el-progress :percentage="t.progress" :status="t.status==='completed'?'success':t.status==='paused'?'warning':''" />
        </div>
        <div class="tc-actions">
          <div>
            <el-tag v-if="t.is_handed_over" size="small" type="info">来自交接</el-tag>
            <el-tag :type="statusTag(t.status)" size="small" style="margin-left:4px">{{ { in_progress:'进行中', paused:'已暂停', completed:'已完成' }[t.status] }}</el-tag>
          </div>
          <div>
            <el-button v-if="t.status!=='completed'" size="small" type="primary" @click="goTask(t)">继续</el-button>
            <el-button v-else size="small" @click="goTask(t)">查看</el-button>
            <el-button size="small" type="danger" plain @click="delTask(t)">删除</el-button>
          </div>
        </div>
      </el-card>
    </div>
    <div v-else class="empty">暂无任务，点击"新建任务"开始</div>

    <!-- 新建任务对话框 -->
    <el-dialog v-model="showCreate" title="新建作业任务" width="540px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="任务名称" required><el-input v-model="form.title" placeholder="如：XX发动机日常检修" /></el-form-item>
        <el-form-item label="设备型号" required>
          <el-select v-model="form.device_model" filterable allow-create placeholder="选择或输入设备型号" style="width:100%" @change="autoMatch">
            <el-option v-for="dm in deviceOptions" :key="dm" :label="dm" :value="dm" />
          </el-select>
        </el-form-item>
        <el-form-item label="检修等级">
          <el-radio-group v-model="form.maintenance_level" @change="autoMatch">
            <el-radio label="日常">日常检修</el-radio>
            <el-radio label="定修">定修</el-radio>
            <el-radio label="大修">大修</el-radio>
          </el-radio-group>
        </el-form-item>

        <!-- 自动匹配的模板推荐 -->
        <el-form-item v-if="matchedTemplates.length" label="推荐模板">
          <el-radio-group v-model="form.template_id">
            <el-radio v-for="m in matchedTemplates" :key="m.template.id" :value="m.template.id" style="display:flex;margin-bottom:8px">
              <div style="font-size:13px">
                <strong>{{ m.template.name }}</strong>
                <el-tag size="small" :type="m.score >= 0.8 ? 'success' : 'warning'" style="margin-left:6px">{{ Math.round(m.score * 100) }}%</el-tag>
                <span style="color:#999;font-size:12px;margin-left:4px">{{ m.template.step_count }}步骤 · {{ m.template.version }}</span>
              </div>
            </el-radio>
            <!-- 不选模板 -->
            <el-radio :value="null" style="margin-top:4px">不使用模板（手动输入步骤）</el-radio>
          </el-radio-group>
        </el-form-item>

        <!-- 手动选择模板 -->
        <el-form-item v-if="!matchedTemplates.length" label="选择模板">
          <el-select v-model="form.template_id" placeholder="选择检修流程模板" clearable style="width:100%">
            <el-option v-for="t in templates" :key="t.id" :label="`${t.name} (${t.step_count}步骤)`" :value="t.id" />
          </el-select>
        </el-form-item>

        <!-- 手动输入步骤（未选模板时） -->
        <el-form-item v-if="!form.template_id" label="手动步骤">
          <el-input v-model="stepInput" placeholder="每行一个步骤，如：断电→挂牌→拆卸→检测→安装→试车" type="textarea" :rows="4" />
          <span style="font-size:12px;color:#999">每行一个步骤名称</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate=false">取消</el-button>
        <el-button type="primary" @click="doCreate" :loading="creating">创建任务</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'

const router = useRouter()
const tasks = ref([]); const templates = ref([])
const showCreate = ref(false); const creating = ref(false)
const matchedTemplates = ref([]); const deviceOptions = ref([])
const stepInput = ref('')
const form = ref({ title: '', device_model: '', maintenance_level: '日常', template_id: null })

onMounted(async () => {
  try { const { data } = await api.get('/api/v1/tasks/'); tasks.value = data.items || [] } catch {}
  try { const { data } = await api.get('/api/v1/tasks/templates'); templates.value = data.items || [] } catch {}
  // 加载设备型号选项（供select使用）
  try {
    const { data } = await api.get('/api/v1/knowledge/tags')
    deviceOptions.value = data.device_models || []
  } catch {}
})

function openCreate() {
  form.value = { title: '', device_model: '', maintenance_level: '日常', template_id: null }
  stepInput.value = ''
  matchedTemplates.value = []
  showCreate.value = true
}

/** 自动匹配模板 */
async function autoMatch() {
  if (!form.value.device_model) { matchedTemplates.value = []; return }
  try {
    const { data } = await api.post('/api/v1/tasks/templates/match', {
      device_model: form.value.device_model,
      maintenance_level: form.value.maintenance_level || '日常',
    })
    matchedTemplates.value = data.matches || []
    // 自动选中最高分的模板
    if (matchedTemplates.value.length && matchedTemplates.value[0].score >= 0.6) {
      form.value.template_id = matchedTemplates.value[0].template.id
    }
  } catch {}
}

async function doCreate() {
  if (!form.value.title || !form.value.device_model) { ElMessage.warning('请填写任务名称和设备型号'); return }
  creating.value = true
  try {
    const steps = stepInput.value.trim().split('\n').filter(Boolean).map((s, i) => ({
      phase: '步骤', step_num: i + 1, title: s.trim(), content: '', compliance_items: []
    }))
    const { data } = await api.post('/api/v1/tasks/', {
      title: form.value.title, device_model: form.value.device_model,
      template_id: form.value.template_id || null, steps: steps.length ? steps : null,
    })
    showCreate.value = false
    ElMessage.success('任务已创建')
    router.push(`/task/${data.id}`)
  } catch {}
  finally { creating.value = false }
}

function goTask(t) { router.push(`/task/${t.id}`) }
async function delTask(t) {
  try {
    await ElMessageBox.confirm('确定删除此任务吗？', '确认')
    await api.post(`/api/v1/tasks/${t.id}/delete`)
    ElMessage.success('任务已删除')
    tasks.value = tasks.value.filter(x => x.id !== t.id)
  } catch {}
}
function statusTag(s) { return { in_progress: '', paused: 'warning', completed: 'success' }[s] }
</script>

<style scoped>
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.task-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; }
.task-card { cursor: pointer; }
.task-card.paused { opacity: 0.7; }
.tc-title { font-size: 15px; font-weight: 600; margin-bottom: 4px; }
.tc-meta { font-size: 12px; color: #999; margin-bottom: 8px; }
.tc-progress { margin: 12px 0; }
.tc-actions { display: flex; justify-content: space-between; align-items: center; }
.empty { text-align: center; color: #999; padding: 60px; }
</style>
