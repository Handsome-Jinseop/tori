export const FLAG_META = {
  clock_skew: { label: '시각 이상', severity: 'warning' },
  duplicate_in: { label: '출근 중복', severity: 'warning' },
  missing_in: { label: '출근 누락', severity: 'warning' },
  auto_checkout: { label: '자동 퇴근', severity: 'caution' },
  manual_out: { label: '퇴근 수기 입력', severity: 'caution' },
  manual_in: { label: '출근 수기 입력', severity: 'caution' },
  manual_pick: { label: '수기 선택', severity: 'caution' },
  temp_employee: { label: '임시 직원', severity: 'info' },
  manual_edit: { label: '관리자 수정', severity: 'info' },
  manual_add: { label: '관리자 추가', severity: 'info' },
}

const SEVERITY_ORDER = { warning: 0, caution: 1, info: 2 }

export function sortFlagsBySeverity(flags) {
  return [...flags].sort(
    (a, b) => (SEVERITY_ORDER[FLAG_META[a]?.severity] ?? 9) - (SEVERITY_ORDER[FLAG_META[b]?.severity] ?? 9)
  )
}
