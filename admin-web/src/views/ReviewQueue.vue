<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { shiftsApi } from '../api'
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
import { useUiStore } from '../stores/ui'

const catalog = useCatalogStore()
const ui = useUiStore()
const isMobile = useIsMobile()
const route = useRoute()

const FLAG_FILTERS = [
  { key: 'auto_checkout', label: '자동 퇴근' },
  { key: 'manual_out,manual_in', label: '수기 입력' },
  { key: 'manual_pick', label: '수기 선택' },
  { key: 'clock_skew', label: '시각 이상' },
  { key: 'duplicate_in,missing_in', label: '출근 중복·누락' },
  { key: 'temp_employee', label: '임시 직원' },
]

const storeId = ref('')
const flagFilter = ref('')
const showReviewed = ref(false)
const period = ref(
  route.query.date_from && route.query.date_to
    ? { start: route.query.date_from, end: route.query.date_to }
    : periodBounds(new Date(), 1)
)
const items = ref([])
const loading = ref(true)
const selected = ref(new Set())
const panelOpen = ref(false)
const activeShiftId = ref(null)

async function load() {
  loading.value = true
  await catalog.load()
  if (period.value.start === undefined) period.value = periodBounds(new Date(), catalog.startDay)
  try {
    const res = await shiftsApi.list({
      store_id: storeId.value,
      flags_any: flagFilter.value,
      has_flags: 'true',
      date_from: period.value.start,
      date_to: period.value.end,
      reviewed: showReviewed.value ? '' : 'false',
    })
    items.value = res.items
    selected.value = new Set()
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch([storeId, flagFilter, showReviewed, period], load, { deep: true })

function toggleSelect(id) {
  const next = new Set(selected.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selected.value = next
}

async function markReviewed(ids) {
  await shiftsApi.review(ids)
  ui.toast('확인 완료로 처리했어요.')
  await load()
}

function openEdit(id) {
  activeShiftId.value = id
  panelOpen.value = true
}

const selectedCount = computed(() => selected.value.size)
</script>

<template>
  <div class="col gap-20">
    <div class="row gap-12" style="justify-content: space-between; flex-wrap: wrap">
      <h1 class="display" style="font-size: 26px">확인 필요 <span class="muted" style="font-size: 18px">{{ items.length }}건</span></h1>
    </div>

    <div class="card card-pad col gap-14">
      <StoreChips v-model="storeId" :stores="catalog.stores" />
      <div class="chip-row">
        <button class="chip" :class="{ active: flagFilter === '' }" @click="flagFilter = ''">전체</button>
        <button v-for="f in FLAG_FILTERS" :key="f.key" class="chip" :class="{ active: flagFilter === f.key }" @click="flagFilter = f.key">
          {{ f.label }}
        </button>
      </div>
      <div class="row gap-12" style="justify-content: space-between; flex-wrap: wrap">
        <PeriodPicker v-model="period" :start-day="catalog.startDay" />
        <label class="row gap-8"><input type="checkbox" v-model="showReviewed" /> 확인 완료 항목도 보기</label>
      </div>
    </div>

    <div v-if="selectedCount" class="row gap-12" style="justify-content: flex-end">
      <button class="btn btn-secondary" @click="markReviewed([...selected])">선택 항목 확인 완료 ({{ selectedCount }})</button>
    </div>

    <Skeleton v-if="loading" :rows="6" />
    <EmptyState v-else-if="!items.length" message="확인할 근무가 없어요. 모두 정상이에요." />

    <template v-else-if="!isMobile">
      <table class="data-table card">
        <thead>
          <tr>
            <th style="width: 30px"></th>
            <th>날짜</th><th>직원</th><th>근무 매장</th><th>출근</th><th>퇴근</th><th>근무시간</th><th>배지</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in items" :key="s.id">
            <td><input type="checkbox" :checked="selected.has(s.id)" @change="toggleSelect(s.id)" @click.stop /></td>
            <td @click="openEdit(s.id)">{{ formatDate(s.business_date) }}</td>
            <td @click="openEdit(s.id)">{{ s.employee_name }} <span class="muted">{{ s.employment_type === 'part_time' ? '알바' : '직원' }}</span></td>
            <td @click="openEdit(s.id)">{{ s.store_name }}</td>
            <td @click="openEdit(s.id)" class="numeric">{{ formatTime(s.check_in) }}</td>
            <td @click="openEdit(s.id)" class="numeric">{{ s.check_out ? formatTime(s.check_out) : '근무 중' }}</td>
            <td @click="openEdit(s.id)" class="numeric">{{ formatDuration(s.minutes) }}</td>
            <td @click="openEdit(s.id)"><FlagBadges :flags="s.flags" :reviewed="s.reviewed" /></td>
            <td class="row gap-8">
              <button class="btn btn-secondary btn-sm" @click="openEdit(s.id)">수정</button>
              <button class="btn btn-ghost btn-sm" @click="markReviewed([s.id])">확인 완료</button>
            </td>
          </tr>
        </tbody>
      </table>
    </template>

    <template v-else>
      <div v-for="s in items" :key="s.id" class="card card-pad col gap-8">
        <div class="row gap-8">
          <input type="checkbox" :checked="selected.has(s.id)" @change="toggleSelect(s.id)" />
          <strong @click="openEdit(s.id)">{{ s.employee_name }}</strong>
          <span class="muted">{{ s.employment_type === 'part_time' ? '알바' : '직원' }}</span>
          <span class="muted" style="margin-left: auto">{{ formatDate(s.business_date) }}</span>
        </div>
        <div @click="openEdit(s.id)" class="row gap-12 muted numeric" style="font-size: 14px">
          <span>{{ s.store_name }}</span>
          <span>{{ formatTime(s.check_in) }} ~ {{ s.check_out ? formatTime(s.check_out) : '근무 중' }}</span>
          <span>{{ formatDuration(s.minutes) }}</span>
        </div>
        <FlagBadges :flags="s.flags" :reviewed="s.reviewed" />
        <div class="row gap-8">
          <button class="btn btn-secondary btn-sm grow" @click="openEdit(s.id)">수정</button>
          <button class="btn btn-ghost btn-sm grow" @click="markReviewed([s.id])">확인 완료</button>
        </div>
      </div>
    </template>

    <ShiftEditPanel v-model="panelOpen" :shift-id="activeShiftId" @saved="load" />
  </div>
</template>
