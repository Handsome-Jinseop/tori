<script setup>
import { computed, ref, watch } from 'vue'
import { employeesApi, enrollmentsApi } from '../api'
import { formatDate, formatDateTime, formatMoney } from '../composables/useFormat'
import { useCatalogStore } from '../stores/catalog'
import { useUiStore } from '../stores/ui'
import EmptyState from './EmptyState.vue'
import Panel from './Panel.vue'
import PayRateDialog from './PayRateDialog.vue'
import TransferDialog from './TransferDialog.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  employeeId: { type: String, default: null },
})
const emit = defineEmits(['update:modelValue', 'changed'])
const catalog = useCatalogStore()
const ui = useUiStore()

const employee = ref(null)
const payRates = ref([])
const assignments = ref([])
const tab = ref('basic')
const basicForm = ref({ name: '', work_store_ids: [], face_exempt: false })
const payRateDialogOpen = ref(false)
const transferDialogOpen = ref(false)

async function load() {
  if (!props.employeeId) return
  employee.value = await employeesApi.get(props.employeeId)
  basicForm.value = {
    name: employee.value.name,
    work_store_ids: [...employee.value.work_store_ids],
    face_exempt: employee.value.face_exempt,
  }
  payRates.value = await employeesApi.payRates(props.employeeId)
  assignments.value = await employeesApi.assignments(props.employeeId)
}

watch(() => [props.modelValue, props.employeeId], () => {
  if (props.modelValue) {
    tab.value = 'basic'
    load()
  }
})

const isPartTime = computed(() => employee.value?.employment_type === 'part_time')

function toggleWorkStore(id) {
  const set = new Set(basicForm.value.work_store_ids)
  if (set.has(id)) set.delete(id)
  else set.add(id)
  basicForm.value.work_store_ids = [...set]
}

async function saveBasic() {
  await employeesApi.update(props.employeeId, basicForm.value)
  ui.toast('저장했어요.')
  await load()
  emit('changed')
}

async function resign() {
  const ok = await ui.confirm({
    title: '퇴사 처리할까요?',
    message: '퇴사 처리하면 매장 폰에서 이 직원의 얼굴 데이터가 삭제돼요.',
    confirmLabel: '퇴사 처리',
    danger: true,
  })
  if (!ok) return
  await employeesApi.resign(props.employeeId)
  ui.toast('퇴사 처리했어요.')
  await load()
  emit('changed')
}

async function approveFace(enrollmentId) {
  await enrollmentsApi.approve(enrollmentId)
  ui.toast('승인했어요.')
  await load()
}
async function revokeFace(enrollmentId) {
  const ok = await ui.confirm({
    title: '얼굴 등록을 해제할까요?',
    message: '해제하면 폰이 다음 동기화 때 이 직원의 얼굴 데이터를 삭제해요.',
    confirmLabel: '해제',
    danger: true,
  })
  if (!ok) return
  await enrollmentsApi.revoke(enrollmentId)
  ui.toast('해제했어요.')
  await load()
}

async function cancelAssignment(id) {
  await employeesApi.cancelAssignment(props.employeeId, id)
  ui.toast('예약을 취소했어요.')
  await load()
}

const FACE_STATUS_LABEL = { pending: '승인 대기', approved: '승인됨', revoked: '해제됨' }
</script>

<template>
  <Panel :model-value="modelValue" @update:model-value="(v) => emit('update:modelValue', v)" :title="employee?.name || '직원'" wide>
    <template v-if="employee">
      <div class="chip-row">
        <button class="chip" :class="{ active: tab === 'basic' }" @click="tab = 'basic'">기본 정보</button>
        <button class="chip" :class="{ active: tab === 'pay' }" @click="tab = 'pay'">급여 설정</button>
        <button class="chip" :class="{ active: tab === 'face' }" @click="tab = 'face'">얼굴 등록</button>
        <button class="chip" :class="{ active: tab === 'history' }" @click="tab = 'history'">이동 이력</button>
      </div>

      <div v-if="tab === 'basic'" class="col gap-16">
        <div class="field">
          <label>이름</label>
          <input class="input" v-model="basicForm.name" />
        </div>
        <div class="field">
          <label>구분</label>
          <span>{{ isPartTime ? '알바' : '직원' }}</span>
        </div>
        <div class="field">
          <label>급여 관리 매장</label>
          <div class="row gap-8">
            <span>{{ catalog.storeName(employee.pay_store_id) }}</span>
            <button class="btn btn-secondary btn-sm" @click="transferDialogOpen = true">이동</button>
          </div>
        </div>
        <div class="field">
          <label>근무 가능 매장</label>
          <div class="chip-row">
            <button v-for="s in catalog.stores" :key="s.id" class="chip" :class="{ active: basicForm.work_store_ids.includes(s.id) }" @click="toggleWorkStore(s.id)">
              {{ s.name }}
            </button>
          </div>
        </div>
        <div class="field"><label>입사일</label><span>{{ formatDate(employee.hire_date) }}</span></div>
        <div class="field"><label>재직 상태</label><span>{{ employee.active ? '재직' : '퇴사' }}</span></div>
        <label class="row gap-8">
          <input type="checkbox" v-model="basicForm.face_exempt" />
          얼굴 등록 면제 (얼굴 등록을 원치 않는 직원은 수기 등록 목록에 항상 포함돼요)
        </label>
        <button class="btn btn-primary" style="align-self: flex-start" @click="saveBasic">저장</button>

        <div class="card card-pad col gap-10" style="background: var(--warning-bg); margin-top: 12px" v-if="employee.active">
          <strong style="color: var(--warning-fg)">위험 영역</strong>
          <button class="btn btn-danger" style="align-self: flex-start" @click="resign">퇴사 처리</button>
        </div>
      </div>

      <div v-else-if="tab === 'pay'" class="col gap-16">
        <div class="card card-pad col gap-8">
          <div class="row" style="justify-content: space-between">
            <strong>{{ employee.current_pay_rate ? (isPartTime ? formatMoney(employee.current_pay_rate.hourly_wage) + ' (시급)' : formatMoney(employee.current_pay_rate.monthly_wage) + ' (월급)') : '-' }}</strong>
            <button class="btn btn-secondary btn-sm" @click="payRateDialogOpen = true">급여 설정 변경</button>
          </div>
          <div class="chip-row" v-if="employee.current_pay_rate">
            <span v-if="isPartTime && employee.current_pay_rate.weekly_holiday_pay" class="chip">주휴수당</span>
            <span v-if="isPartTime && employee.current_pay_rate.night_premium" class="chip">야간 가산</span>
            <span v-if="isPartTime && employee.current_pay_rate.holiday_premium" class="chip">휴일 가산</span>
            <span v-if="employee.current_pay_rate.insurance_national_pension" class="chip">국민연금</span>
            <span v-if="employee.current_pay_rate.insurance_health" class="chip">건강보험</span>
            <span v-if="employee.current_pay_rate.insurance_employment" class="chip">고용보험</span>
          </div>
          <p v-if="employee.upcoming_pay_rate" class="hint">{{ employee.upcoming_pay_rate.effective_from }}부터 적용 예정</p>
        </div>

        <table class="data-table card">
          <thead><tr><th>적용 시작일</th><th>시급/월급</th><th>설정</th></tr></thead>
          <tbody>
            <tr v-for="r in payRates" :key="r.id">
              <td>{{ r.effective_from }}</td>
              <td class="numeric">{{ isPartTime ? formatMoney(r.hourly_wage) : formatMoney(r.monthly_wage) }}</td>
              <td class="muted" style="font-size: 12.5px">
                {{ [r.weekly_holiday_pay && '주휴', r.night_premium && '야간', r.holiday_premium && '휴일', r.insurance_national_pension && '국민연금', r.insurance_health && '건강', r.insurance_employment && '고용'].filter(Boolean).join(', ') || '-' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else-if="tab === 'face'" class="col gap-8">
        <table class="data-table card">
          <thead><tr><th>매장</th><th>상태</th><th>요청·승인 시각</th><th></th></tr></thead>
          <tbody>
            <tr v-for="f in employee.face_enrollments" :key="f.id">
              <td>{{ f.store_name }}</td>
              <td>{{ FACE_STATUS_LABEL[f.status] }}</td>
              <td class="muted" style="font-size: 12.5px">{{ formatDateTime(f.status === 'approved' ? f.approved_at : f.requested_at) }}</td>
              <td>
                <button v-if="f.status === 'pending'" class="btn btn-primary btn-sm" @click="approveFace(f.id)">승인</button>
                <button v-if="f.status === 'approved'" class="btn btn-ghost btn-sm" @click="revokeFace(f.id)">해제</button>
              </td>
            </tr>
          </tbody>
        </table>
        <EmptyState v-if="!employee.face_enrollments?.length" message="얼굴 등록 기록이 없어요." />
      </div>

      <div v-else class="col gap-8">
        <table class="data-table card">
          <thead><tr><th>적용 시작일</th><th>급여 관리 매장</th><th>사유</th><th></th></tr></thead>
          <tbody>
            <tr v-for="a in assignments" :key="a.id">
              <td>{{ a.effective_from }} <span v-if="!a.applied" class="chip" style="height: 22px; padding: 0 8px; font-size: 11.5px">예정</span></td>
              <td>{{ catalog.storeName(a.pay_store_id) }}</td>
              <td class="muted" style="font-size: 13px">{{ a.reason }}</td>
              <td><button v-if="!a.applied" class="btn btn-ghost btn-sm" @click="cancelAssignment(a.id)">예약 취소</button></td>
            </tr>
          </tbody>
        </table>
        <EmptyState v-if="!assignments.length" message="이동 이력이 없어요." />
      </div>
    </template>

    <PayRateDialog v-model="payRateDialogOpen" :employee="employee" :current-rate="employee?.current_pay_rate" @saved="load" />
    <TransferDialog v-model="transferDialogOpen" :employee="employee" @saved="load" />
  </Panel>
</template>
