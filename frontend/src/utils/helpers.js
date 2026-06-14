/** 格式化日期时间字符串：去除 T，截取到分钟 */
export function formatDateTime(s) {
  if (!s) return ''
  return s.slice(0, 16).replace('T', ' ')
}

/** 格式化日期字符串：截取到日 */
export function formatDate(s) {
  if (!s) return ''
  return s.slice(0, 10)
}

/** 通用搜索过滤 */
export function filterBySearch(items, searchText, fieldFn) {
  if (!searchText) return items
  const kw = searchText.toLowerCase()
  return items.filter(item => {
    const val = typeof fieldFn === 'function' ? fieldFn(item) : item[fieldFn]
    return String(val || '').toLowerCase().includes(kw)
  })
}
