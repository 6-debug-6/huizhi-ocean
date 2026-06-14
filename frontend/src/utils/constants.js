/** 工单状态标签 */
export const TICKET_STATUS = {
  pending:    { label: '待处理', tag: 'danger' },
  processing: { label: '处理中', tag: 'warning' },
  replied:    { label: '已回复', tag: '' },
  resolved:   { label: '已解决', tag: 'success' },
  closed:     { label: '已关闭', tag: 'info' },
}

/** 任务状态标签 */
export const TASK_STATUS = {
  in_progress: { label: '进行中', tag: '',        progressStatus: '' },
  paused:      { label: '已暂停', tag: 'warning',  progressStatus: 'warning' },
  completed:   { label: '已完成', tag: 'success',  progressStatus: 'success' },
}

/** 审核状态标签 */
export const REVIEW_STATUS = {
  pending_initial: { label: '待初审', tag: 'warning' },
  pending_expert:  { label: '待复审', tag: 'warning' },
  approved:        { label: '已通过', tag: 'success' },
  rejected:        { label: '已驳回', tag: 'danger' },
}

/** 用户状态标签 */
export const USER_STATUS = {
  pending:  { label: '待审核', tag: 'warning' },
  active:   { label: '正常',   tag: 'success' },
  disabled: { label: '已禁用', tag: 'danger' },
}

/** 角色名映射 */
export const ROLE_LABELS = { worker: '一线', admin: '管理员', expert: '专家' }

/** 知识来源映射 */
export const SOURCE_LABELS = { manual: '手动', pdf_import: 'PDF导入', user_upload: '用户上传', ticket: '工单转化' }

/** 知识状态映射 */
export const KNOWLEDGE_STATUS = { published: '已发布', draft: '草稿', archived: '已归档' }
