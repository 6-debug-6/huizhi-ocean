<template>
  <div class="model-config">
    <h2>大模型配置</h2>
    <el-form label-width="120px" style="max-width:600px">
      <el-form-item label="模型名称"><el-input v-model="config.model_name" disabled /></el-form-item>
      <el-form-item label="模型类型"><el-tag>{{ config.model_type === 'cloud' ? '云端API' : '本地部署' }}</el-tag></el-form-item>
      <el-form-item label="API地址"><el-input v-model="config.api_base" /></el-form-item>
      <el-form-item label="API密钥"><el-input v-model="config.api_key" type="password" show-password placeholder="留空则不修改" /></el-form-item>
      <el-form-item label="Temperature"><el-slider v-model="config.temperature" :min="0" :max="1" :step="0.1" show-input style="width:300px" /></el-form-item>
      <el-form-item label="Max Tokens"><el-input-number v-model="config.max_tokens" :min="512" :max="32768" :step="512" /></el-form-item>
      <el-form-item label="检索召回数"><el-input-number v-model="config.top_k" :min="1" :max="20" /></el-form-item>
      <el-form-item>
        <el-button type="primary" @click="save" :loading="saving">保存配置</el-button>
      </el-form-item>
    </el-form>

    <el-divider />
    <h3>调用统计（近7天）</h3>
    <el-row :gutter="20">
      <el-col :span="8"><el-card><div class="stat-num">{{ stats.call_count }}</div><div class="stat-label">调用次数</div></el-card></el-col>
      <el-col :span="8"><el-card><div class="stat-num">{{ stats.avg_time }}ms</div><div class="stat-label">平均响应时间</div></el-card></el-col>
    </el-row>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

const saving = ref(false)
const config = reactive({ model_name: 'deepseek-chat', model_type: 'cloud', api_base: 'https://api.deepseek.com', api_key: '', temperature: 0.3, max_tokens: 4096, top_k: 5 })
const stats = reactive({ call_count: 0, avg_time: 0 })

async function save() {
  saving.value = true
  try { ElMessage.success('配置已保存（需重启生效）') } finally { saving.value = false }
}
</script>

<style scoped>
.stat-num { font-size: 28px; font-weight: 700; color: #1d4ed8; }
.stat-label { font-size: 13px; color: #999; }
</style>
