<script setup>
import { computed, ref, watch } from 'vue'
import { employeeRequestsApi, employeesApi } from '../api'
import { useCatalogStore } from '../stores/catalog'
import { useUiStore } from '../stores/ui'
import { formatDateTime } from '../composables/useFormat'
import Panel from './Panel.vue'
import AmountInput from './AmountInput.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  request: { type: Object, default: null },
  mode: { type: String, default: 'accept' }, // accept | link | reject
})
const emit = defineEmits(['update:modelValue', 'done'])
const catalog = useCatalogStore()
const ui = useUiStore()

const saving = ref(false)
const form = ref(acceptDefaults())
const linkEmployeeId = ref('')
const linkSearch = ref('')
const rejectReason = ref('')
const allEmployees = ref([])

function acceptDefaults() {
  return {
    name: props.request?.name || '',
    employment_type: 'part_time',
    pay_store_id: props.request?.store_id || '',
    work_store_ids: props.request ? [props.request.store_id] : [],
    hire_date: (props.request?.first_shift_at || new Date().toISOString()).slice(0, 10),
    hourly_wage: null,
    monthly_wage: null,
    weekly_holiday_pay: false,
    night_premium: false,
    holiday_premium: false,
    insurance_national_pension: false,
    insurance_health: false,
    insurance_employment: false,
  }
}

watch(
  () => [props.request, props.mode, props.modelValue],
  async () => {
    if (props.modelValue && props.request) {
      form.value = acceptDefaults()
      linkEmployeeId.value = ''
      linkSearch.value = ''
      rejectReason.value = ''
      if (props.mode === 'link' && allEmployees.value.length === 0) {
        allEmployees.value = await employeesApi.list({})
      }
    }
  }
)

const title = computed(() => {
  if (props.mode === 'accept') return '신규 직원 요청 수락'
  if (props.mode === 'link') return '기존 직원에 연결'
  return '신규 직원 요청 거절'
})

const filteredEmployees = computed(() => {
  if (!linkSearch.value) return allEmployees.value.slice(0, 30)
  return allEmployees.value.filter((e) => e.name.includes(linkSearch.value)).slice(0, 30)
})

function toggleWorkStore(id) {
  const set = new Set(form.value.work_store_ids)
  if (set.has(id)) set.delete(id)
  else set.add(id)
  form.value.work_store_ids = [...set]
}

async function submit() {
  saving.value = true
  try {
    if (props.mode === 'accept') {
      await employeeRequestsApi.accept(props.request.id, form.value)
      ui.toast('수락했어요. 직원을 등록했어요.')
    } else if (props.mode === 'link') {
      if (!linkEmployeeId.value) return
      await employeeRequestsApi.link(props.request.id, linkEmployeeId.value)
      ui.toast('기존 직원에 연결했어요.')
    } else {
      await employeeRequestsApi.reject(props.request.id, rejectReason.value)
      ui.toast('거절했어요.')
    }
    emit('update:modelValue', false)
    emit('done')
  } catch (e) {
    ui.toast(e.message)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Panel :model-value="modelValue" @update:model-value="(v) => emit('update:modelValue', v)" :title="title">
    <template v-if="request">
      <div class="card card-pad col gap-4" style="background: var(--surface-alt)">
        <div class="row" style="justify-content: space-between">
          <strong style="font-size: 17px">{{ request.name }}</strong>
          <span class="muted">{{ request.store_name }}</span>
        </div>
        <span class="muted" style="font-size: 13px">요청 시각 {{ formatDateTime(request.created_at) }}</span>
        <span class="muted" style="font-size: 13px">
          쌓인 근무 기록 {{ request.shift_count }}건<template v-if="request.first_shift_at">, 첫 출근 {{ formatDateTime(request.first_shift_at) }}</template>
        </span>
      </div>

      <template v-if="mode === 'accept'">
        <div class="field">
          <label>이름</label>
          <input class="input" v-model="form.name" />
        </div>
        <div class="field">
          <label>구분</label>
          <div class="chip-row">
            <button class="chip" :class="{ active: form.employment_type === 'part_time' }" @click="form.employment_type = 'part_time'">알바</button>
            <button class="chip" :class="{ active: form.employment_type === 'regular' }" @click="form.employment_type = 'regular'">직원</button>
          </div>
        </div>
        <div class="field">
          <label>급여 관리 매장</label>
          <select class="select" v-model="form.pay_store_id">
            <option v-for="s in catalog.stores" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </div>
        <div class="field">
          <label>근무 가능 매장</label>
          <div class="chip-row">
            <button
              v-for="s in catalog.stores" :key="s.id" class="chip"
              :class="{ active: form.work_store_ids.includes(s.id) }" @click="toggleWorkStore(s.id)"
            >{{ s.name }}</button>
          </div>
        </div>
        <div class="field">
          <label>입사일</label>
          <input type="date" class="input" v-model="form.hire_date" />
        </div>
        <div class="field" v-if="form.employment_type === 'part_time'">
          <label>시급 (비우면 최저시급)</label>
          <AmountInput v-model="form.hourly_wage" placeholder="최저시급 적용" />
        </div>
        <div class="field" v-else>
          <label>월급</label>
          <AmountInput v-model="form.monthly_wage" />
        </div>
        <div class="field">
          <label>급여 설정</label>
          <div class="col gap-8">
            <label v-if="form.employment_type === 'part_time'" class="row gap-8"><input type="checkbox" v-model="form.weekly_holiday_pay" /> 주휴수당</label>
            <label v-if="form.employment_type === 'part_time'" class="row gap-8"><input type="checkbox" v-model="form.night_premium" /> 야간 가산</label>
            <label v-if="form.employment_type === 'part_time'" class="row gap-8"><input type="checkbox" v-model="form.holiday_premium" /> 휴일 가산</label>
            <label class="row gap-8"><input type="checkbox" v-model="form.insurance_national_pension" /> 국민연금</label>
            <label class="row gap-8"><input type="checkbox" v-model="form.insurance_health" /> 건강보험</label>
            <label class="row gap-8"><input type="checkbox" v-model="form.insurance_employment" /> 고용보험</label>
          </div>
        </div>
        <p class="hint">수락하면 이 직원의 얼굴 등록도 함께 승인되고, 쌓인 근무 기록이 이 직원 것으로 옮겨져요.</p>
      </template>

      <template v-else-if="mode === 'link'">
        <div class="field">
          <label>기존 직원 검색</label>
          <input class="input" v-model="linkSearch" placeholder="이름으로 검색" />
        </div>
        <div class="col gap-4" style="max-height: 280px; overflow-y: auto">
          <button
            v-for="e in filteredEmployees" :key="e.id" class="chip" style="justify-content: flex-start; width: 100%"
            :class="{ active: linkEmployeeId === e.id }" @click="linkEmployeeId = e.id"
          >{{ e.name }} <span class="muted" style="margin-left: auto">{{ e.employment_type === 'part_time' ? '알바' : '직원' }}</span></button>
        </div>
        <p class="hint">이름을 잘못 적었거나 이미 있는 직원이에요. 쌓인 근무 기록과 얼굴 정보가 선택한 직원에게 합쳐져요.</p>
      </template>

      <template v-else>
        <div class="field">
          <label>사유 (선택)</label>
          <input class="input" v-model="rejectReason" />
        </div>
        <p class="hint">거절하면 쌓인 임시 근무 기록이 삭제되고, 폰에 저장된 이름과 얼굴 정보도 지워져요.</p>
      </template>
    </template>

    <template #footer>
      <button class="btn btn-secondary" @click="emit('update:modelValue', false)">취소</button>
      <button
        class="btn" :class="mode === 'reject' ? 'btn-danger' : 'btn-primary'"
        :disabled="saving || (mode === 'link' && !linkEmployeeId)"
        @click="submit"
      >
        {{ mode === 'accept' ? '수락하고 등록' : mode === 'link' ? '연결' : '거절' }}
      </button>
    </template>
  </Panel>
</template>
