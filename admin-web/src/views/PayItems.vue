<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { employeesApi, payItemsApi } from '../api'
import AmountInput from '../components/AmountInput.vue'
import EmptyState from '../components/EmptyState.vue'
import Panel from '../components/Panel.vue'
import PeriodPicker from '../components/PeriodPicker.vue'
import Skeleton from '../components/Skeleton.vue'
import StoreChips from '../components/StoreChips.vue'
import { formatSignedMoney } from '../composables/useFormat'
import { periodBounds, periodLabel } from '../utils/period'
import { useCatalogStore } from '../stores/catalog'
import { useUiStore } from '../stores/ui'

const catalog = useCatalogStore()
const ui = useUiStore()

const storeId = ref('')
const kind = ref('')
const q = ref('')
const period = ref({ start: undefined, end: undefined })
const items = ref([])
const bonusTotal = ref(0)
const deductionTotal = ref(0)
const loading = ref(true)

const panelOpen = ref(false)
const editing = ref(null)
const employees = ref([])
const employeeSearch = ref('')
const form = ref(formDefaults())

const PURPOSE_SUGGESTIONS = ['명절 수당', '결근 공제', '지각 공제', '성과급']

function formDefaults() {
  return { employee_id: '', kind: 'bonus', amount: null, purpose: '', memo: '', period_label: '' }
}

async function load() {
  loading.value = true
  await catalog.load()
  if (!period.value.start) period.value = periodBounds(new Date(), catalog.startDay)
  try {
    const res = await payItemsApi.list({ period_label: periodLabel(period.value.start, period.value.end), kind: kind.value })
    let filtered = res.items
    if (storeId.value) filtered = filtered.filter((i) => i.pay_store_id === storeId.value)
    if (q.value) filtered = filtered.filter((i) => i.employee_name.includes(q.value))
    items.value = filtered
    bonusTotal.value = res.bonus_total
    deductionTotal.value = res.deduction_total
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  employees.value = await employeesApi.list({})
  load()
})
watch([storeId, kind, q, period], load, { deep: true })

const filteredEmployees = computed(() =>
  employeeSearch.value ? employees.value.filter((e) => e.name.includes(employeeSearch.value)).slice(0, 30) : employees.value.slice(0, 30)
)

function openAdd() {
  editing.value = null
  form.value = formDefaults()
  form.value.period_label = periodLabel(period.value.start, period.value.end)
  employeeSearch.value = ''
  panelOpen.value = true
}
function openEdit(item) {
  editing.value = item
  form.value = { employee_id: item.employee_id, kind: item.kind, amount: item.amount, purpose: item.purpose, memo: item.memo, period_label: item.period_label }
  employeeSearch.value = item.employee_name
  panelOpen.value = true
}

async function save() {
  if (!form.value.employee_id || !form.value.amount || !form.value.purpose) {
    ui.toast('직원, 금액, 목적을 입력해 주세요.')
    return
  }
  try {
    if (editing.value) await payItemsApi.update(editing.value.id, form.value)
    else await payItemsApi.create(form.value)
    ui.toast('저장했어요.')
    panelOpen.value = false
    await load()
  } catch (e) {
    ui.toast(e.message)
  }
}

async function remove() {
  const ok = await ui.confirm({ title: '항목을 삭제할까요?', message: form.value.purpose, confirmLabel: '삭제', danger: true })
  if (!ok) return
  await payItemsApi.remove(editing.value.id)
  ui.toast('삭제했어요.')
  panelOpen.value = false
  await load()
}
</script>

<template>
  <div class="col gap-20">
    <div class="row gap-12" style="justify-content: space-between; flex-wrap: wrap">
      <h1 class="display" style="font-size: 26px">보너스·공제</h1>
      <button class="btn btn-primary" @click="openAdd">항목 추가</button>
    </div>

    <div class="card card-pad col gap-14">
      <PeriodPicker v-model="period" :start-day="catalog.startDay" />
      <StoreChips v-model="storeId" :stores="catalog.stores" />
      <div class="row gap-12" style="flex-wrap: wrap">
        <input class="input" v-model="q" placeholder="직원 검색" style="max-width: 220px" />
        <div class="chip-row">
          <button class="chip" :class="{ active: kind === '' }" @click="kind = ''">전체</button>
          <button class="chip" :class="{ active: kind === 'bonus' }" @click="kind = 'bonus'">보너스</button>
          <button class="chip" :class="{ active: kind === 'deduction' }" @click="kind = 'deduction'">공제</button>
        </div>
      </div>
    </div>

    <Skeleton v-if="loading" :rows="5" />
    <EmptyState v-else-if="!items.length" message="등록된 항목이 없어요." />

    <template v-else>
      <table class="data-table card">
        <thead><tr><th>정산 기간</th><th>직원</th><th>종류</th><th class="text-right">금액</th><th>목적</th><th>메모</th></tr></thead>
        <tbody>
          <tr v-for="i in items" :key="i.id" @click="openEdit(i)">
            <td class="muted" style="font-size: 12.5px">{{ i.period_label }}</td>
            <td>{{ i.employee_name }} <span class="muted">{{ i.employment_type === 'part_time' ? '알바' : '직원' }}</span></td>
            <td>{{ i.kind === 'bonus' ? '보너스' : '공제' }}</td>
            <td class="text-right money" :class="i.kind === 'bonus' ? 'positive' : 'negative'">{{ formatSignedMoney(i.amount, i.kind) }}</td>
            <td>{{ i.purpose }}</td>
            <td class="muted" style="font-size: 13px">{{ i.memo }}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <td colspan="3" class="text-right muted">합계</td>
            <td class="text-right money positive">+{{ bonusTotal.toLocaleString('ko-KR') }}원 / <span class="negative">-{{ deductionTotal.toLocaleString('ko-KR') }}원</span></td>
            <td colspan="2"></td>
          </tr>
        </tfoot>
      </table>
    </template>

    <Panel v-model="panelOpen" :title="editing ? '항목 수정' : '항목 추가'">
      <div class="field">
        <label>직원</label>
        <input class="input" v-model="employeeSearch" placeholder="이름으로 검색" />
        <div class="col gap-4" style="max-height: 160px; overflow-y: auto; margin-top: 4px">
          <button v-for="e in filteredEmployees" :key="e.id" class="chip" style="justify-content: flex-start; width: 100%" :class="{ active: form.employee_id === e.id }" @click="form.employee_id = e.id">
            {{ e.name }}
          </button>
        </div>
      </div>
      <div class="field">
        <label>종류</label>
        <div class="row gap-8">
          <button class="btn" :class="form.kind === 'bonus' ? 'btn-primary' : 'btn-secondary'" style="flex: 1" @click="form.kind = 'bonus'">보너스</button>
          <button class="btn" :class="form.kind === 'deduction' ? 'btn-primary' : 'btn-secondary'" style="flex: 1" @click="form.kind = 'deduction'">공제</button>
        </div>
        <span class="hint">{{ form.kind === 'bonus' ? '급여에 더해요' : '급여에서 빼요' }}</span>
      </div>
      <div class="field"><label>금액</label><AmountInput v-model="form.amount" /></div>
      <div class="field">
        <label>목적</label>
        <input class="input" v-model="form.purpose" />
        <div class="chip-row">
          <button v-for="p in PURPOSE_SUGGESTIONS" :key="p" class="chip" style="height: 28px; font-size: 12.5px" @click="form.purpose = p">{{ p }}</button>
        </div>
      </div>
      <div class="field"><label>메모 (선택)</label><input class="input" v-model="form.memo" /></div>
      <div class="field">
        <label>반영할 정산 기간</label>
        <span class="hint">{{ form.period_label }}</span>
      </div>
      <template #footer>
        <button class="btn btn-secondary" @click="panelOpen = false">취소</button>
        <button v-if="editing" class="btn btn-danger" @click="remove">삭제</button>
        <button class="btn btn-primary" @click="save">{{ editing ? '저장' : '추가' }}</button>
      </template>
    </Panel>
  </div>
</template>
