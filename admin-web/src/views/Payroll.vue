<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { payrollsApi } from '../api'
import AmountInput from '../components/AmountInput.vue'
import EmptyState from '../components/EmptyState.vue'
import PeriodPicker from '../components/PeriodPicker.vue'
import Skeleton from '../components/Skeleton.vue'
import { formatDuration, formatMoney } from '../composables/useFormat'
import { useIsMobile } from '../composables/useMediaQuery'
import { periodBounds } from '../utils/period'
import { useCatalogStore } from '../stores/catalog'
import { useUiStore } from '../stores/ui'

const catalog = useCatalogStore()
const ui = useUiStore()
const isMobile = useIsMobile()
const router = useRouter()

const period = ref({ start: undefined, end: undefined })
const data = ref(null)
const loading = ref(true)
const ran = ref(true)
const expandedId = ref(null)
const busy = ref(false)

function allowanceOf(item) {
  return item.lines
    .filter((l) => ['weekly_holiday_pay', 'night_premium', 'holiday_premium'].includes(l.code))
    .reduce((sum, l) => sum + l.amount, 0)
}
function baseLine(item) {
  return item.lines.find((l) => l.code.startsWith('base_pay'))
}
function bonusOf(item) {
  const line = item.lines.find((l) => l.code === 'pay_items')
  if (!line) return 0
  return (line.basis || []).filter((b) => b.kind === 'bonus').reduce((s, b) => s + b.amount, 0)
}
function deductionItemsOf(item) {
  const line = item.lines.find((l) => l.code === 'pay_items')
  if (!line) return 0
  return (line.basis || []).filter((b) => b.kind === 'deduction').reduce((s, b) => s + b.amount, 0)
}

async function load() {
  loading.value = true
  await catalog.load()
  if (!period.value.start) period.value = periodBounds(new Date(), catalog.startDay)
  try {
    const res = await payrollsApi.get(period.value.start, period.value.end)
    data.value = res
    ran.value = res.items.length > 0
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(period, load, { deep: true })

async function run() {
  busy.value = true
  try {
    data.value = await payrollsApi.run(period.value.start, period.value.end)
    ran.value = true
    ui.toast('정산을 실행했어요.')
  } finally {
    busy.value = false
  }
}

async function confirm() {
  let message = '확정하면 금액이 잠기고, 나중에 시급이나 요율이 바뀌어도 이 정산은 변하지 않아요.'
  if (data.value.review_count) message += ` 확인이 필요한 근무가 ${data.value.review_count}건 남아 있어요.`
  const ok = await ui.confirm({ title: '정산을 확정할까요?', message, confirmLabel: '확정' })
  if (!ok) return
  data.value = await payrollsApi.confirm(period.value.start, period.value.end)
  ui.toast('확정했어요.')
}

async function reopen() {
  const ok = await ui.confirm({
    title: '정산을 재오픈할까요?',
    message: '다시 수정할 수 있게 돼요. 재오픈과 재확정은 기록에 남아요.',
    confirmLabel: '재오픈',
  })
  if (!ok) return
  data.value = await payrollsApi.reopen(period.value.start, period.value.end)
  ui.toast('재오픈했어요.')
}

function toggle(id) {
  expandedId.value = expandedId.value === id ? null : id
}

async function toggleWeekExcluded(item, week) {
  const excluded = new Set(item.overrides?.weekly_holiday_excluded || [])
  if (excluded.has(week)) excluded.delete(week)
  else excluded.add(week)
  await payrollsApi.updateOverrides(item.employee_id, {
    period_start: period.value.start, period_end: period.value.end,
    weekly_holiday_excluded: [...excluded], insurance_amounts: item.overrides?.insurance_amounts || {},
  })
  await load()
}

async function overrideInsurance(item, code, amount) {
  const amounts = { ...(item.overrides?.insurance_amounts || {}), [code]: amount }
  await payrollsApi.updateOverrides(item.employee_id, {
    period_start: period.value.start, period_end: period.value.end,
    weekly_holiday_excluded: item.overrides?.weekly_holiday_excluded || [], insurance_amounts: amounts,
  })
  await load()
}

function goToRecords(employeeId) {
  router.push({ path: '/shifts', query: { employee_id: employeeId, date_from: period.value.start, date_to: period.value.end } })
}

const csvUrl = computed(() => data.value ? payrollsApi.csvUrl(period.value.start, period.value.end) : '')
</script>

<template>
  <div class="col gap-20">
    <div class="row gap-12" style="justify-content: space-between; flex-wrap: wrap">
      <h1 class="display" style="font-size: 26px">정산</h1>
      <div class="row gap-8">
        <span v-if="ran" class="badge" :class="data?.status === 'confirmed' ? 'badge-success' : 'badge-info'">
          <span class="dot" />{{ data?.status === 'confirmed' ? '확정' : '초안' }}
        </span>
      </div>
    </div>

    <div class="card card-pad">
      <PeriodPicker v-model="period" :start-day="catalog.startDay" />
    </div>

    <Skeleton v-if="loading" :rows="6" />

    <template v-else-if="!ran">
      <EmptyState message="기간을 정하고 [정산 실행]을 눌러 주세요.">
        <button class="btn btn-primary" :disabled="busy" @click="run">정산 실행</button>
      </EmptyState>
    </template>

    <template v-else>
      <div v-if="data.status === 'draft' && data.review_count" class="card card-pad row gap-12" style="background: var(--caution-bg)">
        <span style="color: var(--caution-fg); font-weight: 700">확인이 필요한 근무가 {{ data.review_count }}건 남아 있어요</span>
        <router-link
          :to="{ path: '/shifts/review', query: { date_from: period.start, date_to: period.end } }"
          class="btn btn-secondary btn-sm" style="margin-left: auto"
        >확인하러 가기</router-link>
      </div>
      <div v-if="data.overlapping_confirmed" class="card card-pad" style="background: var(--warning-bg); color: var(--warning-fg); font-weight: 700">
        기간이 겹치는 확정 정산이 있어요
      </div>

      <div class="grid-summary">
        <div class="card card-pad col gap-4"><span class="muted">지급 합계</span><span class="display" style="font-size: 22px">{{ formatMoney(data.totals.gross_pay) }}</span></div>
        <div class="card card-pad col gap-4"><span class="muted">공제 합계</span><span class="display" style="font-size: 22px">{{ formatMoney(data.totals.deduction_total) }}</span></div>
        <div class="card card-pad col gap-4"><span class="muted">실수령 합계</span><span class="display" style="font-size: 22px; color: var(--accent-ink)">{{ formatMoney(data.totals.net_pay) }}</span></div>
        <div v-for="s in catalog.stores" :key="s.id" class="card card-pad col gap-4">
          <span class="muted">{{ s.name }}</span>
          <span class="display" style="font-size: 18px">{{ formatMoney(data.store_totals[s.id] || 0) }}</span>
        </div>
      </div>

      <div v-if="!isMobile" class="payroll-row muted" style="font-size: 12.5px; font-weight: 700; padding: 0 16px">
        <div style="flex: 1.4">직원</div>
        <div style="flex: 1">근무시간</div>
        <div style="flex: 1">기본급</div>
        <div style="flex: 1">수당</div>
        <div style="flex: 1">보너스</div>
        <div style="flex: 1">공제 항목</div>
        <div style="flex: 1">4대보험</div>
        <div style="flex: 1.2">실수령액</div>
      </div>

      <div class="col gap-8">
        <div v-for="item in data.items" :key="item.employee_id" class="card">
          <div class="payroll-row" @click="toggle(item.employee_id)">
            <div class="col gap-2" style="flex: 1.4">
              <strong>{{ item.employee_name }}</strong>
              <span class="muted" style="font-size: 12.5px">{{ item.employment_type === 'part_time' ? '알바' : '직원' }} · {{ catalog.storeName(item.pay_store_id) }}</span>
            </div>
            <div class="col gap-2 numeric" style="flex: 1">
              <span v-if="item.employment_type === 'regular'">월급</span>
              <span v-else>{{ formatDuration(Object.values(item.hours_by_store).reduce((a, b) => a + b, 0)) }}</span>
            </div>
            <div class="numeric" style="flex: 1">{{ formatMoney(baseLine(item)?.amount || 0) }}</div>
            <div class="numeric" style="flex: 1">{{ formatMoney(allowanceOf(item)) }}</div>
            <div class="numeric" style="flex: 1">{{ formatMoney(bonusOf(item)) }}</div>
            <div class="numeric" style="flex: 1">{{ deductionItemsOf(item) ? '−' + formatMoney(deductionItemsOf(item)) : '-' }}</div>
            <div class="numeric" style="flex: 1">{{ item.insurance_total ? '−' + formatMoney(item.insurance_total) : '-' }}</div>
            <div class="numeric" style="flex: 1.2; font-weight: 700; font-size: 16px">{{ formatMoney(item.net_pay) }}</div>
          </div>

          <div v-if="expandedId === item.employee_id" class="payroll-detail">
            <div class="col gap-6">
              <strong style="font-size: 13.5px">기본급</strong>
              <span class="muted">{{ baseLine(item)?.basis }} · {{ formatMoney(baseLine(item)?.amount || 0) }}</span>
              <button class="btn btn-ghost btn-sm" style="align-self: flex-start" @click="goToRecords(item.employee_id)">근무 기록 보기</button>
            </div>

            <template v-for="line in item.lines" :key="line.code">
              <div v-if="line.code === 'weekly_holiday_pay' && line.basis.length" class="col gap-6">
                <strong style="font-size: 13.5px">주휴수당</strong>
                <table class="data-table">
                  <thead><tr><th>주</th><th>근무시간</th><th>지급</th><th class="text-right">금액</th></tr></thead>
                  <tbody>
                    <tr v-for="w in line.basis" :key="w.week">
                      <td>{{ w.week }}</td>
                      <td class="numeric">{{ w.hours }}시간</td>
                      <td v-if="data.status === 'draft'">
                        <label class="row gap-6" style="font-size: 13px"><input type="checkbox" :checked="!w.eligible && w.hours >= 15" @change="toggleWeekExcluded(item, w.week)" /> 제외</label>
                      </td>
                      <td v-else>{{ w.eligible ? '지급' : '제외' }}</td>
                      <td class="text-right numeric">{{ formatMoney(w.amount) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div v-else-if="(line.code === 'night_premium' || line.code === 'holiday_premium') && line.amount" class="row gap-8">
                <span class="muted" style="width: 100px">{{ line.name }}</span>
                <span>{{ line.basis }} · {{ formatMoney(line.amount) }}</span>
              </div>
            </template>

            <div v-if="bonusOf(item) || deductionItemsOf(item)" class="col gap-6">
              <strong style="font-size: 13.5px">보너스·공제</strong>
              <div v-for="b in (item.lines.find((l) => l.code === 'pay_items')?.basis || [])" :key="b.code" class="row gap-8" style="font-size: 13.5px">
                <span>{{ b.name }}</span>
                <span class="money" :class="b.kind === 'bonus' ? 'positive' : 'negative'" style="margin-left: auto">
                  {{ b.kind === 'bonus' ? '+' : '−' }}{{ formatMoney(b.amount) }}
                </span>
              </div>
              <router-link to="/pay-items" class="btn btn-ghost btn-sm" style="align-self: flex-start">보너스·공제로 이동</router-link>
            </div>

            <div v-if="item.insurance_lines.length" class="col gap-6">
              <strong style="font-size: 13.5px">4대보험</strong>
              <div v-for="l in item.insurance_lines" :key="l.code" class="row gap-8" style="font-size: 13.5px; align-items: center">
                <span style="width: 90px">{{ l.name }}</span>
                <AmountInput
                  v-if="data.status === 'draft'"
                  :model-value="l.amount"
                  style="max-width: 160px"
                  @update:model-value="(v) => overrideInsurance(item, l.code, v)"
                />
                <span v-else>{{ formatMoney(l.amount) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="row gap-12">
        <template v-if="data.status === 'draft'">
          <button class="btn btn-secondary" :disabled="busy" @click="run">다시 계산</button>
          <button class="btn btn-primary" @click="confirm">확정</button>
        </template>
        <template v-else>
          <button class="btn btn-secondary" @click="reopen">재오픈</button>
          <a class="btn btn-secondary" :href="csvUrl">CSV 내보내기</a>
        </template>
      </div>
    </template>
  </div>
</template>

<style scoped>
.grid-summary { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; }
.payroll-row { display: flex; align-items: center; gap: 12px; padding: 14px 16px; cursor: pointer; }
.payroll-detail { padding: 0 16px 18px; display: flex; flex-direction: column; gap: 16px; border-top: 1px solid var(--border-soft); padding-top: 16px; margin: 0 16px 16px; }
@media (max-width: 1000px) {
  .grid-summary { grid-template-columns: repeat(3, 1fr); }
  .payroll-row { flex-wrap: wrap; }
}
</style>
