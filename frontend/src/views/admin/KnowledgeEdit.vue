<template>
  <div class="knowledge-edit">
    <h2>{{ isNew ? '新增知识' : '编辑知识' }}</h2>
    <el-form :model="form" label-width="100px" v-loading="loading">
      <el-form-item label="标题" required><el-input v-model="form.title" placeholder="知识条目标题" /></el-form-item>
      <el-form-item label="摘要"><el-input v-model="form.summary" type="textarea" :rows="2" placeholder="列表页展示的简短摘要" /></el-form-item>
      <el-form-item label="来源类型"><el-select v-model="form.source"><el-option label="手动编写" value="manual" /><el-option label="PDF导入" value="pdf_import" /><el-option label="用户上传" value="user_upload" /></el-select></el-form-item>
      <el-form-item label="来源引用"><el-input v-model="form.source_ref" placeholder="手册名称+版本号 或 工单号" /></el-form-item>
      <el-form-item label="设备型号">
        <el-select v-model="form.device_models" multiple filterable allow-create placeholder="输入设备型号后回车添加" style="width:100%" />
      </el-form-item>
      <el-form-item label="故障标签">
        <el-select v-model="form.fault_tags" multiple filterable allow-create placeholder="输入故障标签" style="width:100%" />
      </el-form-item>
      <el-form-item label="检修等级"><el-select v-model="form.maintenance_level" placeholder="可选"><el-option label="日常检修" value="日常" /><el-option label="定修" value="定修" /><el-option label="大修" value="大修" /></el-select></el-form-item>
      <el-form-item label="正文内容" required>
        <el-input v-model="form.content" type="textarea" :rows="12" placeholder="知识条目正文（富文本）" />
      </el-form-item>
      <el-form-item label="修改说明" v-if="!isNew && form.change_summary !== undefined">
        <el-input v-model="form.change_summary" placeholder="请简要描述本次修改的内容" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="submit" :loading="saving">{{ isNew ? '创建' : '保存' }}</el-button>
        <el-button @click="$router.back()">取消</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getKnowledgeDetail, createKnowledge, updateKnowledge } from '@/api/knowledge'

const route = useRoute(); const router = useRouter()
const isNew = computed(() => !route.params.id)
const loading = ref(false); const saving = ref(false)
const form = ref({ title: '', content: '', summary: '', source: 'manual', source_ref: '', device_models: [], fault_tags: [], maintenance_level: '', change_summary: '' })

onMounted(() => { if (!isNew.value) fetchDetail() })

async function fetchDetail() {
  loading.value = true
  try { const { data } = await getKnowledgeDetail(route.params.id); form.value = { ...data, change_summary: '' } } finally { loading.value = false }
}

async function submit() {
  if (!form.value.title || !form.value.content) { ElMessage.warning('标题和内容为必填'); return }
  saving.value = true
  try {
    if (isNew.value) {
      await createKnowledge(form.value)
      ElMessage.success('知识条目已创建')
    } else {
      await updateKnowledge(route.params.id, form.value)
      ElMessage.success('知识条目已更新')
    }
    router.push('/admin/knowledge')
  } finally { saving.value = false }
}
</script>
