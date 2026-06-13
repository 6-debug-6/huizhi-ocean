<template>
  <div class="task-list-page">
    <div class="header"><h2>我的任务</h2><el-button type="primary" @click="showCreate=true">新建任务</el-button></div>

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
    <el-dialog v-model="showCreate" title="新建作业任务" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="任务名称" required><el-input v-model="form.title" placeholder="如：XX发动机日常检修" /></el-form-item>
        <el-form-item label="设备型号" required><el-input v-model="form.device_model" placeholder="如：XX型柴油发动机" /></el-form-item>
        <el-form-item label="选择模板">
          <el-select v-model="form.template_id" placeholder="选择检修流程模板" clearable style="width:100%" @change="loadTemplate">
            <el-option v-for="t in templates" :key="t.id" :label="`${t.name} (${t.step_count}步骤)`" :value="t.id" />
          </el-select>
        </el-form-item>
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
const tasks = ref([]); const templates = ref([]); const showCreate = ref(false); const creating = ref(false)
const stepInput = ref('')
const form = ref({ title: '', device_model: '', template_id: null })

onMounted(async () => {
  try { const { data } = await api.get('/api/v1/tasks/'); tasks.value = data.items } catch {}
  try { const { data } = await api.get('/api/v1/tasks/templates'); templates.value = data.items } catch {}
})

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
    await api.delete(`/api/v1/tasks/${t.id}`)
    ElMessage.success('任务已删除')
    tasks.value = tasks.value.filter(x => x.id !== t.id)
  } catch { /* canceled */ }
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
