<template>
  <div class="home-page">
    <!-- 左侧分类导航 -->
    <aside class="home-sidebar">
      <div class="sidebar-title">知识分类</div>
      <div class="category-block">
        <div
          class="category-root"
          :class="{ active: activeCategory === 'all' }"
          @click="selectCategory('all')"
        >全部知识</div>
      </div>
      <div class="category-block">
        <div class="category-label">设备型号</div>
        <div
          v-for="dm in tags.device_models"
          :key="'dm-' + dm"
          class="category-item"
          :class="{ active: selectedDevice === dm }"
          @click="selectDevice(dm)"
        >{{ dm }}</div>
      </div>
      <div class="category-block">
        <div class="category-label">故障标签</div>
        <div
          v-for="ft in tags.fault_tags"
          :key="'ft-' + ft"
          class="category-item"
          :class="{ active: selectedFault === ft }"
          @click="selectFault(ft)"
        >{{ ft }}</div>
      </div>
    </aside>

    <!-- 右侧主区域 -->
    <main class="home-main">
      <!-- 顶部搜索栏 -->
      <div class="home-toolbar">
        <el-input
          v-model="searchText"
          placeholder="搜索知识库..."
          clearable
          :prefix-icon="Search"
          class="search-input"
          @input="onSearchInput"
        />
        <el-radio-group v-model="sortBy" @change="fetchList" size="small">
          <el-radio-button value="latest">最新</el-radio-button>
          <el-radio-button value="hot">最热</el-radio-button>
        </el-radio-group>
      </div>

      <!-- 最近浏览 -->
      <div v-if="recentViews.length && !searchText && activeCategory === 'all'" class="recent-section">
        <div class="section-title">最近浏览</div>
        <div class="recent-list">
          <el-tag
            v-for="rv in recentViews"
            :key="rv.id"
            class="recent-tag"
            closable
            @click="goDetail(rv.id)"
            @close="removeRecent(rv.id)"
          >{{ rv.title }}</el-tag>
        </div>
      </div>

      <!-- 知识卡片列表 -->
      <div v-loading="loading" class="card-area">
        <div v-if="items.length" class="card-grid">
          <el-card
            v-for="item in items"
            :key="item.id"
            class="k-card"
            shadow="hover"
            @click="goDetail(item.id)"
          >
            <div class="k-card-title">
              <el-tag v-if="item.source === 'pdf_import'" type="danger" size="small" effect="plain" style="margin-right:4px">PDF</el-tag>
              {{ item.title }}
            </div>
            <div class="k-card-summary">{{ item.summary || item.title }}</div>
            <div class="k-card-tags">
              <el-tag v-for="dm in item.device_models" :key="dm" size="small" type="success" effect="plain">{{ dm }}</el-tag>
              <el-tag v-for="ft in item.fault_tags" :key="ft" size="small" type="warning" effect="plain">{{ ft }}</el-tag>
            </div>
            <div class="k-card-footer">
              <div class="k-card-meta">
                <el-tag size="small" type="info" effect="plain">{{ SOURCE_LABELS[item.source] || item.source }}</el-tag>
                <span class="k-card-views" v-if="item.view_count"><el-icon><View /></el-icon> {{ item.view_count }}</span>
              </div>
              <span class="k-card-time">{{ formatDate(item.updated_at) }}</span>
            </div>
          </el-card>
        </div>
        <el-empty v-else-if="!loading" :description="searchText || selectedDevice || selectedFault ? '没有匹配的知识条目' : '知识库暂为空'">
          <template v-if="searchText || selectedDevice || selectedFault">
            <p style="color:#999;font-size:13px;margin-bottom:8px">尝试更换筛选条件或搜索关键词</p>
          </template>
        </el-empty>
      </div>

      <!-- 分页 -->
      <div v-if="total > pageSize" class="home-pagination">
        <el-pagination
          v-model:current-page="page"
          :total="total"
          :page-size="pageSize"
          layout="total, prev, pager, next"
          @current-change="fetchList"
        />
      </div>
    </main>

    <!-- AI悬浮对话面板 -->
    <ChatPanel :knowledge-context="currentKnowledgeContext" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Search, View } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getKnowledgeList, getKnowledgeTags } from '@/api/knowledge'
import { SOURCE_LABELS } from '@/utils/constants'
import { formatDate } from '@/utils/helpers'
import ChatPanel from '@/components/ChatPanel.vue'

const router = useRouter()

// 标签数据
const tags = reactive({ device_models: [], fault_tags: [] })

// 筛选状态
const activeCategory = ref('all')
const selectedDevice = ref('')
const selectedFault = ref('')
const searchText = ref('')
const sortBy = ref('latest')
const page = ref(1)
const pageSize = 20
const total = ref(0)
const loading = ref(false)
const items = ref([])

// 最近浏览（localStorage）
const recentViews = ref(JSON.parse(localStorage.getItem('recent_knowledge_views') || '[]'))

let searchTimer = null

onMounted(() => {
  loadTags()
  fetchList()
})

/** 加载分类标签 */
async function loadTags() {
  try {
    const { data } = await getKnowledgeTags()
    tags.device_models = data.device_models || []
    tags.fault_tags = data.fault_tags || []
  } catch {}
}

/** 加载知识列表 */
async function fetchList() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize, status: 'published', sort_by: sortBy.value }
    if (searchText.value) params.keyword = searchText.value
    if (selectedDevice.value) params.device_model = selectedDevice.value
    if (selectedFault.value) params.fault_tag = selectedFault.value
    const { data } = await getKnowledgeList(params)
    items.value = data.items || []
    total.value = data.total || 0
  } catch {}
  loading.value = false
}

/** 分类选择 */
function selectCategory(cat) {
  activeCategory.value = cat
  selectedDevice.value = ''
  selectedFault.value = ''
  page.value = 1
  fetchList()
}

function selectDevice(dm) {
  selectedDevice.value = selectedDevice.value === dm ? '' : dm
  selectedFault.value = ''
  activeCategory.value = ''
  page.value = 1
  fetchList()
}

function selectFault(ft) {
  selectedFault.value = selectedFault.value === ft ? '' : ft
  selectedDevice.value = ''
  activeCategory.value = ''
  page.value = 1
  fetchList()
}

// 当前浏览的知识条目上下文（传给 ChatPanel）
const selectedKnowledge = ref({ title: '', summary: '' })
const currentKnowledgeContext = computed(() => {
  if (!selectedKnowledge.value.title) return ''
  return `[知识条目] ${selectedKnowledge.value.title}${selectedKnowledge.value.summary ? '：' + selectedKnowledge.value.summary : ''}`
})

/** 搜索防抖 */
function onSearchInput() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    fetchList()
  }, 300)
}

/** 跳转详情 */
function goDetail(id) {
  // 记录最近浏览
  const item = items.value.find(i => i.id === id)
  let recents = JSON.parse(localStorage.getItem('recent_knowledge_views') || '[]')
  if (item) {
    selectedKnowledge.value = { title: item.title, summary: item.summary || '' }
    recents = recents.filter(r => r.id !== id)
    recents.unshift({ id: item.id, title: item.title })
    if (recents.length > 10) recents = recents.slice(0, 10)
    localStorage.setItem('recent_knowledge_views', JSON.stringify(recents))
  }
  router.push(`/knowledge/${id}`)
}

function removeRecent(id) {
  recentViews.value = recentViews.value.filter(r => r.id !== id)
  localStorage.setItem('recent_knowledge_views', JSON.stringify(recentViews.value))
}
</script>

<style scoped>
.home-page { display: flex; gap: 20px; min-height: calc(100vh - 120px); }

/* 左侧导航 */
.home-sidebar { width: 220px; flex-shrink: 0; background: #fff; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); align-self: flex-start; position: sticky; top: 16px; }
.sidebar-title { font-size: 15px; font-weight: 600; margin-bottom: 12px; color: #333; }
.category-block { margin-bottom: 16px; }
.category-label { font-size: 12px; color: #999; margin-bottom: 6px; padding-left: 2px; }
.category-root { padding: 6px 10px; cursor: pointer; border-radius: 6px; font-size: 14px; transition: all 0.2s; }
.category-root:hover { background: #f0f5ff; }
.category-root.active { background: #e6f0ff; color: #1d4ed8; font-weight: 500; }
.category-item { padding: 5px 10px; cursor: pointer; border-radius: 6px; font-size: 13px; color: #555; transition: all 0.2s; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.category-item:hover { background: #f5f5f5; }
.category-item.active { background: #e6f0ff; color: #1d4ed8; font-weight: 500; }

/* 右侧主区域 */
.home-main { flex: 1; min-width: 0; }

/* 搜索栏 */
.home-toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 16px; }
.search-input { max-width: 480px; }

/* 最近浏览 */
.recent-section { margin-bottom: 16px; }
.section-title { font-size: 13px; color: #999; margin-bottom: 8px; }
.recent-list { display: flex; gap: 8px; flex-wrap: wrap; }
.recent-tag { cursor: pointer; }
.recent-tag:hover { opacity: 0.8; }

/* 卡片网格 */
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }

/* 单张卡片 */
.k-card { cursor: pointer; transition: all 0.25s ease; border: 1px solid transparent; position: relative; overflow: hidden; }
.k-card:hover { transform: translateY(-3px); box-shadow: 0 8px 25px rgba(29,78,216,0.12); border-color: #dbeafe; }
.k-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: linear-gradient(90deg, #1d4ed8, #3b82f6, #60a5fa); transform: scaleX(0); transition: transform 0.3s; }
.k-card:hover::before { transform: scaleX(1); }
.k-card-title { font-size: 15px; font-weight: 600; margin-bottom: 8px; color: #222; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.k-card-summary { font-size: 13px; color: #777; margin-bottom: 10px; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; line-height: 1.5; }
.k-card-tags { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
.k-card-footer { display: flex; justify-content: space-between; align-items: center; }
.k-card-meta { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.k-card-views { color: #bbb; display: flex; align-items: center; gap: 2px; }
.k-card-time { font-size: 12px; color: #bbb; }

/* 分页 */
.home-pagination { display: flex; justify-content: center; margin-top: 24px; }
</style>
