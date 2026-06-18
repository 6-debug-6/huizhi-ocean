<template>
  <div class="feedback-manage">
    <h2>AI 反馈管理</h2>
    <p style="color:#666;font-size:13px;margin-bottom:16px">查看所有用户对 AI 回复的有用/无用标注，发现知识库盲区和模型回答质量问题。</p>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-radio-group v-model="filterType" @change="loadData">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="useless">无用</el-radio-button>
        <el-radio-button value="partial">部分有用</el-radio-button>
        <el-radio-button value="useful">有用</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 反馈列表 -->
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column label="用户" width="100">
        <template #default="{ row }">{{ row.user_name || '未知' }}</template>
      </el-table-column>
      <el-table-column label="用户提问" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">{{ row.question }}</template>
      </el-table-column>
      <el-table-column label="AI 回复" min-width="180">
        <template #default="{ row }">
          <span class="text-preview">{{ (row.ai_reply || '').slice(0, 60) }}{{ (row.ai_reply || '').length > 60 ? '...' : '' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="反馈" width="100">
        <template #default="{ row }">
          <el-tag :type="tagType(row.feedback)" size="small">
            {{ { useful: '有用', partial: '部分有用', useless: '无用' }[row.feedback] || row.feedback }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="修正建议" min-width="120" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.comment" style="color:#e6a23c">{{ row.comment }}</span>
          <span v-else style="color:#ccc">—</span>
        </template>
      </el-table-column>
      <el-table-column label="时间" width="160">
        <template #default="{ row }">{{ row.created_at?.slice(0, 16) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="showDetail(row)">查看详情</el-button>
          <el-button size="small" type="danger" @click="delFeedback(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div style="margin-top:16px;text-align:right">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadData"
      />
    </div>

    <!-- ==================== 详情对话框 ==================== -->
    <el-dialog v-model="showDialog" title="反馈详情" width="700px" destroy-on-close>
      <div v-if="detail" class="detail-body">
        <div class="detail-section">
          <div class="detail-label">用户</div>
          <div class="detail-value">{{ detail.user_name || '未知' }}（ID: {{ detail.user_id }}）</div>
        </div>
        <div class="detail-section">
          <div class="detail-label">反馈类型</div>
          <div class="detail-value">
            <el-tag :type="tagType(detail.feedback)" size="small">
              {{ { useful: '有用', partial: '部分有用', useless: '无用' }[detail.feedback] || detail.feedback }}
            </el-tag>
          </div>
        </div>
        <div class="detail-section">
          <div class="detail-label">用户提问</div>
          <div class="detail-value detail-content">{{ detail.question }}</div>
        </div>
        <div class="detail-section">
          <div class="detail-label">AI 回复</div>
          <div class="detail-value detail-content">{{ detail.ai_reply }}</div>
        </div>
        <div class="detail-section">
          <div class="detail-label">修正建议</div>
          <div class="detail-value detail-content">{{ detail.comment || '（无）' }}</div>
        </div>
        <div class="detail-section">
          <div class="detail-label">时间</div>
          <div class="detail-value">{{ detail.created_at?.slice(0, 16) }}</div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showDialog = false">关闭</el-button>
        <el-button type="primary" @click="convertToKnowledge" :loading="converting">转化为知识条目</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import api from '@/api'

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const filterType = ref('')
const router = useRouter()

// 详情弹窗
const showDialog = ref(false)
const detail = ref(null)
const converting = ref(false)

onMounted(() => loadData())

async function loadData() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filterType.value) params.feedback_type = filterType.value
    const { data } = await api.get('/api/v1/admin/feedback', { params })
    items.value = data.items || []
    total.value = data.total || 0
  } catch {}
  loading.value = false
}

function tagType(fb) {
  return fb === 'useful' ? 'success' : fb === 'partial' ? 'warning' : 'danger'
}

function showDetail(row) {
  // 先获取完整的 AI 回复（列表只返回截断内容），通过消息 ID 请求完整数据
  detail.value = { ...row }
  showDialog.value = true
}

async function delFeedback(row) {
  try {
    await ElMessageBox.confirm('确定删除此反馈记录吗？（消息本身保留，仅清除反馈标记）', '确认删除', { type: 'warning' })
    await api.post(`/api/v1/admin/feedback/${row.message_id}/delete`)
    ElMessage.success('已删除')
    loadData()
  } catch {}
}

async function convertToKnowledge() {
  if (!detail.value) return
  try {
    await ElMessageBox.confirm(
      '将把此 AI 反馈（含用户提问、AI 回复、修正建议）转化为知识条目草稿，确认继续？',
      '确认转化'
    )
    converting.value = true
    const { data } = await api.post(`/api/v1/admin/feedback/${detail.value.message_id}/to-knowledge`)
    ElMessage.success(data.message || '已转化为知识条目草稿')
    showDialog.value = false
    router.push(`/admin/knowledge/${data.id}/edit`)
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') {
      // ElMessageBox.confirm reject on cancel, don't show error
    }
  }
  converting.value = false
}
</script>

<style scoped>
.filter-bar { margin-bottom: 16px; }
.text-preview { color: #555; font-size: 13px; }

.detail-body { max-height: 55vh; overflow-y: auto; }
.detail-section { margin-bottom: 16px; }
.detail-label { font-size: 12px; color: #999; margin-bottom: 4px; }
.detail-value { font-size: 14px; color: #333; }
.detail-content {
  padding: 12px;
  background: #f9fafb;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 250px;
  overflow-y: auto;
}
</style>
