<template>
  <div class="template-manage">
    <h2>检修流程模板管理</h2>
    <div style="margin-bottom:12px"><el-button type="primary" @click="addTemplate">新增模板</el-button></div>
    <el-table :data="templates">
      <el-table-column prop="name" label="模板名称" />
      <el-table-column prop="maintenance_level" label="检修等级" width="100" />
      <el-table-column prop="version" label="版本" width="80" />
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }"><el-tag :type="row.status==='published'?'success':'info'" size="small">{{ { published:'已发布', draft:'草稿' }[row.status] }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default>
          <el-button size="small">编辑</el-button>
          <el-button size="small">步骤编辑</el-button>
          <el-button size="small" type="danger">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
const templates = ref([])
function addTemplate() { ElMessage.info('功能实现中') }
</script>
