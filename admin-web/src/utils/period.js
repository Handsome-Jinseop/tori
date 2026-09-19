function pad(n) {
  return String(n).padStart(2, '0')
}

function toIso(y, m, d) {
  return `${y}-${pad(m)}-${pad(d)}`
}

function daysInMonth(y, m) {
  return new Date(y, m, 0).getDate()
}

// start_day 기준으로 refDate(Date)가 속한 정산 기간의 { start, end } (ISO 문자열)를 반환.
export function periodBounds(refDate, startDay = 1) {
  const clampedStartDay = Math.max(1, Math.min(startDay, 28))
  const y = refDate.getFullYear()
  const m = refDate.getMonth() + 1
  const day = refDate.getDate()

  let sy = y
  let sm = m
  if (day < clampedStartDay) {
    sm -= 1
    if (sm === 0) {
      sm = 12
      sy -= 1
    }
  }
  let ey = sy
  let em = sm + 1
  if (em === 13) {
    em = 1
    ey += 1
  }
  const endDay = clampedStartDay === 1 ? daysInMonth(ey, em) : Math.min(clampedStartDay - 1, daysInMonth(ey, em))
  return { start: toIso(sy, sm, clampedStartDay), end: toIso(ey, em, endDay) }
}

export function shiftPeriod(refDate, startDay, monthDelta) {
  const shifted = new Date(refDate)
  shifted.setMonth(shifted.getMonth() + monthDelta)
  return periodBounds(shifted, startDay)
}

export function periodLabel(start, end) {
  return `${start}~${end}`
}
