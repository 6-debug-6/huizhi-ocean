# 设备检修知识检索与作业系统

基于多模态大模型技术的工业设备检修知识检索与作业辅助系统。

## 技术栈

| 层         | 技术                   | 备注                      |
| ---------- | ---------------------- | ------------------------- |
| 前端       | Vue 3 + Vite           | PC Web 端，响应式适配平板 |
| 后端       | FastAPI (Python 3.10+) | REST API                  |
| LLM 编排   | LangChain              | 模型调用、检索链路编排    |
| 大模型     | DeepSeek / 千问 API    | 支持本地部署或云端接入    |
| 向量数据库 | ChromaDB               | 需验证 LoongArch 兼容性   |
| 关系数据库 | PostgreSQL 或 SQLite   | SQLite 用于轻量/开发      |
| PDF 解析   | PyMuPDF (fitz)         | 备选 pdfplumber           |
| 文件存储   | 本地文件系统 或 MinIO  | 图片/附件先上传落盘再URL引用 |

## 运行环境

- **强制性**: LoongArch 架构 + 银河麒麟高级服务器版 V10
- 开发阶段可在 Windows/macOS 上进行，部署时迁移至目标环境

## 目录结构（规划）

```
.
├── backend/                # FastAPI 后端
│   ├── app/
│   │   ├── api/           # API 路由
│   │   ├── core/          # 配置、安全、依赖
│   │   ├── models/        # 数据库模型
│   │   ├── schemas/       # Pydantic 模型
│   │   ├── services/      # 业务逻辑（LLM、检索、知识库）
│   │   └── main.py        # 入口
│   ├── tests/
│   └── requirements.txt
├── frontend/               # Vue 3 前端
│   ├── src/
│   │   ├── views/         # 页面
│   │   ├── components/    # 通用组件（含 ChatPanel.vue 可嵌入对话面板）
│   │   ├── composables/   # 共享逻辑（useChat 对话引擎等）
│   │   ├── api/           # API 调用封装
│   │   ├── router/        # 路由
│   │   └── stores/        # Pinia 状态管理
│   └── package.json
├── docs/                   # 文档
├── requirements.md         # 需求规格说明书
└── CLAUDE.md
```

## 前端架构要点

### useChat Composable（共享对话引擎）
- 封装对话核心逻辑：会话创建、消息发送、流式接收、历史管理、反馈提交
- 与后端 `/api/v1/conversations` 系列接口交互
- 接受 `context` 参数注入背景信息（设备型号、当前步骤、关联知识条目等）
- 各页面通过 `useChat(conversationId)` 绑定独立会话，互不干扰

### ChatPanel.vue（可嵌入对话面板）
- 紧凑型对话面板，接收 `mode`（floating/embedded）和 `context` props
- 三态：悬浮按钮 → 弹出面板 → 全屏展开（跳转 Chat.vue）
- 嵌入场景：首页悬浮AI（携带当前浏览知识条目上下文）、作业指引步骤内嵌AI（携带步骤上下文）
- 与 Chat.vue 全屏对话页共享 useChat，同一会话切换页面后历史不丢失

### AI 对话能力复用原则
- 所有对话场景（全屏对话页、首页悬浮AI、作业指引内嵌AI）共用 useChat + ChatPanel
- 新增对话场景仅需引用 ChatPanel 并传入对应 context，不重复编写对话逻辑

## 文件存储规范

- 图片/附件通过 `/api/v1/files/upload` 先上传落盘（路径：`settings.UPLOAD_DIR`），再在业务接口中引用返回的文件 URL
- 数据库仅存文件相对路径，不存文件本体
- 案例提交前必须先完成文件上传（前端上传→拿URL→提交案例时传URL列表）

## 编码约定

- Python: 遵循 PEP 8，使用 type hints
- Vue: Composition API + `<script setup>` 语法
- 所有 API 端点使用 `/api/v1/` 前缀
- Git 提交信息使用中文，格式: `类型: 简要描述`
- 后端环境通过 `.env` 文件配置，不硬编码密钥
- 所有的代码内容都必须有详细的注释！

## 关键约束

- 系统必须可完整部署在 LoongArch + 麒麟 V10 上
- 优先选择有 LoongArch 兼容性的依赖库
- 大模型调用支持配置切换（DeepSeek / 千问 / 本地模型）
- 用户角色：一线人员、知识管理员、专家，需权限隔离
- 大模型API开发阶段通过 .env 配置，最终发布时支持管理员在后台动态配置
