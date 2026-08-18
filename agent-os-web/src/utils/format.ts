// 时间格式化
export function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString('zh-CN')
}

// 相对时间
export function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}小时前`
  return `${Math.floor(hours / 24)}天前`
}

// Cron 转中文
export function cronToChinese(cron: string): string {
  if (!cron) return '-'
  const parts = cron.split(' ')
  // 支持 6 字段 cron（含秒）和 5 字段 cron
  if (parts.length === 6) {
    // 6 字段: 秒 分 时 日 月 周
    const [sec, min, hour, day, month, week] = parts
    if (min === '0' && hour === '2' && day === '*' && month === '*' && week === '*') return '每天 02:00'
    if (min === '40' && hour === '17') return '工作日 17:40'
    if (min === '0' && hour === '9') return '工作日 09:00'
    if (min === '30' && hour === '15') return '工作日 15:30'
    if (min === '0' && hour === '8') return '工作日 08:00'
    return `每天 ${hour}:${min}`
  }
  // 5 字段: 分 时 日 月 周
  const [min, hour, day, month, week] = parts
  if (min === '0' && hour === '2' && day === '*' && month === '*' && week === '*') return '每天 02:00'
  if (min === '40' && hour === '17') return '工作日 17:40'
  if (min === '0' && hour === '9') return '工作日 09:00'
  if (min === '30' && hour === '15') return '工作日 15:30'
  if (min === '0' && hour === '8') return '工作日 08:00'
  return cron
}
