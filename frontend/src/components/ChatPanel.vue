<template>
  <!-- 悬浮按钮（最小化时显示） -->
  <div v-if="!visible" class="cp-float-btn" @click="showPanel">
    <img src="@/assets/ai-assistant.jpg" class="cp-float-icon" alt="AI助手" />
  </div>

  <!-- 弹出面板 -->
  <transition name="cp-slide">
    <div v-if="visible" class="cp-panel">
      <div class="cp-header">
        <span class="cp-title">AI 检修助手</span>
        <div class="cp-header-actions">
          <el-button text size="small" @click="goFullChat" title="全屏展开">
            <el-icon><FullScreen /></el-icon>
          </el-button>
          <el-button text size="small" @click="hidePanel" title="最小化">
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
      </div>

      <!-- 上下文提示 -->
      <div v-if="contextHint" class="cp-context">{{ contextHint }}</div>

      <!-- 消息列表（紧凑模式，显示最近消息） -->
      <div class="cp-messages" ref="msgContainer">
        <div v-if="!convId && !sending" class="cp-empty">输入问题咨询AI助手</div>
        <div v-for="m in visibleMessages" :key="m.id" class="cp-msg" :class="m.role">
          <div class="cp-msg-content" v-html="renderContent(m)"></div>
          <!-- 来源链接 -->
          <div v-if="m.role==='assistant' && m.sources?.length" class="cp-sources">
            <el-tag v-for="(s, i) in m.sources" :key="i" size="small" type="info" effect="plain"
              class="cp-source-tag" @click="goKnowledge(s)">
              {{ s.title?.slice(0, 20) || '来源' }}
            </el-tag>
          </div>
        </div>
        <div v-if="sending" class="cp-msg assistant">
          <div class="cp-msg-content">思考中...</div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="cp-input-area">
        <div style="display:flex;gap:4px;margin-bottom:6px">
          <el-select v-model="chatMode" size="small" style="width:110px">
            <el-option label="🔧 检修" value="rag" />
            <el-option label="💬 闲聊" value="casual" />
          </el-select>
        </div>
        <el-input
          v-model="inputText"
          :rows="2"
          type="textarea"
          placeholder="输入问题..."
          @keydown.enter.exact.prevent="send()"
        />
        <el-button type="primary" size="small" @click="send()" :loading="sending" style="margin-top:6px">
          发送
        </el-button>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { FullScreen, Close } from '@element-plus/icons-vue'
import { useChat } from '@/composables/useChat'

const props = defineProps({
  deviceModel: { type: String, default: '' },
  taskStep: { type: String, default: '' },
  taskId: { type: Number, default: null },
  knowledgeContext: { type: String, default: '' },
})

const emit = defineEmits(['update:visible'])
const router = useRouter()
const visible = ref(false)

// 初始化 useChat 并注入上下文
const {
  convId, messages, inputText, sending, msgContainer,
  renderContent, send, loadConversations, newChat, chatMode,
} = useChat({
  deviceModel: props.deviceModel,
  taskStep: props.taskStep,
  taskId: props.taskId,
  knowledgeContext: props.knowledgeContext,
})

// 只显示最近 6 条消息
const visibleMessages = computed(() => messages.value.slice(-6))

// 上下文提示文本
const contextHint = computed(() => {
  const parts = []
  if (props.deviceModel) parts.push(`设备：${props.deviceModel}`)
  if (props.taskStep) parts.push(`步骤：${props.taskStep}`)
  if (props.knowledgeContext) parts.push(`知识：${props.knowledgeContext}`)
  return parts.length ? parts.join(' · ') : ''
})

onMounted(() => loadConversations())

function showPanel() {
  visible.value = true
  // 如果没有当前对话，自动创建
  if (!convId.value) {
    newChat()
  }
}

function hidePanel() {
  visible.value = false
}

function goFullChat() {
  if (convId.value) {
    router.push(`/chat/${convId.value}`)
  } else {
    router.push('/chat')
  }
}

/** 点击来源标签跳转知识详情 */
function goKnowledge(source) {
  if (source?.entry_id) {
    router.push(`/knowledge/${source.entry_id}`)
  }
}
</script>

<style scoped>
/* 悬浮按钮 */
.cp-float-btn {
  position: fixed; bottom: 80px; right: 24px; z-index: 1000;
  width: 48px; height: 48px; border-radius: 50%;
  background: #1d4ed8; color: #fff;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; box-shadow: 0 4px 12px rgba(29,78,216,0.3);
  transition: transform 0.2s;
}
.cp-float-btn:hover { transform: scale(1.1); }
.cp-float-icon { width: 48px; height: 48px; border-radius: 50%; object-fit: cover; }

/* 面板 */
.cp-panel {
  position: fixed; bottom: 20px; right: 20px; z-index: 1000;
  width: 400px; max-height: 560px;
  background: #fff; border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.12);
  display: flex; flex-direction: column;
}

/* 面板头部 */
.cp-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px; border-bottom: 1px solid #eee;
}
.cp-title { font-size: 14px; font-weight: 600; }
.cp-header-actions { display: flex; gap: 4px; }

/* 上下文 */
.cp-context {
  font-size: 12px; color: #1d4ed8; background: #e8f0fe;
  padding: 6px 12px; border-bottom: 1px solid #dbeafe;
}

/* 消息区 */
.cp-messages { flex: 1; overflow-y: auto; padding: 12px; min-height: 200px; max-height: 340px; }
.cp-empty { text-align: center; color: #999; font-size: 13px; padding: 40px 0; }
.cp-msg { margin-bottom: 10px; }
.cp-msg-content { padding: 8px 12px; border-radius: 8px; font-size: 13px; line-height: 1.6; display: inline-block; max-width: 90%; }
.cp-msg.user .cp-msg-content { background: #1d4ed8; color: #fff; }
.cp-msg.assistant .cp-msg-content { background: #f0f2f5; color: #333; }

/* 来源标签 */
.cp-sources { margin-top: 4px; display: flex; gap: 4px; flex-wrap: wrap; }
.cp-source-tag { cursor: pointer; }
.cp-source-tag:hover { opacity: 0.8; }

/* 输入区 */
.cp-input-area { padding: 10px 12px; border-top: 1px solid #eee; }

/* 过渡动画 */
.cp-slide-enter-active { transition: all 0.25s ease-out; }
.cp-slide-leave-active { transition: all 0.2s ease-in; }
.cp-slide-enter-from { opacity: 0; transform: translateY(20px); }
.cp-slide-leave-to { opacity: 0; transform: translateY(20px); }
</style>
