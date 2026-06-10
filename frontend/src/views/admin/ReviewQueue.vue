<template>
  <div class="review-queue">
    <h2>审核队列</h2>
    <el-radio-group v-model="reviewStatus" @change="fetchList" style="margin-bottom:16px">
      <el-radio-button value="pending_initial">待初审</el-radio-button>
      <el-radio-button value="pending_expert">待复审</el-radio-button>
      <el-radio-button value="approved">已通过</el-radio-button>
      <el-radio-button value="rejected">已驳回</el-radio-button>
    </el-radio-group>

    <el-table :data="items" v-loading="loading" @row-click="goDetail" style="cursor:pointer">
      <el-table-column prop="title" label="案例标题" />
      <el-table-column prop="uploader_name" label="提交人" width="120" />
      <el-table-column label="知识类型" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_experience_based ? 'warning' : 'info'" size="small">
            {{ row.is_experience_based ? '经验型' : '事实型' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="review_status" label="审核状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.review_status)" size="small">{{ statusLabel(row.review_status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="提交时间" width="170">
        <template #default="{ row }">{{ row.created_at?.slice(0, 16).replace('T', ' ') }}</template>
      </el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="20" @current-change="fetchList" layout="prev,next" style="margin-top:16px" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getReviewList } from '@/api/review'

const router = useRouter()
const items = ref([]); const loading = ref(false); const total = ref(0); const page = ref(1); const reviewStatus = ref('pending_initial')

onMounted(() => fetchList())

async function fetchList() {
  loading.value = true
  try {
    const { data } = await getReviewList({ page: page.value, review_status: reviewStatus.value })
    items.value = data.items; total.value = data.total
  } finally { loading.value = false }
}

function goDetail(row) { router.push(`/admin/review/${row.id}`) }
function statusTag(s) { return s === 'approved' ? 'success' : s === 'rejected' ? 'danger' : 'warning' }
function statusLabel(s) { return { pending_initial: '待初审', pending_expert: '待复审', approved: '已通过', approved_edited: '通过含修改', rejected: '已驳回' }[s] || s }
</script>
