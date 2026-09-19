<script setup>
import { startRegistration } from '@simplewebauthn/browser'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { auditLogsApi, authApi, holidaysApi, ratesApi, settingsApi } from '../api'
import AmountInput from '../components/AmountInput.vue'
import EmptyState from '../components/EmptyState.vue'
import Panel from '../components/Panel.vue'
import { formatDateTime } from '../composables/useFormat'
import { useAuthStore } from '../stores/auth'
import { useCatalogStore } from '../stores/catalog'
import { useUiStore } from '../stores/ui'

const catalog = useCatalogStore()
const auth = useAuthStore()
const ui = useUiStore()
const router = useRouter()

const TABS = [
  { key: 'min-wage', label: '최저시급' },
  { key: 'insurance', label: '4대보험 요율' },
  { key: 'holidays', label: '휴일 달력' },
  { key: 'rules', label: '급여 규칙' },
  { key: 'app', label: '폰 앱' },
  { key: 'account', label: '관리자 계정' },
  { key: 'audit', label: '감사 로그' },
]
const tab = ref('min-wage')

// 최저시급
const minWages = ref([])
const minWagePanel = ref(false)
const minWageForm = ref({ effective_from: '', hourly_wage: null })
async function loadMinWages() {
  minWages.value = await ratesApi.minWages()
}
async function saveMinWage() {
  await ratesApi.addMinWage(minWageForm.value)
  minWagePanel.value = false
  ui.toast('저장했어요.')
  await loadMinWages()
}

// 4대보험
const insuranceRates = ref([])
const insurancePanel = ref(false)
const insuranceForm = ref({ effective_from: '', national_pension: 0.045, health_insurance: 0.0709, long_term_care: 0.1281, employment_insurance: 0.009 })
async function loadInsurance() {
  insuranceRates.value = await ratesApi.insuranceRates()
}
async function saveInsurance() {
  await ratesApi.addInsuranceRate(insuranceForm.value)
  insurancePanel.value = false
  ui.toast('저장했어요.')
  await loadInsurance()
}

// 휴일 달력
const calMonth = ref(new Date())
const holidays = ref([])
async function loadHolidays() {
  holidays.value = await holidaysApi.list(calMonth.value.getFullYear())
}
const calDays = computed(() => {
  const y = calMonth.value.getFullYear()
  const m = calMonth.value.getMonth()
  const first = new Date(y, m, 1)
  const startOffset = first.getDay()
  const daysInMonth = new Date(y, m + 1, 0).getDate()
  const cells = []
  for (let i = 0; i < startOffset; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) {
    const iso = `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    cells.push({ day: d, iso, holiday: holidays.value.find((h) => h.date === iso) })
  }
  return cells
})
function shiftMonth(delta) {
  calMonth.value = new Date(calMonth.value.getFullYear(), calMonth.value.getMonth() + delta, 1)
  loadHolidays()
}
async function onDayClick(cell) {
  if (!cell) return
  if (cell.holiday) {
    const ok = await ui.confirm({ title: '휴일 지정을 해제할까요?', message: cell.holiday.name, confirmLabel: '해제' })
    if (!ok) return
    await holidaysApi.remove(cell.iso)
  } else {
    const name = prompt('휴일 이름을 입력해 주세요.')
    if (!name) return
    await holidaysApi.upsert({ date: cell.iso, name })
  }
  await loadHolidays()
}

// 급여 규칙 / 폰 앱
const settingsForm = ref(null)
async function loadSettings() {
  settingsForm.value = await settingsApi.get()
}
async function saveSettings() {
  settingsForm.value = await settingsApi.update(settingsForm.value)
  await catalog.refreshSettings()
  ui.toast('저장했어요.')
}

// 관리자 계정
async function addPasskey() {
  try {
    const { options } = await authApi.registerOptions()
    const credential = await startRegistration({ optionsJSON: options })
    await authApi.registerVerify(credential, '새 기기')
    ui.toast('패스키를 추가했어요.')
    await auth.refreshMe()
  } catch {
    ui.toast('추가하지 못했어요.')
  }
}
async function removePasskey(id) {
  await authApi.deletePasskey(id)
  await auth.refreshMe()
  ui.toast('삭제했어요.')
}
const newRecoveryCodes = ref(null)
async function regenerateRecovery() {
  const res = await authApi.recoveryRegenerate()
  newRecoveryCodes.value = res.recovery_codes
}
async function logout() {
  await auth.logout()
  router.push('/login')
}

// 감사 로그
const auditLogs = ref([])
const auditFilter = ref({ date_from: '', date_to: '', target_type: '' })
const expandedLog = ref(null)
async function loadAudit() {
  auditLogs.value = await auditLogsApi.list(auditFilter.value)
}

onMounted(async () => {
  await catalog.load()
  await Promise.all([loadMinWages(), loadInsurance(), loadHolidays(), loadSettings(), loadAudit()])
})
</script>

<template>
  <div class="col gap-20">
    <h1 class="display" style="font-size: 26px">설정</h1>

    <div class="chip-row scrollbar-thin" style="overflow-x: auto; flex-wrap: nowrap">
      <button v-for="t in TABS" :key="t.key" class="chip" :class="{ active: tab === t.key }" @click="tab = t.key">{{ t.label }}</button>
    </div>

    <div v-if="tab === 'min-wage'" class="col gap-12">
      <button class="btn btn-primary" style="align-self: flex-start" @click="minWageForm = { effective_from: '', hourly_wage: null }; minWagePanel = true">추가</button>
      <table class="data-table card"><thead><tr><th>적용 시작일</th><th class="text-right">시급</th></tr></thead>
        <tbody><tr v-for="m in minWages" :key="m.id"><td>{{ m.effective_from }}</td><td class="text-right numeric">{{ m.hourly_wage.toLocaleString('ko-KR') }}원</td></tr></tbody>
      </table>
    </div>

    <div v-else-if="tab === 'insurance'" class="col gap-12">
      <button class="btn btn-primary" style="align-self: flex-start" @click="insurancePanel = true">추가</button>
      <table class="data-table card">
        <thead><tr><th>적용 시작일</th><th class="text-right">국민연금</th><th class="text-right">건강보험</th><th class="text-right">장기요양</th><th class="text-right">고용보험</th></tr></thead>
        <tbody>
          <tr v-for="r in insuranceRates" :key="r.id">
            <td>{{ r.effective_from }}</td>
            <td class="text-right numeric">{{ (r.national_pension * 100).toFixed(2) }}%</td>
            <td class="text-right numeric">{{ (r.health_insurance * 100).toFixed(2) }}%</td>
            <td class="text-right numeric">{{ (r.long_term_care * 100).toFixed(2) }}%</td>
            <td class="text-right numeric">{{ (r.employment_insurance * 100).toFixed(2) }}%</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else-if="tab === 'holidays'" class="row gap-16" style="align-items: flex-start; flex-wrap: wrap">
      <div class="card card-pad col gap-10" style="flex: 1; min-width: 280px">
        <div class="row" style="justify-content: space-between">
          <button class="btn btn-ghost btn-sm" @click="shiftMonth(-1)">‹ 이전</button>
          <strong>{{ calMonth.getFullYear() }}년 {{ calMonth.getMonth() + 1 }}월</strong>
          <button class="btn btn-ghost btn-sm" @click="shiftMonth(1)">다음 ›</button>
        </div>
        <div class="cal-grid">
          <span v-for="w in ['일', '월', '화', '수', '목', '금', '토']" :key="w" class="muted cal-cell" style="font-size: 12px">{{ w }}</span>
          <div v-for="(c, i) in calDays" :key="i" class="cal-cell cal-day" :class="{ holiday: c?.holiday, empty: !c }" @click="onDayClick(c)">
            <span v-if="c">{{ c.day }}</span>
            <span v-if="c?.holiday" class="cal-holiday-name">{{ c.holiday.name }}</span>
          </div>
        </div>
      </div>
      <div class="card card-pad col gap-8" style="flex: none; min-width: 200px">
        <strong>{{ calMonth.getFullYear() }}년 휴일</strong>
        <div v-for="h in holidays" :key="h.date" class="row" style="justify-content: space-between; font-size: 13.5px">
          <span>{{ h.date }}</span><span>{{ h.name }}</span>
        </div>
        <EmptyState v-if="!holidays.length" message="등록된 휴일이 없어요." />
      </div>
    </div>

    <div v-else-if="tab === 'rules' && settingsForm" class="card card-pad col gap-16" style="max-width: 420px">
      <div class="field"><label>야간 가산율</label><input type="number" step="0.05" class="input" v-model.number="settingsForm.night_premium_rate" /></div>
      <div class="field"><label>휴일 가산율</label><input type="number" step="0.05" class="input" v-model.number="settingsForm.holiday_premium_rate" /></div>
      <div class="field">
        <label>기본 정산 시작일</label>
        <input type="number" min="1" max="28" class="input" v-model.number="settingsForm.default_period_start_day" />
        <span class="hint">바꾸면 이후 정산의 기본 기간이 달라져요</span>
      </div>
      <button class="btn btn-primary" style="align-self: flex-start" @click="saveSettings">저장</button>
    </div>

    <div v-else-if="tab === 'app' && settingsForm" class="card card-pad col gap-16" style="max-width: 420px">
      <div class="field">
        <label>얼굴 인식 기준값</label>
        <input type="number" step="0.01" min="0" max="1" class="input" v-model.number="settingsForm.face_match_threshold" />
        <span class="hint">바꾸면 모든 매장 폰이 다음 동기화 때 적용해요</span>
      </div>
      <label class="row gap-8"><input type="checkbox" v-model="settingsForm.allow_manual_pick" /> 수기 등록 허용</label>
      <label class="row gap-8"><input type="checkbox" v-model="settingsForm.allow_pre_approval_clock" /> 승인 전 출퇴근 허용</label>
      <button class="btn btn-primary" style="align-self: flex-start" @click="saveSettings">저장</button>
    </div>

    <div v-else-if="tab === 'account'" class="col gap-16" style="max-width: 480px">
      <div class="card card-pad col gap-6">
        <strong>{{ auth.admin?.display_name }}</strong>
        <span class="muted">역할: owner</span>
      </div>
      <div class="col gap-8">
        <strong>등록된 패스키</strong>
        <div v-for="pk in auth.admin?.passkeys || []" :key="pk.credential_id" class="card card-pad row" style="justify-content: space-between">
          <div class="col gap-2">
            <span>{{ pk.device_name }}</span>
            <span class="muted" style="font-size: 12px">{{ formatDateTime(pk.created_at) }} 등록</span>
          </div>
          <button class="btn btn-ghost btn-sm" @click="removePasskey(pk.credential_id)">삭제</button>
        </div>
        <button class="btn btn-secondary" style="align-self: flex-start" @click="addPasskey">패스키 추가</button>
      </div>
      <div class="col gap-8">
        <button class="btn btn-secondary" style="align-self: flex-start" @click="regenerateRecovery">새 복구 코드 발급</button>
        <div v-if="newRecoveryCodes" class="card card-pad col gap-8" style="background: var(--surface-alt)">
          <span class="muted" style="font-size: 13px">지금 한 번만 보여드려요. 안전한 곳에 저장해 주세요.</span>
          <div class="recovery-grid">
            <span v-for="c in newRecoveryCodes" :key="c" class="numeric">{{ c }}</span>
          </div>
          <button class="btn btn-secondary btn-sm" style="align-self: flex-start" @click="navigator.clipboard?.writeText(newRecoveryCodes.join('\n')); ui.toast('복사했어요.')">복사</button>
        </div>
      </div>
      <button class="btn btn-danger" style="align-self: flex-start" @click="logout">로그아웃</button>
    </div>

    <div v-else-if="tab === 'audit'" class="col gap-14">
      <div class="card card-pad row gap-12" style="flex-wrap: wrap">
        <input type="date" class="input" style="max-width: 170px" v-model="auditFilter.date_from" @change="loadAudit" />
        <input type="date" class="input" style="max-width: 170px" v-model="auditFilter.date_to" @change="loadAudit" />
        <select class="select" style="max-width: 180px" v-model="auditFilter.target_type" @change="loadAudit">
          <option value="">대상 전체</option>
          <option value="shift">근무 기록</option>
          <option value="employee">직원</option>
          <option value="payroll">정산</option>
          <option value="pay_item">보너스·공제</option>
          <option value="store">매장</option>
          <option value="device">기기</option>
        </select>
      </div>
      <EmptyState v-if="!auditLogs.length" message="기록이 없어요." />
      <div v-for="log in auditLogs" :key="log.id" class="card card-pad" @click="expandedLog = expandedLog === log.id ? null : log.id">
        <div class="row" style="justify-content: space-between">
          <span>{{ log.summary }}</span>
          <span class="muted numeric" style="font-size: 12.5px">{{ formatDateTime(log.created_at) }}</span>
        </div>
        <div v-if="expandedLog === log.id" class="col gap-6" style="margin-top: 10px; font-size: 12.5px">
          <pre class="muted" style="white-space: pre-wrap; margin: 0">이전: {{ JSON.stringify(log.before) }}</pre>
          <pre class="muted" style="white-space: pre-wrap; margin: 0">이후: {{ JSON.stringify(log.after) }}</pre>
        </div>
      </div>
    </div>

    <Panel v-model="minWagePanel" title="최저시급 추가">
      <div class="field"><label>적용 시작일</label><input type="date" class="input" v-model="minWageForm.effective_from" /></div>
      <div class="field"><label>시급</label><AmountInput v-model="minWageForm.hourly_wage" /></div>
      <template #footer>
        <button class="btn btn-secondary" @click="minWagePanel = false">취소</button>
        <button class="btn btn-primary" @click="saveMinWage">추가</button>
      </template>
    </Panel>

    <Panel v-model="insurancePanel" title="4대보험 요율 추가">
      <div class="field"><label>적용 시작일</label><input type="date" class="input" v-model="insuranceForm.effective_from" /></div>
      <div class="field"><label>국민연금 (%)</label><input type="number" step="0.001" class="input" v-model.number="insuranceForm.national_pension" /></div>
      <div class="field"><label>건강보험 (%)</label><input type="number" step="0.001" class="input" v-model.number="insuranceForm.health_insurance" /></div>
      <div class="field"><label>장기요양 (건강보험료 대비 %)</label><input type="number" step="0.001" class="input" v-model.number="insuranceForm.long_term_care" /></div>
      <div class="field"><label>고용보험 (%)</label><input type="number" step="0.001" class="input" v-model.number="insuranceForm.employment_insurance" /></div>
      <template #footer>
        <button class="btn btn-secondary" @click="insurancePanel = false">취소</button>
        <button class="btn btn-primary" @click="saveInsurance">추가</button>
      </template>
    </Panel>
  </div>
</template>

<style scoped>
.cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
.cal-cell { text-align: center; padding: 6px 2px; }
.cal-day { border-radius: var(--radius-sm); cursor: pointer; min-height: 48px; display: flex; flex-direction: column; align-items: center; gap: 2px; font-size: 13px; }
.cal-day:not(.empty):hover { background: var(--surface-alt); }
.cal-day.holiday { background: var(--warning-bg); color: var(--warning-fg); font-weight: 700; }
.cal-holiday-name { font-size: 10px; }
.recovery-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
</style>
