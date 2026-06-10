<template>
  <div class="device-manage">
    <h2>设备型号与故障分类管理</h2>
    <el-tabs v-model="activeTab">
      <!-- 设备型号 -->
      <el-tab-pane label="设备型号" name="devices">
        <div style="margin-bottom:12px"><el-button type="primary" @click="addDevice">新增设备型号</el-button></div>
        <el-table :data="devices">
          <el-table-column prop="name" label="型号名称" />
          <el-table-column prop="production_line" label="产线" />
          <el-table-column prop="category" label="分类" />
          <el-table-column prop="status" label="状态" width="80">
            <template #default="{ row }"><el-tag :type="row.status==='active'?'success':'info'" size="small">{{ row.status==='active'?'启用':'已归档' }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button size="small">编辑</el-button>
              <el-button size="small" type="danger" v-if="row.status==='active'">归档</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 故障分类 -->
      <el-tab-pane label="故障分类" name="faults">
        <div style="margin-bottom:12px"><el-button type="primary" @click="addFault">新增根分类</el-button></div>
        <el-tree :data="faultTree" node-key="id" default-expand-all>
          <template #default="{ node, data }">
            <span class="tree-node">
              {{ data.name }}
              <el-button size="small" style="margin-left:8px" @click="addChild(data)">+子分类</el-button>
              <el-button size="small" type="danger" @click="delFault(data)">删除</el-button>
            </span>
          </template>
        </el-tree>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const activeTab = ref('devices')
const devices = ref([])
const faultTree = ref([])

function addDevice() { ElMessage.info('功能实现中') }
function addFault() { ElMessage.info('功能实现中') }
function addChild(data) { ElMessage.info('功能实现中') }
function delFault(data) { ElMessage.info('功能实现中') }
</script>

<style scoped>
.tree-node { font-size: 14px; }
</style>
