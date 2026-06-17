<template>
  <div class="knowledge-detail" v-loading="loading">
    <template v-if="entry">
      <!-- 面包屑 -->
      <el-breadcrumb separator=">">
        <el-breadcrumb-item :to="{ name: 'Home' }">首页</el-breadcrumb-item>
        <el-breadcrumb-item>知识详情</el-breadcrumb-item>
      </el-breadcrumb>

      <!-- 标题区 -->
      <div class="detail-header">
        <h2 class="detail-title">{{ entry.title }}</h2>
        <div class="detail-meta">
          <el-tag size="small" type="info" effect="plain">{{ SOURCE_LABELS[entry.source] || entry.source }}</el-tag>
          <span v-if="entry.source_ref">来源：{{ entry.source_ref }}</span>
          <span>版本：{{ entry.current_version }}</span>
          <span>更新：{{ formatDateTime(entry.updated_at) }}</span>
          <span><el-icon><View /></el-icon> {{ entry.view_count || 0 }} 次浏览</span>
        </div>
      </div>

      <!-- 设备与故障标签 -->
      <div class="detail-tags">
        <div v-if="entry.device_models?.length" class="tag-row">
          <span class="tag-label">设备型号：</span>
          <el-tag v-for="dm in entry.device_models" :key="dm" size="small" type="success" effect="plain">{{ dm }}</el-tag>
        </div>
        <div v-if="entry.fault_tags?.length" class="tag-row">
          <span class="tag-label">故障标签：</span>
          <el-tag v-for="ft in entry.fault_tags" :key="ft" size="small" type="warning" effect="plain">{{ ft }}</el-tag>
        </div>
        <div v-if="entry.maintenance_level" class="tag-row">
          <span class="tag-label">检修等级：</span>
          <el-tag size="small" effect="plain">{{ entry.maintenance_level }}</el-tag>
        </div>
      </div>

      <!-- 原文件入口（PDF导入类，仅 source_ref 为有效 URL 路径时显示） -->
      <div v-if="entry.source === 'pdf_import' && entry.source_ref && entry.source_ref.startsWith('/uploads/')" class="file-entry">
        <el-button type="primary" @click="openOriginalFile(entry.source_ref)">
          <el-icon><Document /></el-icon> 查看原始 PDF 文件
        </el-button>
        <span class="file-hint">点击在新标签页中打开原始PDF手册</span>
      </div>

      <!-- 正文内容 -->
      <div class="detail-content" v-html="formattedContent"></div>

      <!-- 步骤化内容（作业指引类型） -->
      <div v-if="entry.is_procedure && entry.procedure_data?.length" class="procedure-section">
        <h3>作业步骤</h3>
        <el-steps direction="vertical" :active="-1">
          <el-step v-for="(step, i) in entry.procedure_data" :key="i" :title="`步骤${i + 1}：${step.title || step.content?.slice(0, 40)}`">
            <template #description>
              <div v-html="step.content"></div>
              <div v-if="step.compliance_items?.length" class="compliance-list">
                <div v-for="(ci, j) in step.compliance_items" :key="j" class="compliance-item">
                  <el-icon color="#f56c6c"><WarningFilled /></el-icon> {{ ci }}
                </div>
              </div>
            </template>
          </el-step>
        </el-steps>
      </div>

      <!-- 版本信息 -->
      <div v-if="entry.versions?.length > 1" class="version-info">
        <span class="info-label">历史版本：</span>
        <el-tag v-for="v in entry.versions" :key="v.id" size="small" class="ver-tag">
          {{ v.version }} — {{ v.change_summary || '无说明' }}
        </el-tag>
      </div>

      <!-- 操作按钮 -->
      <div class="detail-actions">
        <el-button v-if="entry.is_procedure" type="success" @click="$router.push(`/task?tpl=${entry.id}`)">
          开始作业
        </el-button>
        <el-button plain @click="$router.back()">返回</el-button>
      </div>
    </template>
    <el-empty v-else-if="!loading" description="知识条目不存在" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { View, WarningFilled, Document } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getKnowledgeDetail } from '@/api/knowledge'
import { SOURCE_LABELS } from '@/utils/constants'
import { formatDateTime } from '@/utils/helpers'

const route = useRoute()
const router = useRouter()
const entry = ref(null)
const loading = ref(false)

/** 格式化正文：换行转<br>（仅纯文本，HTML标签保留不动） */
const formattedContent = computed(() => {
  const raw = entry.value?.content || ''
  // 已有HTML标签 → 直接渲染
  if (/<\/?(div|p|table|h[1-6]|ul|ol|li|img|hr|pre)\b/i.test(raw)) return raw
  // 纯文本 → \n 转 <br>
  return raw.replace(/\n/g, '<br>')
})

onMounted(() => {
  const id = Number(route.params.id)
  if (id && !isNaN(id)) fetchDetail(id)
  else loading.value = false
})

async function fetchDetail(id) {
  loading.value = true
  try {
    const { data } = await getKnowledgeDetail(id)
    entry.value = data
  } catch (e) {
    if (e.code !== 'ERR_CANCELED') loading.value = false
  }
  loading.value = false
}

/** 打开原文件（encodeURI 处理中文路径，保留 / 等URL结构字符） */
function openOriginalFile(url) {
  window.open(encodeURI(url), '_blank')
}
</script>

<style scoped>
.knowledge-detail { max-width: 900px; margin: 0 auto; padding: 20px; }

.detail-header { margin: 16px 0 12px; }
.detail-title { font-size: 22px; font-weight: 700; color: #222; margin-bottom: 10px; }
.detail-meta { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; font-size: 13px; color: #999; }

.detail-tags { margin-bottom: 20px; display: flex; flex-direction: column; gap: 8px; }
.tag-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.tag-label { font-size: 13px; color: #666; white-space: nowrap; }

.file-entry { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; padding: 14px 18px; background: #f0f7ff; border-radius: 8px; border: 1px solid #dbeafe; }
.file-hint { font-size: 12px; color: #999; }
.detail-actions { margin-top: 24px; display: flex; gap: 12px; }
</style>

<!-- 正文内容样式（非scoped，确保v-html渲染的元素可被样式命中） -->
<style>
.detail-content { padding: 20px; background: #fff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); line-height: 1.9; font-size: 15px; color: #333; }
.detail-content p { margin: 0 0 12px 0; }
.detail-content img { max-width: 100% !important; border-radius: 6px; margin: 10px 0; display: block; }
.detail-content table { border-collapse: collapse; width: 100%; margin: 12px 0; }
.detail-content td, .detail-content th { border: 1px solid #e5e7eb; padding: 8px 12px; }
.detail-content hr { margin: 20px 0; }
</style>
