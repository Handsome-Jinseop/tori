<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { employeesApi, shiftsApi } from '../api'
import EmptyState from '../components/EmptyState.vue'
import FlagBadges from '../components/FlagBadges.vue'
import PeriodPicker from '../components/PeriodPicker.vue'
import ShiftEditPanel from '../components/ShiftEditPanel.vue'
import Skeleton from '../components/Skeleton.vue'
import StoreChips from '../components/StoreChips.vue'
import { formatDate, formatDuration, formatTime } from '../composables/useFormat'
import { useIsMobile } from '../composables/useMediaQuery'
import { periodBounds } from '../utils/period'
import { useCatalogStore } from '../stores/catalog'

const catalog = useCatalogStore()
const isMobile = useIsMobile()
const route = useRoute()

const storeId = ref(route.query.store_id || '')
const employeeId = ref(route.query.employee_id || '')
const employeeSearch = ref('')
const employees = ref([])
const status = ref('')
const hasFlags = ref('')
const period = ref({
  start: route.query.date_from || undefined,
  end: route.query.date_to || undefined,
})
const items = ref([])
const totalMinutes = ref(0)
const loading = ref(true)
const panelOpen = ref(false)
const activeShiftId = ref(null)
const addOpen = ref(false)

async function load() {
  loading.value = true
  await catalog.load()
  if (!period.value.start) period.value = periodBounds(new Date(), catalog.startDay)
  try {
    const res = await shiftsApi.list({
      store_id: storeId.value,
      employee_id: employeeId.value,
      status: status.value,
      has_flags: hasFlags.value,
      date_from: period.value.start,
      date_to: period.value.end,
    })
    items.value = res.items
    totalMinutes.value = res.total_minutes
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  employees.value = await employeesApi.list({})
  load()
})
watch([storeId, employeeId, status, hasFlags, period], load, { deep: true })

function openEdit(id) {
  activeShiftId.value = id
  panelOpen.value = true
}
</script>

<template>
  <div class="col gap-20">
    <div class="row gap-12" style="justify-content: space-between; flex-wrap: wrap">
      <h1 class="display" style="font-size: 26px">근무 기록</h1>
      <button class="btn btn-primary" @click="addOpen = true">근무 기록 추가</button>
    </div>

    <div class="card card-pad col gap-14">
      <StoreChips v-model="storeId" :stores="catalog.stores" />
      <div class="row gap-12" style="flex-wrap: wrap">
        <select class="select" style="max-width: 200px" v-model="employeeId">
          <option value="">직원 전체</option>
          <option v-for="e in employees" :key="e.id" :value="e.id">{{ e.name }}</option>
        </select>
        <select class="select" style="max-width: 160px" v-model="status">
          <option value="">상태 전체</option>
          <option value="open">근무 중</option>
          <option value="closed">퇴근</option>
        </select>
        <select class="select" style="max-width: 180px" v-model="hasFlags">
          <option value="">특이사항 전체</option>
          <option value="true">있는 것만</option>
        </select>
      </div>
      <PeriodPicker v-model="period" :start-day="catalog.startDay" />
    </div>

    <Skeleton v-if="loading" :rows="6" />
    <EmptyState v-else-if="!items.length" message="조건에 맞는 근무 기록이 없어요." />

    <template v-else-if="!isMobile">
      <table class="data-table card">
        <thead>
          <tr><th>날짜</th><th>직원</th><th>근무 매장</th><th>출근</th><th>퇴근</th><th>근무시간</th><th>배지</th></tr>
        </thead>
        <tbody>
          <tr v-for="s in items" :key="s.id" @click="openEdit(s.id)">
            <td>{{ formatDate(s.business_date) }}</td>
            <td>{{ s.employee_name }} <span class="muted">{{ s.employment_type === 'part_time' ? '알바' : '직원' }}</span></td>
            <td>{{ s.store_name }}</td>
            <td class="numeric">{{ formatTime(s.check_in) }}</td>
            <td class="numeric">{{ s.check_out ? formatTime(s.check_out) : '근무 중' }}</td>
            <td class="numeric">{{ formatDuration(s.minutes) }}</td>
            <td><FlagBadges :flags="s.flags" :reviewed="s.reviewed" /></td>
          </tr>
        </tbody>
        <tfoot>
          <tr><td colspan="5" class="text-right muted">합계</td><td class="numeric" style="font-weight: 700">{{ formatDuration(totalMinutes) }}</td><td></td></tr>
        </tfoot>
      </table>
    </template>

    <template v-else>
      <div v-for="s in items" :key="s.id" class="card card-pad col gap-8" @click="openEdit(s.id)">
        <div class="row gap-8">
          <strong>{{ s.employee_name }}</strong>
          <span class="muted">{{ s.employment_type === 'part_time' ? '알바' : '직원' }}</span>
          <span class="muted" style="margin-left: auto">{{ formatDate(s.business_date) }}</span>
        </div>
        <div class="row gap-12 muted numeric" style="font-size: 14px">
          <span>{{ s.store_name }}</span>
          <span>{{ formatTime(s.check_in) }} ~ {{ s.check_out ? formatTime(s.check_out) : '근무 중' }}</span>
          <span>{{ formatDuration(s.minutes) }}</span>
        </div>
        <FlagBadges :flags="s.flags" :reviewed="s.reviewed" />
      </div>
      <div class="card card-pad row" style="justify-content: space-between">
        <span class="muted">합계</span>
        <span class="numeric" style="font-weight: 700">{{ formatDuration(totalMinutes) }}</span>
      </div>
    </template>

    <ShiftEditPanel v-model="panelOpen" :shift-id="activeShiftId" @saved="load" />
    <ShiftEditPanel v-model="addOpen" :shift-id="null" @saved="load" />
  </div>
</template>
