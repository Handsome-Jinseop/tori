<script setup>
import { onMounted, ref, watch } from 'vue'
import { employeesApi } from '../api'
import AmountInput from '../components/AmountInput.vue'
import EmployeeDetailPanel from '../components/EmployeeDetailPanel.vue'
import EmptyState from '../components/EmptyState.vue'
import Panel from '../components/Panel.vue'
import Skeleton from '../components/Skeleton.vue'
import { formatMoney } from '../composables/useFormat'
import { useIsMobile } from '../composables/useMediaQuery'
import { useCatalogStore } from '../stores/catalog'
import { useUiStore } from '../stores/ui'

const catalog = useCatalogStore()
const ui = useUiStore()
const isMobile = useIsMobile()

const q = ref('')
const employmentType = ref('')
const active = ref('true')
const payStoreId = ref('')
const items = ref([])
const loading = ref(true)

const detailOpen = ref(false)
const activeEmployeeId = ref(null)
const addOpen = ref(false)
const addForm = ref(addDefaults())

function addDefaults() {
  return {
    name: '', employment_type: 'part_time', pay_store_id: '', work_store_ids: [],
    hire_date: new Date().toISOString().slice(0, 10), face_exempt: false,
    hourly_wage: null, monthly_wage: null,
  }
}

async function load() {
  loading.value = true
  await catalog.load()
  if (!addForm.value.pay_store_id) addForm.value.pay_store_id = catalog.stores[0]?.id || ''
  try {
    items.value = await employeesApi.list({
      q: q.value, employment_type: employmentType.value, active: active.value, pay_store_id: payStoreId.value,
    })
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch([q, employmentType, active, payStoreId], load)

function openDetail(id) {
  activeEmployeeId.value = id
  detailOpen.value = true
}

function openAdd() {
  addForm.value = addDefaults()
  addForm.value.pay_store_id = catalog.stores[0]?.id || ''
  addOpen.value = true
}

function toggleAddWorkStore(id) {
  const set = new Set(addForm.value.work_store_ids)
  if (set.has(id)) set.delete(id)
  else set.add(id)
  addForm.value.work_store_ids = [...set]
}

async function submitAdd() {
  if (!addForm.value.name || !addForm.value.work_store_ids.length) {
    ui.toast('이름과 근무 가능 매장을 입력해 주세요.')
    return
  }
  try {
    await employeesApi.create(addForm.value)
    ui.toast('직원을 추가했어요.')
    addOpen.value = false
    await load()
  } catch (e) {
    ui.toast(e.message)
  }
}

const FACE_ICON = { approved: '●', pending: '◐', revoked: '○' }
</script>

<template>
  <div class="col gap-20">
    <div class="row gap-12" style="justify-content: space-between; flex-wrap: wrap">
      <h1 class="display" style="font-size: 26px">직원 관리</h1>
      <button class="btn btn-primary" @click="openAdd">직원 추가</button>
    </div>

    <div class="card card-pad col gap-14">
      <input class="input" v-model="q" placeholder="이름 검색" style="max-width: 260px" />
      <div class="row gap-16" style="flex-wrap: wrap">
        <div class="chip-row">
          <button class="chip" :class="{ active: employmentType === '' }" @click="employmentType = ''">전체</button>
          <button class="chip" :class="{ active: employmentType === 'part_time' }" @click="employmentType = 'part_time'">알바</button>
          <button class="chip" :class="{ active: employmentType === 'regular' }" @click="employmentType = 'regular'">직원</button>
        </div>
        <div class="chip-row">
          <button class="chip" :class="{ active: active === 'true' }" @click="active = 'true'">재직</button>
          <button class="chip" :class="{ active: active === 'false' }" @click="active = 'false'">퇴사</button>
          <button class="chip" :class="{ active: active === '' }" @click="active = ''">전체</button>
        </div>
      </div>
      <div class="chip-row">
        <button class="chip" :class="{ active: payStoreId === '' }" @click="payStoreId = ''">매장 전체</button>
        <button v-for="s in catalog.stores" :key="s.id" class="chip" :class="{ active: payStoreId === s.id }" @click="payStoreId = s.id">{{ s.name }}</button>
      </div>
    </div>

    <Skeleton v-if="loading" :rows="6" />
    <EmptyState v-else-if="!items.length" message="조건에 맞는 직원이 없어요." />

    <template v-else-if="!isMobile">
      <table class="data-table card">
        <thead>
          <tr><th>이름</th><th>구분</th><th>급여 관리 매장</th><th>근무 가능 매장</th><th>시급/월급</th><th>얼굴 등록</th><th>재직</th></tr>
        </thead>
        <tbody>
          <tr v-for="e in items" :key="e.id" @click="openDetail(e.id)">
            <td>{{ e.name }}</td>
            <td>{{ e.employment_type === 'part_time' ? '알바' : '직원' }}</td>
            <td>{{ catalog.storeName(e.pay_store_id) }}</td>
            <td><span class="chip-row">
              <span v-for="sid in e.work_store_ids" :key="sid" class="chip" style="height: 24px; padding: 0 8px; font-size: 11.5px; cursor: default">{{ catalog.storeName(sid) }}</span>
            </span></td>
            <td class="numeric">
              {{ e.employment_type === 'part_time' ? (e.current_pay_rate?.hourly_wage ? formatMoney(e.current_pay_rate.hourly_wage) : '최저시급') : formatMoney(e.current_pay_rate?.monthly_wage) }}
            </td>
            <td>
              <span v-for="s in catalog.stores" :key="s.id" :title="s.name" style="margin-right: 4px">
                {{ FACE_ICON[e.face_status[s.id]] || '·' }}
              </span>
            </td>
            <td>{{ e.active ? '재직' : '퇴사' }}</td>
          </tr>
        </tbody>
      </table>
    </template>

    <template v-else>
      <div v-for="e in items" :key="e.id" class="card card-pad col gap-6" @click="openDetail(e.id)">
        <div class="row" style="justify-content: space-between">
          <strong>{{ e.name }}</strong>
          <span class="muted">{{ e.employment_type === 'part_time' ? '알바' : '직원' }}</span>
        </div>
        <span class="muted" style="font-size: 13.5px">{{ catalog.storeName(e.pay_store_id) }}</span>
        <span class="numeric" style="font-size: 14px">
          {{ e.employment_type === 'part_time' ? (e.current_pay_rate?.hourly_wage ? formatMoney(e.current_pay_rate.hourly_wage) : '최저시급') : formatMoney(e.current_pay_rate?.monthly_wage) }}
        </span>
      </div>
    </template>

    <EmployeeDetailPanel v-model="detailOpen" :employee-id="activeEmployeeId" @changed="load" />

    <Panel v-model="addOpen" title="직원 추가">
      <div class="field"><label>이름</label><input class="input" v-model="addForm.name" /></div>
      <div class="field">
        <label>구분</label>
        <div class="chip-row">
          <button class="chip" :class="{ active: addForm.employment_type === 'part_time' }" @click="addForm.employment_type = 'part_time'">알바</button>
          <button class="chip" :class="{ active: addForm.employment_type === 'regular' }" @click="addForm.employment_type = 'regular'">직원</button>
        </div>
      </div>
      <div class="field">
        <label>급여 관리 매장</label>
        <select class="select" v-model="addForm.pay_store_id">
          <option v-for="s in catalog.stores" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
      </div>
      <div class="field">
        <label>근무 가능 매장</label>
        <div class="chip-row">
          <button v-for="s in catalog.stores" :key="s.id" class="chip" :class="{ active: addForm.work_store_ids.includes(s.id) }" @click="toggleAddWorkStore(s.id)">{{ s.name }}</button>
        </div>
      </div>
      <div class="field"><label>입사일</label><input type="date" class="input" v-model="addForm.hire_date" /></div>
      <div class="field" v-if="addForm.employment_type === 'part_time'">
        <label>시급 (비우면 최저시급)</label>
        <AmountInput v-model="addForm.hourly_wage" />
      </div>
      <div class="field" v-else>
        <label>월급</label>
        <AmountInput v-model="addForm.monthly_wage" />
      </div>
      <p class="hint">급여 설정 스위치(주휴수당, 야간·휴일 가산, 4대보험)는 모두 미적용으로 시작해요. 추가한 뒤 직원 상세에서 바꿀 수 있어요.</p>

      <template #footer>
        <button class="btn btn-secondary" @click="addOpen = false">취소</button>
        <button class="btn btn-primary" @click="submitAdd">추가</button>
      </template>
    </Panel>
  </div>
</template>
