<template>
  <div class="workspace">
    <div class="ws-header">
      <h2>个人工作台</h2>
      <el-input v-model="searchText" placeholder="搜索..." clearable style="width:240px" />
    </div>
    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <!-- ========== Tab 1: 我的任务 ========== -->
      <el-tab-pane label="我的任务" name="tasks">
        <div v-loading="loading.tasks">
          <div v-if="filteredTasks.length" class="card-grid">
            <el-card v-for="t in filteredTasks" :key="t.id" class="ws-card" :class="t.status" @click="$router.push(`/task/${t.id}`)">
              <div class="card-title">{{ t.title }}</div>
              <div class="card-meta">{{ t.device_model }} · {{ t.maintenance_level }}</div>
              <el-progress :percentage="t.progress" :status="statusClass(t.status)" style="margin:8px 0" />
              <div class="card-bottom">
                <el-tag :type="tagType(t.status)" size="small">{{ statusLabel(t.status) }}</el-tag>
                <span class="card-time">{{ t.started_at?.slice(0, 10) }}</span>
              </div>
            </el-card>
          </div>
          <el-empty v-else description="暂无任务" />
        </div>
      </el-tab-pane>

      <!-- ========== Tab 2: 我的上传记录 ========== -->
      <el-tab-pane label="我的上传" name="uploads">
        <div v-loading="loading.uploads">
          <div v-if="filteredCases.length" class="card-grid">
            <el-card v-for="c in filteredCases" :key="c.id" class="ws-card">
              <div class="card-title">{{ c.title }}</div>
              <div class="card-meta">
                <span v-for="t in c.fault_tags" :key="t" class="tag">{{ t }}</span>
              </div>
              <div class="card-bottom">
                <el-tag :type="reviewTag(c.review_status)" size="small">{{ reviewLabel(c.review_status) }}</el-tag>
                <div>
                  <el-button size="small" type="danger" plain @click.stop="delCase(c)">删除</el-button>
                  <span class="card-time">{{ c.created_at?.slice(0, 10) }}</span>
                </div>
              </div>
              <div v-if="c.review_comment" class="review-comment">审核意见：{{ c.review_comment }}</div>
              <div v-if="c.reject_reason" class="reject-reason">驳回原因：{{ c.reject_reason }}</div>
            </el-card>
          </div>
          <el-empty v-else description="暂无上传记录" />
        </div>
      </el-tab-pane>

      <!-- ========== Tab 3: 我的客服工单 ========== -->
      <el-tab-pane label="客服工单" name="tickets">
        <div v-loading="loading.tickets">
          <div v-if="filteredTickets.length" class="card-grid">
            <el-card v-for="t in filteredTickets" :key="t.id" class="ws-card" @click="$router.push(`/tickets/${t.id}`)">
              <div class="card-title">{{ t.ticket_no }}</div>
              <div class="card-meta">{{ t.title }}</div>
              <div class="card-bottom">
                <el-tag :type="ticketTag(t.status)" size="small">{{ ticketLabel(t.status) }}</el-tag>
                <span class="card-time">{{ t.created_at?.slice(0, 10) }}</span>
              </div>
            </el-card>
          </div>
          <el-empty v-else description="暂无工单"><el-button @click="$router.push('/tickets')">提交工单</el-button></el-empty>
        </div>
      </el-tab-pane>

      <!-- ========== Tab 4: 我的修正记录 ========== -->
      <el-tab-pane label="修正记录" name="feedback">
        <div v-loading="loading.feedback">
          <div v-if="filteredFeedback.length">
            <div v-for="f in filteredFeedback" :key="f.id" class="feedback-item">
              <div class="fb-question"><b>Q:</b> {{ f.question?.slice(0, 150) }}</div>
              <div class="fb-reply"><b>A:</b> {{ f.ai_reply?.slice(0, 200) }}</div>
              <div class="fb-meta">
                <el-tag :type="f.feedback==='useful'?'success':f.feedback==='partial'?'warning':'danger'" size="small">
                  {{ { useful:'有用', partial:'部分有用', useless:'无用' }[f.feedback] }}
                </el-tag>
                <span v-if="f.comment" class="fb-comment">{{ f.comment }}</span>
                <span class="card-time">{{ f.created_at?.slice(0, 16) }}</span>
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无修正记录" />
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'
import { TICKET_STATUS, TASK_STATUS, REVIEW_STATUS } from '@/utils/constants'
import { formatDate } from '@/utils/helpers'

const activeTab = ref('tasks')
const searchText = ref('')
const loading = reactive({ tasks: false, uploads: false, tickets: false, feedback: false })
const tasks = ref([]); const cases = ref([]); const tickets = ref([])
const feedbackList = ref([])

const filteredTasks = computed(() => tasks.value.filter(t => !searchText.value || t.title?.includes(searchText.value)))
const filteredCases = computed(() => cases.value.filter(c => !searchText.value || c.title?.includes(searchText.value)))
const filteredTickets = computed(() => tickets.value.filter(t => !searchText.value || t.title?.includes(searchText.value)))
const filteredFeedback = computed(() => feedbackList.value.filter(f => !searchText.value || f.question?.includes(searchText.value)))

async function loadTasks() {
  loading.tasks = true
  try { const { data } = await api.get('/api/v1/tasks/'); tasks.value = data.items || [] } catch {}
  loading.tasks = false
}

async function loadUploads() {
  loading.uploads = true
  try { const { data } = await api.get('/api/v1/cases/'); cases.value = data.items || [] } catch {}
  loading.uploads = false
}

async function loadTickets() {
  loading.tickets = true
  try { const { data } = await api.get('/api/v1/tickets/'); tickets.value = data.items || [] } catch {}
  loading.tickets = false
}

async function loadFeedback() {
  loading.feedback = true
  try { const { data } = await api.get('/api/v1/conversations/my-feedback'); feedbackList.value = data.items || [] } catch {}
  loading.feedback = false
}

async function delCase(c) {
  try {
    await ElMessageBox.confirm('确定删除此上传记录吗？', '确认')
    await api.post(`/api/v1/cases/${c.id}/delete`)
    ElMessage.success('已删除')
    loadUploads()
  } catch {}
}

async function delTask(t) {
  try {
    await ElMessageBox.confirm('确定删除此任务吗？', '确认')
    await api.post(`/api/v1/tasks/${t.id}/delete`)
    ElMessage.success('已删除')
    loadTasks()
  } catch {}
}

function onTabChange(name) {
  if (name === 'tasks') loadTasks()
  else if (name === 'uploads') loadUploads()
  else if (name === 'tickets') loadTickets()
  else if (name === 'feedback') loadFeedback()
}

// 初始加载第一个 tab
loadTasks()

function statusClass(s) { return TASK_STATUS[s]?.progressStatus || '' }
function tagType(s) { return TASK_STATUS[s]?.tag || '' }
function statusLabel(s) { return TASK_STATUS[s]?.label || s }
function reviewTag(s) { return REVIEW_STATUS[s]?.tag || 'info' }
function reviewLabel(s) { return REVIEW_STATUS[s]?.label || s }
function ticketTag(s) { return TICKET_STATUS[s]?.tag || 'info' }
function ticketLabel(s) { return TICKET_STATUS[s]?.label || s }
</script>

<style scoped>
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
.ws-card { cursor: pointer; }
.ws-card.paused { opacity: 0.6; }
.card-title { font-size: 15px; font-weight: 600; margin-bottom: 4px; }
.card-meta { font-size: 12px; color: #999; margin-bottom: 8px; }
.tag { display: inline-block; background: #e8f0fe; color: #1d4ed8; padding: 1px 6px; border-radius: 3px; font-size: 11px; margin-right: 4px; }
.card-bottom { display: flex; justify-content: space-between; align-items: center; }
.card-time { font-size: 12px; color: #bbb; }
.review-comment { margin-top: 8px; padding: 6px 10px; background: #f0fdf4; color: #16a34a; font-size: 12px; border-radius: 4px; }
.reject-reason { margin-top: 8px; padding: 6px 10px; background: #fef2f2; color: #dc2626; font-size: 12px; border-radius: 4px; }
.feedback-item { padding: 16px; margin-bottom: 12px; background: #fff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
.fb-question { font-size: 14px; margin-bottom: 8px; color: #333; }
.fb-reply { font-size: 13px; color: #666; margin-bottom: 8px; padding-left: 12px; border-left: 2px solid #e5e7eb; }
.fb-meta { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.fb-comment { color: #999; flex: 1; }
</style>
