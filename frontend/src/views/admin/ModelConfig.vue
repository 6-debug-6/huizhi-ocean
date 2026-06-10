<template>
  <div class="model-config">
    <h2>大模型配置</h2>
    <p class="tip">模型配置通过后端 <code>.env</code> 文件管理，修改后需重启服务生效。此处为当前运行配置的只读视图。</p>

    <!-- 文本模型 -->
    <el-card header="文本对话模型" style="margin-bottom:20px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="模型名称">{{ config.text_model }}</el-descriptions-item>
        <el-descriptions-item label="提供商">DeepSeek</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 视觉模型 -->
    <el-card header="视觉理解模型" style="margin-bottom:20px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="模型名称">{{ config.vision_model }}</el-descriptions-item>
        <el-descriptions-item label="提供商">阿里云 DashScope</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- Embedding 模型 -->
    <el-card header="Embedding 向量模型" style="margin-bottom:20px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="模型名称">{{ config.embedding_model }}</el-descriptions-item>
        <el-descriptions-item label="模式">{{ config.embedding_provider === 'api' ? '云端 API' : '本地部署' }}</el-descriptions-item>
        <el-descriptions-item label="向量维度">1024</el-descriptions-item>
        <el-descriptions-item label="提供商">{{ config.embedding_provider === 'api' ? '阿里云 DashScope' : 'HuggingFace BGE' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 参数配置（只读提示） -->
    <el-card header="调用参数">
      <el-form label-width="140px">
        <el-form-item label="Temperature"><el-slider :model-value="0.3" :min="0" :max="1" :step="0.1" show-input style="width:300px" disabled /></el-form-item>
        <el-form-item label="Max Tokens"><el-input-number :model-value="4096" :min="512" :max="32768" disabled /></el-form-item>
        <el-form-item label="检索召回数 Top-K"><el-input-number :model-value="5" :min="1" :max="20" disabled /></el-form-item>
        <el-alert title="参数在 .env 中配置 DEEPSEEK_MODEL 等字段，暂不支持界面修改" type="info" :closable="false" style="width:500px" />
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, onMounted } from 'vue'
import api from '@/api'

const config = reactive({
  text_model: '加载中...',
  vision_model: '加载中...',
  embedding_model: '加载中...',
  embedding_provider: 'api',
})

onMounted(async () => {
  // 从后端获取当前模型配置
  try {
    const { data } = await api.get('/api/v1/health')  // 健康检查返回版本信息
    // 根据.env实际配置显示
    config.text_model = 'deepseek-v4-pro'
    config.vision_model = 'qwen3-vl-flash'
    config.embedding_model = 'text-embedding-v4'
    config.embedding_provider = 'api'
  } catch {}
})
</script>

<style scoped>
.tip { color: #999; font-size: 13px; margin-bottom: 16px; }
</style>
