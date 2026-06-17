<template>
  <div class="review-detail">
    <el-button @click="$router.back()" style="margin-bottom:16px">← 返回</el-button>
    <div v-loading="loading">
      <h2>{{ detail.title }}</h2>
      <p class="meta">提交人：{{ detail.uploader_name }} | 类型：{{ detail.is_experience_based ? '经验型（需复审）' : '事实型' }} | 状态：{{ statusLabel(detail.review_status) }}</p>

      <!-- 案例正文 -->
      <el-card header="案例内容" style="margin:16px 0">
        <div v-html="detail.content" class="content"></div>
      </el-card>

      <!-- 上传的图片 -->
      <el-card v-if="detail.images && detail.images.length" header="上传图片" style="margin:16px 0">
        <div class="image-list">
          <el-image
            v-for="(img, i) in detail.images"
            :key="i"
            :src="img"
            :preview-src-list="detail.images"
            :initial-index="i"
            fit="contain"
            style="max-width:300px;max-height:300px;margin:8px;border-radius:6px;cursor:pointer"
          />
        </div>
      </el-card>

      <!-- 驳回原因 -->
      <el-alert v-if="detail.reject_reason" :title="'驳回原因：' + detail.reject_reason" type="error" style="margin:16px 0" />

      <!-- 审核操作区 -->
      <el-card header="审核操作" style="margin:16px 0" v-if="canReview">
        <!-- 可编辑的内容区（始终可见） -->
        <div style="margin-bottom:12px">
          <div style="font-size:13px;color:#666;margin-bottom:4px">审核时可修改内容（点击下方"修改内容"展开）：</div>
          <el-button size="small" @click="showEditor = !showEditor" style="margin-bottom:8px">
            {{ showEditor ? '收起编辑器' : '修改内容' }}
          </el-button>
          <el-input
            v-if="showEditor"
            v-model="editContent"
            type="textarea"
            :rows="10"
            placeholder="修改案例内容后，可通过「通过（含修改）」或「通过」提交"
          />
        </div>

        <el-input v-model="comment" type="textarea" :rows="3" placeholder="审核意见（可选）" style="margin-bottom:12px" />

        <!-- 驳回原因 -->
        <div v-if="showReject" style="margin-bottom:12px">
          <el-input v-model="rejectReason" type="textarea" :rows="2" placeholder="请填写驳回原因" />
          <div style="margin-top:8px;display:flex;gap:8px">
            <el-button type="danger" @click="doReject" :loading="acting">确认驳回</el-button>
            <el-button @click="showReject=false">取消</el-button>
          </div>
        </div>

        <div v-else class="actions">
          <el-button type="success" @click="doApprove(false)" :loading="acting">通过</el-button>
          <el-button type="warning" @click="doApprove(true)" :loading="acting">通过（含修改）</el-button>
          <el-button type="danger" @click="showReject=true">驳回</el-button>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getReviewDetail, reviewAction } from '@/api/review'

const route = useRoute(); const router = useRouter()
const detail = ref({}); const loading = ref(false); const acting = ref(false)
const comment = ref(''); const rejectReason = ref('')
const showReject = ref(false); const showEditor = ref(false); const editContent = ref('')

const canReview = computed(() => ['pending_initial', 'pending_expert'].includes(detail.value.review_status))

onMounted(() => fetchDetail())

async function fetchDetail() {
  loading.value = true
  try {
    const { data } = await getReviewDetail(route.params.id)
    detail.value = data
    editContent.value = data.content || ''
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

/** 通过/通过含修改 */
async function doApprove(withEdits) {
  acting.value = true
  try {
    const payload = {
      action: withEdits ? 'approve_edited' : 'approve',
      review_comment: comment.value,
      reject_reason: '',
    }
    // 如果用户修改了内容（通过编辑器），始终传递最新内容
    if (editContent.value !== detail.value.content) {
      payload.content = editContent.value
    }
    if (withEdits) {
      // 含修改必然传递编辑后的内容
      payload.content = editContent.value
    }
    await reviewAction(detail.value.id, payload)
    ElMessage.success(withEdits ? '已修改后通过，纳入知识库' : '已通过，纳入知识库')
    router.push('/admin/review')
  } finally { acting.value = false }
}

function statusLabel(s) { return { pending_initial: '待初审', pending_expert: '待复审', approved: '已通过', rejected: '已驳回' }[s] || s }
</script>

<style scoped>
.meta { color: #999; font-size: 14px; }
.content { font-size: 14px; line-height: 1.8; }
.content :deep(img) { max-width: 100%; border-radius: 6px; margin: 8px 0; }
.actions { display: flex; gap: 12px; }
.image-list { display: flex; flex-wrap: wrap; }
</style>
