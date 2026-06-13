<template>
  <div class="case-upload">
    <h2>提交检修案例</h2>
    <el-form :model="form" label-width="120px" style="max-width:800px" v-loading="submitting">
      <el-form-item label="案例标题" required>
        <el-input v-model="form.title" placeholder="简要描述故障和修复内容" maxlength="300" />
      </el-form-item>

      <el-form-item label="故障描述" required>
        <el-input v-model="form.content" type="textarea" :rows="8" placeholder="详细描述故障现象、排查过程、最终发现的根因" />
      </el-form-item>

      <el-form-item label="设备型号">
        <el-select v-model="form.device_models" multiple filterable allow-create placeholder="输入设备型号后回车添加" style="width:100%"/>
      </el-form-item>

      <el-form-item label="故障分类">
        <el-select v-model="form.fault_tags" multiple filterable allow-create placeholder="如：机械故障、电气故障" style="width:100%"/>
      </el-form-item>

      <el-form-item label="知识类型">
        <el-radio-group v-model="form.is_experience_based">
          <el-radio :value="false">事实型（客观事实描述）</el-radio>
          <el-radio :value="true">经验型（含个人判断，需专家复审）</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="现场图片">
        <el-upload :http-request="uploadImage" :show-file-list="false" accept="image/*">
          <el-button size="small">上传图片</el-button>
        </el-upload>
        <div v-if="form.images.length" class="preview-list">
          <div v-for="(img, i) in form.images" :key="i" class="preview-item">
            <span>{{ typeof img === 'string' ? img.split('/').pop() : img }}</span>
            <el-button type="danger" link size="small" @click="form.images.splice(i,1)">删除</el-button>
          </div>
        </div>
      </el-form-item>

      <el-form-item>
        <el-button type="primary" @click="submit" :loading="submitting">提交审核</el-button>
        <el-button @click="saveDraft" :disabled="submitting">保存草稿</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/api'

const router = useRouter()
const submitting = ref(false)

const form = reactive({
  title: '',
  content: '',
  device_models: [],
  fault_tags: [],
  is_experience_based: false,
  images: [],
  attachments: [],
})

// 恢复草稿
onMounted(() => {
  const draft = localStorage.getItem('case_draft')
  if (draft) {
    try { Object.assign(form, JSON.parse(draft)) } catch {}
  }
})

async function uploadImage(options) {
  const fd = new FormData()
  fd.append('file', options.file)
  try {
    const { data } = await api.post('/api/v1/upload', fd)
    form.images.push(data.url)
  } catch { ElMessage.error('图片上传失败') }
}

async function submit() {
  if (!form.title || !form.content) { ElMessage.warning('标题和故障描述为必填'); return }
  submitting.value = true
  try {
    await api.post('/api/v1/cases/', {
      title: form.title,
      content: form.content,
      device_models: form.device_models,
      fault_tags: form.fault_tags,
      is_experience_based: form.is_experience_based,
      images: form.images,
      attachments: form.attachments,
    })
    ElMessage.success('案例已提交，等待管理员审核')
    localStorage.removeItem('case_draft')
    router.push('/workspace')
  } catch {}
  finally { submitting.value = false }
}

function saveDraft() {
  localStorage.setItem('case_draft', JSON.stringify({ ...form }))
  ElMessage.success('草稿已保存')
}
</script>

<style scoped>
.preview-list { margin-top: 8px; }
.preview-item { font-size: 13px; display: flex; align-items: center; gap: 8px; padding: 2px 0; }
</style>
