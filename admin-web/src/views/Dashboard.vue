<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { dashboardApi, enrollmentsApi } from '../api'
import EmptyState from '../components/EmptyState.vue'
import NewEmployeeRequestDialog from '../components/NewEmployeeRequestDialog.vue'
import Skeleton from '../components/Skeleton.vue'
import StoreChips from '../components/StoreChips.vue'
import { formatDate, formatDateTime, formatTime, relativeFromNow } from '../composables/useFormat'
import { useCatalogStore } from '../stores/catalog'
import { useUiStore } from '../stores/ui'

const catalog = useCatalogStore()
const ui = useUiStore()
const router = useRouter()

const data = ref(null)
const loading = ref(true)
const dialogOpen = ref(false)
const dialogMode = ref('accept')
const dialogRequest = ref(null)

async function load() {
  loading.value = true
  try {
    await catalog.load()
    data.value = await dashboardApi.get(catalog.selectedStoreId)
  } finally {
    loading.value = false
  }
}

function openRequestDialog(request, mode) {
  dialogRequest.value = request
  dialogMode.value = mode
  dialogOpen.value = true
}

async function approveEnrollment(enrollment) {
  await enrollmentsApi.approve(enrollment.id)
  ui.toast('승인했어요.')
  await load()
}

async function rejectEnrollment(enrollment) {
  const ok = await ui.confirm({
    title: '얼굴 등록을 거절할까요?',
    message: `${enrollment.employee_name}님의 등록 요청을 거절해요.`,
    confirmLabel: '거절',
    danger: true,
  })
  if (!ok) return
  await enrollmentsApi.reject(enrollment.id, '')
  ui.toast('거절했어요.')
  await load()
}

onMounted(load)
</script>

<template>
  <div class="col gap-24">
    <div class="row gap-16" style="justify-content: space-between; flex-wrap: wrap">
      <div class="col gap-4">
        <h1 class="display" style="font-size: 26px">대시보드</h1>
        <span class="muted">{{ data ? formatDate(data.date) : '' }}</span>
      </div>
      <StoreChips v-if="catalog.loaded" v-model="catalog.selectedStoreId" :stores="catalog.stores" @update:model-value="load" />
    </div>

    <Skeleton v-if="loading" :rows="6" height="90px" />

    <template v-else-if="data">
      <div v-for="w in data.device_warnings" :key="w.device_id" class="card card-pad row gap-12" style="background: var(--caution-bg); border-color: transparent">
        <span style="color: var(--caution-fg); font-weight: 700">
          {{ w.store_name }} 폰이 {{ w.minutes_since_sync != null ? `${Math.floor(w.minutes_since_sync / 60)}시간 넘게` : '오래' }} 연결되지 않았어요
        </span>
        <button class="btn btn-secondary btn-sm" style="margin-left: auto" @click="router.push('/devices')">기기 관리로 이동</button>
      </div>

      <div class="grid-2">
        <div class="card card-pad col gap-12">
          <h3 class="display">신규 직원 요청 {{ data.employee_requests.length ? `${data.employee_requests.length}건` : '' }}</h3>
          <EmptyState v-if="!data.employee_requests.length" message="새 요청이 없어요." />
          <div v-for="r in data.employee_requests" :key="r.id" class="request-row">
            <div class="col gap-4 grow">
              <strong>{{ r.name }}</strong>
              <span class="muted" style="font-size: 13px">{{ r.store_name }} · {{ relativeFromNow(r.created_at) }} · 기록 {{ r.shift_count }}건</span>
            </div>
            <div class="row gap-8">
              <button class="btn btn-primary btn-sm" @click="openRequestDialog(r, 'accept')">수락</button>
              <button class="btn btn-secondary btn-sm" @click="openRequestDialog(r, 'link')">연결</button>
              <button class="btn btn-ghost btn-sm" @click="openRequestDialog(r, 'reject')">거절</button>
            </div>
          </div>
        </div>

        <div class="card card-pad col gap-12">
          <h3 class="display">얼굴 등록 승인 대기 {{ data.enrollments_pending.length ? `${data.enrollments_pending.length}건` : '' }}</h3>
          <EmptyState v-if="!data.enrollments_pending.length" message="대기 중인 등록이 없어요." />
          <div v-for="e in data.enrollments_pending" :key="e.id" class="request-row">
            <div class="col gap-4 grow">
              <strong>{{ e.employee_name }} <span v-if="e.is_reenroll" class="muted" style="font-size: 12px">(재등록)</span></strong>
              <span class="muted" style="font-size: 13px">{{ e.store_name }} · {{ relativeFromNow(e.requested_at) }}</span>
            </div>
            <div class="row gap-8">
              <button class="btn btn-primary btn-sm" @click="approveEnrollment(e)">승인</button>
              <button class="btn btn-ghost btn-sm" @click="rejectEnrollment(e)">거절</button>
            </div>
          </div>
        </div>
      </div>

      <div class="card card-pad col gap-12">
        <div class="row" style="justify-content: space-between">
          <div class="col">
            <span class="muted">확인 필요</span>
            <span class="display" style="font-size: 34px">{{ data.needs_review_count }}건</span>
          </div>
          <button class="btn btn-secondary" @click="router.push('/shifts/review')">확인하러 가기</button>
        </div>
        <EmptyState v-if="!data.needs_review_count" message="확인할 근무가 없어요. 모두 정상이에요." />
        <div v-else class="chip-row">
          <span v-for="f in data.needs_review_by_flag" :key="f.flag" class="chip" style="cursor: default">
            {{ f.label }} {{ f.count }}
          </span>
        </div>
      </div>

      <div class="grid-3">
        <div v-for="s in data.stores" :key="s.store_id" class="card card-pad col gap-10">
          <div class="row" style="justify-content: space-between">
            <strong>{{ s.name }}</strong>
            <span class="muted" style="font-size: 13px">{{ s.last_sync ? relativeFromNow(s.last_sync) : '연결 기록 없음' }}</span>
          </div>
          <span class="display" style="font-size: 24px">{{ s.working_count }}명 근무 중</span>
          <div class="col gap-4">
            <div v-for="w in s.working" :key="w.employee_id" class="row" style="justify-content: space-between; font-size: 14px">
              <span>{{ w.name }}</span>
              <span class="muted numeric">{{ formatTime(w.check_in) }}부터</span>
            </div>
          </div>
        </div>
      </div>
    </template>

    <NewEmployeeRequestDialog
      v-model="dialogOpen"
      :request="dialogRequest"
      :mode="dialogMode"
      @done="load"
    />
  </div>
</template>

<style scoped>
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.request-row { display: flex; align-items: center; gap: 10px; padding: 10px 0; border-top: 1px solid var(--border-soft); flex-wrap: wrap; }
.request-row:first-of-type { border-top: none; }
@media (max-width: 900px) {
  .grid-2, .grid-3 { grid-template-columns: 1fr; }
}
</style>
