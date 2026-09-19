const KST_TZ = 'Asia/Seoul'

function toDate(value) {
  if (!value) return null
  return value instanceof Date ? value : new Date(value)
}

export function formatMoney(amount) {
  if (amount === null || amount === undefined) return '-'
  return `${Math.round(amount).toLocaleString('ko-KR')}원`
}

export function formatSignedMoney(amount, kind) {
  const sign = kind === 'deduction' ? '−' : '+'
  return `${sign}${Math.abs(Math.round(amount)).toLocaleString('ko-KR')}원`
}

export function formatTime(value) {
  const d = toDate(value)
  if (!d) return '-'
  return new Intl.DateTimeFormat('ko-KR', {
    timeZone: KST_TZ,
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(d)
}

const WEEKDAY_SHORT_TO_KO = { Sun: '일', Mon: '월', Tue: '화', Wed: '수', Thu: '목', Fri: '금', Sat: '토' }

export function formatDate(value) {
  const d = toDate(value)
  if (!d) return '-'
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: KST_TZ,
    month: 'long',
    day: 'numeric',
    weekday: 'short',
  }).formatToParts(d)
  const monthName = new Intl.DateTimeFormat('ko-KR', { timeZone: KST_TZ, month: 'long' }).format(d)
  const day = parts.find((p) => p.type === 'day')?.value ?? ''
  const weekdayShort = parts.find((p) => p.type === 'weekday')?.value ?? ''
  return `${monthName} ${day} (${WEEKDAY_SHORT_TO_KO[weekdayShort] ?? ''})`
}

export function formatDateTime(value) {
  const d = toDate(value)
  if (!d) return '-'
  return `${formatDate(d)} ${formatTime(d)}`
}

export function formatDuration(minutes) {
  if (minutes === null || minutes === undefined) return '-'
  const h = Math.floor(minutes / 60)
  const m = Math.round(minutes % 60)
  if (h <= 0) return `${m}분`
  if (m === 0) return `${h}시간`
  return `${h}시간 ${m}분`
}

export function relativeFromNow(value) {
  const d = toDate(value)
  if (!d) return '-'
  const diffMin = Math.round((Date.now() - d.getTime()) / 60000)
  if (diffMin < 1) return '방금 전'
  if (diffMin < 60) return `${diffMin}분 전`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24) return `${diffH}시간 전`
  return formatDate(d)
}

export function todayKstIso() {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: KST_TZ }).formatToParts(new Date())
  const y = parts.find((p) => p.type === 'year').value
  const m = parts.find((p) => p.type === 'month').value
  const d = parts.find((p) => p.type === 'day').value
  return `${y}-${m}-${d}`
}
