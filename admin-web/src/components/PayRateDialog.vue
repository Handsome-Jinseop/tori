<script setup>
import { computed, ref, watch } from 'vue'
import { employeesApi, ratesApi } from '../api'
import { ApiError } from '../api/client'
import { formatMoney } from '../composables/useFormat'
import { periodBounds, shiftPeriod } from '../utils/period'
import { useCatalogStore } from '../stores/catalog'
import { useUiStore } from '../stores/ui'
import AmountInput from './AmountInput.vue'
import Panel from './Panel.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  employee: { type: Object, default: null },
  currentRate: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'saved'])
const catalog = useCatalogStore()
const ui = useUiStore()

const form = ref(defaults())
const applyFrom = ref('next')
const confirmBelowMinWage = ref(false)
const minWageWarning = ref(null)
const preview = ref(null)
const saving = ref(false)
const minWage = ref(null)

function defaults() {
  return {
    hourly_wage: props.currentRate?.hourly_wage ?? null,
    monthly_wage: props.currentRate?.monthly_wage ?? null,
    weekly_holiday_pay: props.currentRate?.weekly_holiday_pay ?? false,
    night_premium: props.currentRate?.night_premium ?? false,
    holiday_premium: props.currentRate?.holiday_premium ?? false,
    insurance_national_pension: props.currentRate?.insurance_national_pension ?? false,
    insurance_health: props.currentRate?.insurance_health ?? false,
    insurance_employment: props.currentRate?.insurance_employment ?? false,
  }
}

const thisPeriod = computed(() => periodBounds(new Date(), catalog.startDay))
const nextPeriod = computed(() => shiftPeriod(new Date(), catalog.startDay, 1))
const isPartTime = computed(() => props.employee?.employment_type === 'part_time')

watch(
  () => [props.modelValue, props.employee],
  async () => {
    if (props.modelValue) {
      form.value = defaults()
      applyFrom.value = 'next'
      confirmBelowMinWage.value = false
      minWageWarning.value = null
      preview.value = null
      const wages = await ratesApi.minWages()
      minWage.value = wages[0]?.hourly_wage ?? null
    }
  }
)

watch(
  () => form.value.hourly_wage,
  async (v) => {
    minWageWarning.value = v !== null && minWage.value !== null && v < minWage.value
    confirmBelowMinWage.value = false
    if (v !== null && applyFrom.value === 'this' && props.employee) {
      preview.value = await employeesApi.previewPayRate(props.employee.id, v)
    } else {
      preview.value = null
    }
  }
)

watch(applyFrom, async (v) => {
  if (v === 'this' && form.value.hourly_wage !== null && props.employee) {
    preview.value = await employeesApi.previewPayRate(props.employee.id, form.value.hourly_wage)
  } else {
    preview.value = null
  }
})

async function save() {
  saving.value = true
  try {
    await employeesApi.changePayRate(props.employee.id, {
      ...form.value,
      apply_from: applyFrom.value,
      confirm_below_min_wage: confirmBelowMinWage.value,
    })
    ui.toast('저장했어요.')
    emit('update:modelValue', false)
    emit('saved')
  } catch (e) {
    if (e instanceof ApiError && e.payload?.detail?.code === 'below_min_wage') {
      minWageWarning.value = true
    } else {
      ui.toast(e.message)
    }
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Panel :model-value="modelValue" @update:model-value="(v) => emit('update:modelValue', v)" title="급여 설정 변경">
    <template v-if="employee">
      <p class="muted">{{ employee.name }} · {{ isPartTime ? '알바' : '직원' }}</p>

      <div class="field" v-if="isPartTime">
        <label>시급 (비우면 최저시급 {{ minWage ? formatMoney(minWage) : '' }} 적용)</label>
        <AmountInput v-model="form.hourly_wage" :invalid="minWageWarning" />
        <span v-if="minWageWarning" class="input-error">최저시급({{ formatMoney(minWage) }})보다 낮아요</span>
        <label v-if="minWageWarning" class="row gap-8" style="margin-top: 4px">
          <input type="checkbox" v-model="confirmBelowMinWage" /> 낮은 시급으로 저장할게요
        </label>
      </div>
      <div class="field" v-else>
        <label>월급</label>
        <AmountInput v-model="form.monthly_wage" />
      </div>

      <div class="field">
        <label>급여 설정</label>
        <div class="col gap-8">
          <label v-if="isPartTime" class="row gap-8"><input type="checkbox" v-model="form.weekly_holiday_pay" /> 주휴수당</label>
          <label v-if="isPartTime" class="row gap-8"><input type="checkbox" v-model="form.night_premium" /> 야간 가산</label>
          <label v-if="isPartTime" class="row gap-8"><input type="checkbox" v-model="form.holiday_premium" /> 휴일 가산</label>
          <label class="row gap-8"><input type="checkbox" v-model="form.insurance_national_pension" /> 국민연금</label>
          <label class="row gap-8"><input type="checkbox" v-model="form.insurance_health" /> 건강보험</label>
          <label class="row gap-8"><input type="checkbox" v-model="form.insurance_employment" /> 고용보험</label>
        </div>
      </div>

      <div class="field">
        <label>적용 시점</label>
        <div class="col gap-8">
          <label class="card card-pad row gap-8" :style="applyFrom === 'this' ? 'border-color: var(--accent-strong)' : ''">
            <input type="radio" value="this" v-model="applyFrom" />
            <span>이번 정산 기간부터 ({{ thisPeriod.start }}부터 소급 적용)</span>
          </label>
          <label class="card card-pad row gap-8" :style="applyFrom === 'next' ? 'border-color: var(--accent-strong)' : ''">
            <input type="radio" value="next" v-model="applyFrom" />
            <span>다음 정산 기간부터 ({{ nextPeriod.start }}부터)</span>
          </label>
        </div>
      </div>

      <div v-if="preview" class="card card-pad" style="background: var(--surface-alt)">
        이번 정산 금액이 {{ formatMoney(preview.before) }}에서 {{ formatMoney(preview.after) }}으로 바뀌어요
        ({{ preview.diff >= 0 ? '+' : '' }}{{ formatMoney(preview.diff) }})
      </div>
    </template>

    <template #footer>
      <button class="btn btn-secondary" @click="emit('update:modelValue', false)">취소</button>
      <button class="btn btn-primary" :disabled="saving || (minWageWarning && !confirmBelowMinWage)" @click="save">저장</button>
    </template>
  </Panel>
</template>
