<template>
  <div class="versions-page">
    <el-button @click="$router.back()" style="margin-bottom:16px">← 返回</el-button>
    <h2>版本历史</h2>
    <el-table :data="versions" v-loading="loading">
      <el-table-column prop="version" label="版本号" width="100" />
      <el-table-column prop="version_num" label="版本序号" width="80" />
      <el-table-column prop="change_summary" label="修改说明" />
      <el-table-column prop="created_at" label="创建时间" width="170"><template #default="{ row }">{{ row.created_at?.slice(0, 16).replace('T', ' ') }}</template></el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button size="small" type="warning" @click="doRollback(row)" :loading="rolling === row.id">回滚</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getVersions, rollbackVersion } from '@/api/knowledge'

const route = useRoute()
const versions = ref([]); const loading = ref(false); const rolling = ref(null)

onMounted(() => fetchVersions())

async function fetchVersions() {
  loading.value = true
  try { const { data } = await getVersions(route.params.id); versions.value = data } finally { loading.value = false }
}

async function doRollback(row) {
  await ElMessageBox.confirm(`确定回滚到版本 ${row.version} 吗？回滚后将生成一个新版本。`, '确认回滚')
  rolling.value = row.id
  try {
    await rollbackVersion(route.params.id, row.id)
    ElMessage.success(`已回滚至 ${row.version}`)
    fetchVersions()
  } finally { rolling.value = null }
}
</script>
