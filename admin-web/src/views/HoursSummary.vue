<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { reportsApi } from '../api'
import EmptyState from '../components/EmptyState.vue'
import PeriodPicker from '../components/PeriodPicker.vue'
import Skeleton from '../components/Skeleton.vue'
import { formatDuration } from '../composables/useFormat'
import { useIsMobile } from '../composables/useMediaQuery'
import { periodBounds } from '../utils/period'
import { useCatalogStore } from '../stores/catalog'

const catalog = useCatalogStore()
const isMobile = useIsMobile()
const router = useRouter()

const employmentType = ref('')
const period = ref({ start: undefined, end: undefined })
const data = ref(null)
const loading = ref(true)

async function load() {
  loading.value = true
  await catalog.load()
  if (!period.value.start) period.value = periodBounds(new Date(), catalog.startDay)
  try {
    data.value = await reportsApi.hours({
      period_start: period.value.start,
      period_end: period.value.end,
      employment_type: employmentType.value,
    })
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch([employmentType, period], load, { deep: true })

function goToRecords(employeeId, storeId) {
  router.push({
    path: '/shifts',
    query: { employee_id: employeeId, store_id: storeId, date_from: period.value.start, date_to: period.value.end },
  })
}
</script>

<template>
  <div class="col gap-20">
    <h1 class="display" style="font-size: 26px">근무시간 요약</h1>

    <div class="card card-pad col gap-14">
      <PeriodPicker v-model="period" :start-day="catalog.startDay" />
      <div class="chip-row">
        <button class="chip" :class="{ active: employmentType === '' }" @click="employmentType = ''">전체</button>
        <button class="chip" :class="{ active: employmentType === 'part_time' }" @click="employmentType = 'part_time'">알바</button>
        <button class="chip" :class="{ active: employmentType === 'regular' }" @click="employmentType = 'regular'">직원</button>
      </div>
    </div>

    <Skeleton v-if="loading" :rows="6" />
    <EmptyState v-else-if="!data?.rows.length" message="조건에 맞는 근무 기록이 없어요." />

    <template v-else-if="!isMobile">
      <table class="data-table card">
        <thead>
          <tr>
            <th>직원</th>
            <th v-for="s in data.stores" :key="s.id" class="text-right">{{ s.name }}</th>
            <th class="text-right">합계</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in data.rows" :key="r.employee_id">
            <td>{{ r.name }} <span class="muted" style="font-size: 12.5px">{{ r.pay_store_name }}</span></td>
            <td v-for="s in data.stores" :key="s.id" class="text-right numeric" @click="r.cells[s.id] && goToRecords(r.employee_id, s.id)">
              {{ r.cells[s.id] ? formatDuration(r.cells[s.id]) : '-' }}
            </td>
            <td class="text-right numeric" style="font-weight: 700">{{ formatDuration(r.total_minutes) }}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <td class="muted">합계</td>
            <td v-for="s in data.stores" :key="s.id" class="text-right numeric">{{ formatDuration(data.store_totals[s.id]) }}</td>
            <td class="text-right numeric" style="font-weight: 700">{{ formatDuration(data.grand_total) }}</td>
          </tr>
        </tfoot>
      </table>
    </template>

    <template v-else>
      <div v-for="r in data.rows" :key="r.employee_id" class="card card-pad col gap-8">
        <div class="row">
          <strong>{{ r.name }}</strong>
          <span class="muted" style="margin-left: 8px; font-size: 12.5px">{{ r.pay_store_name }}</span>
          <span class="numeric" style="margin-left: auto; font-weight: 700">{{ formatDuration(r.total_minutes) }}</span>
        </div>
        <div v-for="s in data.stores" :key="s.id" class="row" style="justify-content: space-between; font-size: 14px" @click="r.cells[s.id] && goToRecords(r.employee_id, s.id)">
          <span class="muted">{{ s.name }}</span>
          <span class="numeric">{{ r.cells[s.id] ? formatDuration(r.cells[s.id]) : '-' }}</span>
        </div>
      </div>
    </template>
  </div>
</template>
