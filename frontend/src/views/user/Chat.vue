<template>
  <div class="chat-page">
    <!-- 左侧对话列表 -->
    <aside class="chat-sidebar">
      <el-button type="primary" @click="newChat" style="width:100%;margin-bottom:12px">新建对话</el-button>
      <div class="conv-list">
        <div v-for="c in conversations" :key="c.id" class="conv-item" :class="{ active: c.id === convId }" @click="switchChat(c.id)">
          <span class="conv-title" @dblclick.stop="startRename(c)">{{ editingId === c.id ? '' : (c.title || '新对话') }}</span>
          <el-input v-if="editingId === c.id" v-model="renameText" size="small" @blur="doRename(c)" @keydown.enter="doRename(c)" @click.stop style="width:100%" />
          <span class="conv-time">{{ c.updated_at?.slice(0, 10) }}</span>
          <span class="conv-actions" @click.stop>
            <el-button size="small" text @click="startRename(c)" title="重命名">✎</el-button>
            <el-button size="small" text @click="delConv(c)" title="删除">✕</el-button>
          </span>
        </div>
      </div>
    </aside>

    <!-- 右侧对话区 -->
    <main class="chat-main">
      <div v-if="!convId" class="chat-empty">点击左侧"新建对话"开始咨询</div>
      <template v-else>
        <div class="chat-messages" ref="msgContainer">
          <div v-for="m in messages" :key="m.id" class="msg-item" :class="m.role">
            <div class="msg-avatar">{{ m.role === 'user' ? '我' : 'AI' }}</div>
            <div class="msg-body">
              <div class="msg-content" v-html="renderContent(m)"></div>
              <!-- 反馈按钮 -->
              <div v-if="m.role === 'assistant'" class="msg-feedback">
                <el-button size="small" text :type="m.feedback==='useful'?'primary':''" @click="doFeedback(m, 'useful')" :disabled="!!m.feedback">有用</el-button>
                <el-button size="small" text :type="m.feedback==='partial'?'warning':''" @click="doFeedback(m, 'partial')" :disabled="!!m.feedback">部分有用</el-button>
                <el-button size="small" text :type="m.feedback==='useless'?'danger':''" @click="doFeedback(m, 'useless')" :disabled="!!m.feedback">无用</el-button>
                <span v-if="uselessCount >= 2" class="ticket-hint">
                  <router-link to="/tickets">问题未解决？提交客服工单 →</router-link>
                </span>
              </div>
            </div>
          </div>
          <div v-if="sending" class="msg-item assistant">
            <div class="msg-avatar">AI</div><div class="msg-body"><div class="msg-content">思考中...</div></div>
          </div>
        </div>
        <!-- 输入区 -->
        <div class="chat-input">
          <el-input v-model="inputText" type="textarea" :rows="3" placeholder="输入问题，描述设备故障现象..." @keydown.enter.exact.prevent="send()" />
          <div class="input-toolbar">
            <div class="toolbar-left">
              <!-- 图片上传（仅千问VL模式下显示） -->
              <template v-if="activeModel === 'qwen'">
                <el-upload :before-upload="handleImageSelect" :show-file-list="false" accept="image/*">
                  <el-button size="small" :disabled="sending">📷 上传图片</el-button>
                </el-upload>
                <span v-if="selectedImage" class="image-tag">{{ selectedImage.name }} <el-button type="danger" link size="small" @click="selectedImage=null">✕</el-button></span>
              </template>
              <!-- 模型选择 -->
              <el-select v-model="activeModel" size="small" style="width:140px;margin-left:12px">
                <el-option label="DeepSeek (文本)" value="deepseek" />
                <el-option label="千问 VL (图文)" value="qwen" />
              </el-select>
            </div>
            <el-button type="primary" @click="send" :loading="sending">发送</el-button>
          </div>
        </div>
      </template>
    </main>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useChat } from '@/composables/useChat'

const route = useRoute()
const router = useRouter()

const {
  conversations, convId, messages, inputText, sending,
  msgContainer, uselessCount, editingId, renameText,
  selectedImage, activeModel,
  loadConversations, newChat, switchChat, send,
  handleImageSelect, doFeedback, renderContent,
  delConv, startRename, doRename,
} = useChat()

onMounted(async () => {
  await loadConversations()
  // 如果路由携带对话ID（如 /chat/123），自动切换到该对话
  const id = Number(route.params.id)
  if (id) {
    await switchChat(id)
  }
})
</script>

<style scoped>
.chat-page { display: flex; height: calc(100vh - 80px); gap: 0; }
.chat-sidebar { width: 240px; background: #fff; border-right: 1px solid #eee; padding: 12px; overflow-y: auto; }
.conv-list { margin-top: 8px; }
.conv-item { padding: 10px 8px; cursor: pointer; border-radius: 4px; border-bottom: 1px solid #f5f5f5; }
.conv-item:hover, .conv-item.active { background: #e8f0fe; }
.conv-title { display: block; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conv-time { font-size: 11px; color: #aaa; }
.conv-actions { display: none; margin-left: auto; }
.conv-item:hover .conv-actions { display: inline-flex; gap: 2px; }
.chat-main { flex: 1; display: flex; flex-direction: column; background: #f5f7fa; }
.chat-empty { flex: 1; display: flex; align-items: center; justify-content: center; color: #999; font-size: 16px; }
.chat-messages { flex: 1; overflow-y: auto; padding: 20px; }
.msg-item { display: flex; gap: 12px; margin-bottom: 20px; }
.msg-item.user { flex-direction: row-reverse; }
.msg-avatar { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; flex-shrink: 0; }
.msg-item.user .msg-avatar { background: #1d4ed8; color: #fff; }
.msg-item.assistant .msg-avatar { background: #10b981; color: #fff; }
.msg-body { max-width: 75%; }
.msg-content { background: #fff; padding: 12px 16px; border-radius: 8px; font-size: 14px; line-height: 1.7; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
.msg-item.user .msg-content { background: #1d4ed8; color: #fff; }
.msg-feedback { margin-top: 4px; padding-left: 4px; }
.ticket-hint { font-size: 12px; color: #e6a23c; margin-left: 8px; }
.chat-input { padding: 16px 20px; background: #fff; border-top: 1px solid #eee; }
</style>
