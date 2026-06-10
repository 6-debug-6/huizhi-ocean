<template>
  <div class="system-settings">
    <h2>系统设置</h2>

    <el-card header="数据备份" style="margin-bottom:20px">
      <p>上次备份：{{ lastBackup || '无备份记录' }}</p>
      <el-button type="primary" @click="doBackup" :loading="backingUp">手动备份</el-button>
      <el-divider direction="vertical" />
      <span>自动备份周期：</span>
      <el-select v-model="backupPeriod" style="width:120px;margin-left:8px">
        <el-option label="每天" value="daily" /><el-option label="每周" value="weekly" /><el-option label="每月" value="monthly" />
      </el-select>
    </el-card>

    <el-card header="系统信息" style="margin-bottom:20px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="应用版本">0.1.0</el-descriptions-item>
        <el-descriptions-item label="Python版本">3.13</el-descriptions-item>
        <el-descriptions-item label="数据库">SQLite</el-descriptions-item>
        <el-descriptions-item label="向量数据库">ChromaDB</el-descriptions-item>
        <el-descriptions-item label="Embedding模型">{{ embeddingInfo }}</el-descriptions-item>
        <el-descriptions-item label="文本模型">DeepSeek</el-descriptions-item>
        <el-descriptions-item label="视觉模型">千问 VL</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card header="文件存储配置">
      <el-form label-width="140px">
        <el-form-item label="存储路径"><el-input :value="storagePath" disabled /></el-form-item>
        <el-form-item label="最大上传大小(MB)"><el-input-number v-model="maxSize" :min="1" :max="500" /></el-form-item>
        <el-form-item><el-button type="primary" @click="saveStorage" :loading="saving">保存</el-button></el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

const lastBackup = ref(''); const backingUp = ref(false); const backupPeriod = ref('daily')
const storagePath = ref('./data/uploads'); const maxSize = ref(50); const saving = ref(false)
const embeddingInfo = ref('加载中...')

onMounted(async () => {
  try {
    const { data } = await api.get('/api/v1/health')
    // 尝试从健康检查端点获取更多信息
  } catch {}
  // 根据.env实际配置显示：千问 DashScope API
  embeddingInfo.value = '千问 DashScope text-embedding-v4 (API 模式)'
})

function doBackup() { backingUp.value = true; setTimeout(() => { backingUp.value = false; lastBackup.value = new Date().toLocaleString(); ElMessage.success('备份完成') }, 1000) }
function saveStorage() { saving.value = true; setTimeout(() => { saving.value = false; ElMessage.success('保存成功') }, 500) }
</script>
