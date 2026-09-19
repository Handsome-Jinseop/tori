<script setup>
import { computed, ref, watch } from 'vue'
import { employeesApi, shiftsApi } from '../api'
import { useCatalogStore } from '../stores/catalog'
import { useUiStore } from '../stores/ui'
import { formatDateTime, formatDuration } from '../composables/useFormat'
import DateTimeField from './DateTimeField.vue'
import FlagBadges from './FlagBadges.vue'
import Panel from './Panel.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  shiftId: { type: String, default: null }, // null = 추가 모드
  defaultEmployeeId: { type: String, default: '' },
  defaultStoreId: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'saved'])
const catalog = useCatalogStore()
const ui = useUiStore()

const loading = ref(false)
const saving = ref(false)
const shift = ref(null)
const historyOpen = ref(false)
const employees = ref([])
const employeeSearch = ref('')

const form = ref({ employee_id: '', store_id: '', check_in: null, check_out: null, memo: '', reason: '' })

const isAdd = computed(() => !props.shiftId)
const locked = computed(() => shift.value?.locked_payroll_id)

async function load() {
  if (props.shiftId) {
    loading.value = true
    try {
      shift.value = await shiftsApi.get(props.shiftId)
      form.value = {
        employee_id: shift.value.employee_id,
        store_id: shift.value.store_id,
        check_in: shift.value.check_in,
        check_out: shift.value.check_out,
        memo: shift.value.memo || '',
        reason: '',
      }
    } finally {
      loading.value = false
    }
  } else {
    shift.value = null
    form.value = {
      employee_id: props.defaultEmployeeId,
      store_id: props.defaultStoreId || catalog.stores[0]?.id || '',
      check_in: null,
      check_out: null,
      memo: '',
      reason: '',
    }
    if (employees.value.length === 0) {
      employees.value = await employeesApi.list({})
    }
  }
}

watch(() => [props.modelValue, props.shiftId], () => {
  if (props.modelValue) load()
})

const filteredEmployees = computed(() => {
  if (!employeeSearch.value) return employees.value.slice(0, 30)
  return employees.value.filter((e) => e.name.includes(employeeSearch.value)).slice(0, 30)
})

async function save() {
  saving.value = true
  try {
    if (isAdd.value) {
      if (!form.value.employee_id || !form.value.check_in) {
        ui.toast('직원과 출근 시각을 입력해 주세요.')
        return
      }
      await shiftsApi.create({
        employee_id: form.value.employee_id,
        store_id: form.value.store_id,
        check_in: form.value.check_in,
        check_out: form.value.check_out,
        reason: form.value.reason,
      })
      ui.toast('근무 기록을 추가했어요.')
    } else {
      await shiftsApi.update(props.shiftId, {
        store_id: form.value.store_id,
        check_in: form.value.check_in,
        check_out: form.value.check_out,
        memo: form.value.memo,
        reason: form.value.reason,
      })
      ui.toast('저장했어요.')
    }
    emit('update:modelValue', false)
    emit('saved')
  } catch (e) {
    ui.toast(e.message)
  } finally {
    saving.value = false
  }
}

async function remove() {
  const ok = await ui.confirm({
    title: '이 근무 기록을 삭제할까요?',
    message: '삭제한 기록은 목록에서 사라져요.',
    confirmLabel: '삭제',
    danger: true,
  })
  if (!ok) return
  try {
    await shiftsApi.remove(props.shiftId)
    ui.toast('삭제했어요.')
    emit('update:modelValue', false)
    emit('saved')
  } catch (e) {
    ui.toast(e.message)
  }
}
</script>

<template>
  <Panel :model-value="modelValue" @update:model-value="(v) => emit('update:modelValue', v)" :title="isAdd ? '근무 기록 추가' : '근무 기록 수정'">
    <template v-if="!isAdd && locked">
      <div class="card card-pad col gap-8" style="background: var(--warning-bg)">
        <span style="color: var(--warning-fg); font-weight: 700">
          이 근무는 확정된 정산에 포함돼 있어요. 수정하려면 정산을 재오픈해야 해요.
        </span>
        <router-link to="/payroll" class="btn btn-secondary btn-sm" style="align-self: flex-start">정산으로 이동</router-link>
      </div>
    </template>

    <template v-if="isAdd">
      <div class="field">
        <label>직원</label>
        <input class="input" v-model="employeeSearch" placeholder="이름으로 검색" />
        <div class="col gap-4" style="max-height: 160px; overflow-y: auto; margin-top: 4px">
          <button
            v-for="e in filteredEmployees" :key="e.id" class="chip" style="justify-content: flex-start; width: 100%"
            :class="{ active: form.employee_id === e.id }" @click="form.employee_id = e.id"
          >{{ e.name }}</button>
        </div>
      </div>
    </template>
    <template v-else-if="shift">
      <div class="field">
        <label>직원</label>
        <span>{{ shift.employee_name }} · {{ shift.employment_type === 'part_time' ? '알바' : '직원' }}</span>
      </div>
    </template>

    <div class="field">
      <label>근무 매장</label>
      <select class="select" v-model="form.store_id" :disabled="locked">
        <option v-for="s in catalog.stores" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
    </div>

    <DateTimeField label="출근 시각" v-model="form.check_in" />
    <DateTimeField label="퇴근 시각" v-model="form.check_out" allow-empty empty-label="근무 중" />

    <div class="field" v-if="!isAdd">
      <label>메모</label>
      <input class="input" v-model="form.memo" :disabled="locked" />
    </div>

    <div class="field">
      <label>변경 사유</label>
      <input class="input" v-model="form.reason" placeholder="예: 손님 몰려서 늦게 퇴근 처리" :disabled="locked" />
    </div>

    <template v-if="!isAdd && shift">
      <div class="field">
        <label>폰 원본 기록</label>
        <div class="card card-pad col gap-6" style="background: var(--surface-alt)">
          <span class="muted" style="font-size: 13.5px">
            출근 {{ formatDateTime(shift.check_in) }}<template v-if="shift.check_out"> · 퇴근 {{ formatDateTime(shift.check_out) }}</template>
          </span>
          <FlagBadges :flags="shift.flags" :reviewed="shift.reviewed" />
        </div>
      </div>

      <div class="field">
        <button class="btn btn-ghost btn-sm" style="align-self: flex-start" @click="historyOpen = !historyOpen">
          변경 이력 {{ historyOpen ? '접기' : `펼치기 (${shift.history?.length || 0})` }}
        </button>
        <div v-if="historyOpen" class="col gap-8">
          <div v-for="(h, i) in shift.history" :key="i" class="card card-pad" style="font-size: 13px">
            <div class="muted">{{ formatDateTime(h.at) }} · {{ h.reason || '(사유 없음)' }}</div>
          </div>
          <span v-if="!shift.history?.length" class="muted" style="font-size: 13px">변경 이력이 없어요.</span>
        </div>
      </div>

      <button class="btn btn-danger" style="align-self: flex-start" :disabled="locked" @click="remove">삭제</button>
    </template>

    <template #footer>
      <button class="btn btn-secondary" @click="emit('update:modelValue', false)">취소</button>
      <button class="btn btn-primary" :disabled="saving || locked" @click="save">
        {{ isAdd ? '추가' : '저장' }}
      </button>
    </template>
  </Panel>
</template>
