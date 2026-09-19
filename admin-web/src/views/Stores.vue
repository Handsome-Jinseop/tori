<script setup>
import { onMounted, ref } from 'vue'
import { devicesApi, employeesApi, storesApi } from '../api'
import Panel from '../components/Panel.vue'
import { useUiStore } from '../stores/ui'
import { useCatalogStore } from '../stores/catalog'

const catalog = useCatalogStore()
const ui = useUiStore()

const employeeCounts = ref({})
const deviceStatuses = ref({})
const panelOpen = ref(false)
const editing = ref(null) // null = add

function defaults() {
  return { name: '', close_time: '22:00', close_next_day: false, grace_min: 15 }
}
const form = ref(defaults())

async function load() {
  await catalog.refreshStores()
  const employees = await employeesApi.list({ active: 'true' })
  const counts = {}
  for (const e of employees) counts[e.pay_store_id] = (counts[e.pay_store_id] || 0) + 1
  employeeCounts.value = counts

  const devices = await devicesApi.list()
  const statuses = {}
  for (const d of devices) statuses[d.store_id] = d.status
  deviceStatuses.value = statuses
}

onMounted(load)

function openAdd() {
  editing.value = null
  form.value = defaults()
  panelOpen.value = true
}
function openEdit(store) {
  editing.value = store
  form.value = { name: store.name, close_time: store.close_time, close_next_day: store.close_next_day, grace_min: store.grace_min }
  panelOpen.value = true
}

async function save() {
  try {
    if (editing.value) await storesApi.update(editing.value.id, form.value)
    else await storesApi.create(form.value)
    ui.toast('저장했어요.')
    panelOpen.value = false
    await load()
  } catch (e) {
    ui.toast(e.message)
  }
}

const STATUS_LABEL = { ok: '정상', stale: '지연', inactive: '비활성화', none: '기기 없음' }
</script>

<template>
  <div class="col gap-20">
    <div class="row gap-12" style="justify-content: space-between">
      <h1 class="display" style="font-size: 26px">매장 관리</h1>
      <button class="btn btn-primary" @click="openAdd">매장 추가</button>
    </div>

    <div class="grid-3">
      <div v-for="s in catalog.stores" :key="s.id" class="card card-pad col gap-8">
        <div class="row" style="justify-content: space-between">
          <strong style="font-size: 17px">{{ s.name }}</strong>
          <button class="btn btn-secondary btn-sm" @click="openEdit(s)">수정</button>
        </div>
        <span class="muted numeric">영업 마감 {{ s.close_time }}<template v-if="s.close_next_day"> (다음날)</template></span>
        <span class="muted numeric">자동 퇴근 유예 {{ s.grace_min }}분</span>
        <span class="muted">근무 가능 직원 {{ employeeCounts[s.id] || 0 }}명</span>
        <span class="muted">폰 상태 {{ STATUS_LABEL[deviceStatuses[s.id] || 'none'] }}</span>
      </div>
    </div>

    <Panel v-model="panelOpen" :title="editing ? '매장 수정' : '매장 추가'">
      <div class="field"><label>매장 이름</label><input class="input" v-model="form.name" /></div>
      <div class="field"><label>영업 마감시각</label><input type="time" class="input" v-model="form.close_time" /></div>
      <label class="row gap-8"><input type="checkbox" v-model="form.close_next_day" /> 다음날 마감</label>
      <div class="field"><label>자동 퇴근 유예시간(분)</label><input type="number" class="input" v-model.number="form.grace_min" /></div>
      <p class="hint">마감 후 이 시간이 지나도 퇴근이 없으면 마감시각으로 자동 퇴근 처리돼요. 기록되는 퇴근 시각은 항상 마감시각이에요.</p>
      <template #footer>
        <button class="btn btn-secondary" @click="panelOpen = false">취소</button>
        <button class="btn btn-primary" @click="save">저장</button>
      </template>
    </Panel>
  </div>
</template>

<style scoped>
.grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
@media (max-width: 900px) { .grid-3 { grid-template-columns: 1fr; } }
</style>
