<script setup>
import { onMounted, ref, watch } from 'vue'
import { enrollmentsApi } from '../api'
import EmptyState from '../components/EmptyState.vue'
import Skeleton from '../components/Skeleton.vue'
import { formatDateTime } from '../composables/useFormat'
import { useUiStore } from '../stores/ui'

const ui = useUiStore()
const tab = ref('pending')
const items = ref([])
const loading = ref(true)

async function load() {
  loading.value = true
  try {
    items.value = await enrollmentsApi.list(tab.value)
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(tab, load)

async function approve(e) {
  await enrollmentsApi.approve(e.id)
  ui.toast('승인했어요.')
  await load()
}
async function reject(e) {
  const ok = await ui.confirm({ title: '얼굴 등록을 거절할까요?', message: `${e.employee_name}님의 등록 요청을 거절해요.`, confirmLabel: '거절', danger: true })
  if (!ok) return
  await enrollmentsApi.reject(e.id, '')
  ui.toast('거절했어요.')
  await load()
}
async function revoke(e) {
  const ok = await ui.confirm({ title: '얼굴 등록을 해제할까요?', message: '해제하면 폰이 다음 동기화 때 이 직원의 얼굴 데이터를 삭제해요.', confirmLabel: '해제', danger: true })
  if (!ok) return
  await enrollmentsApi.revoke(e.id)
  ui.toast('해제했어요.')
  await load()
}
</script>

<template>
  <div class="col gap-20">
    <h1 class="display" style="font-size: 26px">얼굴 등록 승인</h1>
    <p class="hint">목록에 이름이 없어서 온 신규 직원 요청은 이 화면이 아니라 대시보드의 신규 직원 요청 카드에서 처리해요.</p>

    <div class="chip-row">
      <button class="chip" :class="{ active: tab === 'pending' }" @click="tab = 'pending'">승인 대기</button>
      <button class="chip" :class="{ active: tab === 'completed' }" @click="tab = 'completed'">처리 완료</button>
    </div>

    <Skeleton v-if="loading" :rows="5" />
    <EmptyState v-else-if="!items.length" :message="tab === 'pending' ? '대기 중인 등록이 없어요.' : '처리한 기록이 없어요.'" />

    <table v-else class="data-table card">
      <thead><tr><th>직원</th><th>매장(기기)</th><th>요청 시각</th><th>종류</th><th></th></tr></thead>
      <tbody>
        <tr v-for="e in items" :key="e.id">
          <td>{{ e.employee_name }}</td>
          <td>{{ e.store_name }} ({{ e.device_name }})</td>
          <td class="numeric">{{ formatDateTime(e.requested_at) }}</td>
          <td>{{ e.is_reenroll ? '재등록' : '신규' }}</td>
          <td class="row gap-8">
            <template v-if="tab === 'pending'">
              <button class="btn btn-primary btn-sm" @click="approve(e)">승인</button>
              <button class="btn btn-ghost btn-sm" @click="reject(e)">거절</button>
            </template>
            <button v-else-if="e.status === 'approved'" class="btn btn-ghost btn-sm" @click="revoke(e)">해제</button>
            <span v-else class="muted">해제됨</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
