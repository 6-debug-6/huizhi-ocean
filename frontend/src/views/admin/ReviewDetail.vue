<template>
  <div class="review-detail">
    <el-button @click="$router.back()" style="margin-bottom:16px">← 返回</el-button>
    <div v-loading="loading">
      <h2>{{ detail.title }}</h2>
      <p class="meta">提交人：{{ detail.uploader_name }} | 类型：{{ detail.is_experience_based ? '经验型（需复审）' : '事实型' }} | 状态：{{ statusLabel(detail.review_status) }}</p>

      <!-- 案例内容 -->
      <el-card header="案例内容" style="margin:16px 0">
        <div v-html="detail.content" class="content"></div>
      </el-card>

      <!-- 驳回原因（驳回时展示） -->
      <el-alert v-if="detail.reject_reason" :title="'驳回原因：' + detail.reject_reason" type="error" style="margin:16px 0" />

      <!-- 审核操作区 -->
      <el-card header="审核操作" style="margin:16px 0" v-if="canReview">
        <el-input v-model="comment" type="textarea" :rows="3" placeholder="审核意见（可选）" style="margin-bottom:12px" />

        <!-- 通过含修改：显示内容编辑器 -->
        <div v-if="showEdit" style="margin-bottom:12px">
          <div style="font-size:13px;color:#666;margin-bottom:6px">请修改案例内容（修改后将以此内容入库）：</div>
          <el-input v-model="editContent" type="textarea" :rows="10" placeholder="修改后的完整内容" />
          <div style="margin-top:8px;display:flex;gap:8px">
            <el-button type="warning" @click="doAction('approve_edited')" :loading="acting">确认发布修改后的内容</el-button>
            <el-button @click="showEdit=false">取消</el-button>
          </div>
        </div>

        <!-- 驳回原因输入 -->
        <div v-else-if="showReject" style="margin-bottom:12px">
          <el-input v-model="rejectReason" type="textarea" :rows="2" placeholder="请填写驳回原因" />
          <div style="margin-top:8px;display:flex;gap:8px">
            <el-button type="danger" @click="doReject" :loading="acting">确认驳回</el-button>
            <el-button @click="showReject=false">取消</el-button>
          </div>
        </div>

        <div v-else class="actions">
          <el-button type="success" @click="doAction('approve')" :loading="acting">通过</el-button>
          <el-button type="warning" @click="showEdit = true">通过（含修改）</el-button>
          <el-button type="danger" @click="showReject=true">驳回</el-button>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getReviewDetail, reviewAction } from '@/api/review'

const route = useRoute(); const router = useRouter()
const detail = ref({}); const loading = ref(false); const acting = ref(false)
const comment = ref(''); const rejectReason = ref(''); const showReject = ref(false)
const showEdit = ref(false); const editContent = ref('')

const canReview = computed(() => ['pending_initial', 'pending_expert'].includes(detail.value.review_status))

onMounted(() => fetchDetail())

async function fetchDetail() {
  loading.value = true
  try {
    const { data } = await getReviewDetail(route.params.id)
    detail.value = data
    editContent.value = data.content || '' // 初始化编辑内容
  } finally { loading.value = false }
}

async function doReject() {
  if (!rejectReason.value.trim()) { ElMessage.warning('请填写驳回原因'); return }
  acting.value = true
  try {
    await reviewAction(detail.value.id, { action: 'reject', review_comment: comment.value, reject_reason: rejectReason.value })
    ElMessage.success('案例已驳回')
    router.push('/admin/review')
  } catch {}
  finally { acting.value = false }
}

async function doAction(action) {
  acting.value = true
  try {
    const payload = { action, review_comment: comment.value, reject_reason: rejectReason.value }
    // 通过含修改时传递修改后的内容
    if (action === 'approve_edited') {
      payload.content = editContent.value
    }
    await reviewAction(detail.value.id, payload)
    ElMessage.success({ approve: '案例已通过，已纳入知识库', approve_edited: '已修改后通过' }[action])
    router.push('/admin/review')
  } finally { acting.value = false }
}

function statusLabel(s) { return { pending_initial: '待初审', pending_expert: '待复审', approved: '已通过', rejected: '已驳回' }[s] || s }
</script>

<style scoped>
.meta { color: #999; font-size: 14px; }
.content { font-size: 14px; line-height: 1.8; }
.actions { display: flex; gap: 12px; }
</style>
