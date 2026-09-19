<script setup>
import { onMounted, ref, watch } from 'vue'
import { reportsApi } from '../api'
import EmptyState from '../components/EmptyState.vue'
import PeriodPicker from '../components/PeriodPicker.vue'
import Skeleton from '../components/Skeleton.vue'
import { formatMoney } from '../composables/useFormat'
import { periodBounds } from '../utils/period'
import { useCatalogStore } from '../stores/catalog'

const catalog = useCatalogStore()
const period = ref({ start: undefined, end: undefined })
const data = ref(null)
const loading = ref(true)
const sortKey = ref('net_pay')
const sortDir = ref(-1)

async function load() {
  loading.value = true
  await catalog.load()
  if (!period.value.start) period.value = periodBounds(new Date(), catalog.startDay)
  try {
    data.value = await reportsApi.stores(period.value.start, period.value.end)
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(period, load, { deep: true })

function sortBy(key) {
  if (sortKey.value === key) sortDir.value *= -1
  else {
    sortKey.value = key
    sortDir.value = -1
  }
}

function sortedRanking() {
  if (!data.value) return []
  return [...data.value.ranking].sort((a, b) => (a[sortKey.value] > b[sortKey.value] ? 1 : -1) * sortDir.value)
}

const csvUrl = () => reportsApi.storesCsvUrl(period.value.start, period.value.end)
const maxCost = () => Math.max(1, ...(data.value?.stores.map((s) => s.total_cost) || [1]))
</script>

<template>
  <div class="col gap-20">
    <div class="row gap-12" style="justify-content: space-between; flex-wrap: wrap">
      <div class="col gap-4">
        <h1 class="display" style="font-size: 26px">매장별 리포트</h1>
        <span v-if="data?.is_draft" class="muted" style="font-size: 13px">초안 기준</span>
      </div>
      <a class="btn btn-secondary" :href="csvUrl()">CSV 내보내기</a>
    </div>

    <div class="card card-pad"><PeriodPicker v-model="period" :start-day="catalog.startDay" /></div>

    <Skeleton v-if="loading" :rows="6" />
    <EmptyState v-else-if="!data?.stores.length" message="이 기간에 정산된 데이터가 없어요." />

    <template v-else>
      <div class="grid-3">
        <div v-for="s in data.stores" :key="s.store_id" class="card card-pad col gap-6">
          <strong>{{ s.name }}</strong>
          <span class="display" style="font-size: 22px">{{ formatMoney(s.total_cost) }}</span>
          <span class="muted" style="font-size: 13px">알바 {{ formatMoney(s.part_time_cost) }} · 직원 {{ formatMoney(s.regular_cost) }}</span>
        </div>
      </div>

      <div class="card card-pad col gap-10">
        <strong>매장별 인건비</strong>
        <div v-for="s in data.stores" :key="s.store_id" class="col gap-4">
          <div class="row" style="justify-content: space-between; font-size: 13px"><span>{{ s.name }}</span><span class="numeric">{{ formatMoney(s.total_cost) }}</span></div>
          <div class="bar-track">
            <div class="bar-segment part-time" :style="{ width: `${(s.part_time_cost / maxCost()) * 100}%` }" />
            <div class="bar-segment regular" :style="{ width: `${(s.regular_cost / maxCost()) * 100}%` }" />
          </div>
        </div>
        <div class="row gap-16" style="font-size: 12.5px">
          <span class="row gap-6"><span class="legend-dot part-time" />알바</span>
          <span class="row gap-6"><span class="legend-dot regular" />직원</span>
        </div>
      </div>

      <table class="data-table card">
        <thead><tr><th>매장</th><th class="text-right">알바 인건비</th><th class="text-right">직원 인건비</th><th class="text-right">인건비 합계</th><th class="text-right">공제 합계</th><th class="text-right">실수령 합계</th><th class="text-right">근무시간 합계</th></tr></thead>
        <tbody>
          <tr v-for="s in data.stores" :key="s.store_id">
            <td>{{ s.name }}</td>
            <td class="text-right numeric">{{ formatMoney(s.part_time_cost) }}</td>
            <td class="text-right numeric">{{ formatMoney(s.regular_cost) }}</td>
            <td class="text-right numeric" style="font-weight: 700">{{ formatMoney(s.total_cost) }}</td>
            <td class="text-right numeric">{{ formatMoney(s.deduction_total) }}</td>
            <td class="text-right numeric">{{ formatMoney(s.net_total) }}</td>
            <td class="text-right numeric">{{ s.total_hours }}시간</td>
          </tr>
        </tbody>
      </table>

      <div class="col gap-8">
        <strong>직원별 순위</strong>
        <table class="data-table card">
          <thead>
            <tr>
              <th @click="sortBy('name')" style="cursor: pointer">직원</th>
              <th>구분</th>
              <th>급여 관리 매장</th>
              <th class="text-right" @click="sortBy('net_pay')" style="cursor: pointer">실수령액</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in sortedRanking()" :key="r.employee_id">
              <td>{{ r.name }}</td>
              <td>{{ r.employment_type === 'part_time' ? '알바' : '직원' }}</td>
              <td>{{ catalog.storeName(r.pay_store_id) }}</td>
              <td class="text-right numeric" style="font-weight: 700">{{ formatMoney(r.net_pay) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <p class="hint">인건비는 급여 관리 매장 기준이고, 근무시간은 실제 근무한 매장 기준이에요.</p>
    </template>
  </div>
</template>

<style scoped>
.grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.bar-track { height: 10px; border-radius: 6px; background: var(--border-soft); display: flex; overflow: hidden; }
.bar-segment.part-time { background: var(--accent); }
.bar-segment.regular { background: var(--info-icon); }
.legend-dot { width: 9px; height: 9px; border-radius: 3px; display: inline-block; }
.legend-dot.part-time { background: var(--accent); }
.legend-dot.regular { background: var(--info-icon); }
@media (max-width: 900px) { .grid-3 { grid-template-columns: 1fr; } }
</style>
