<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { devicesApi } from '../api'
import EmptyState from '../components/EmptyState.vue'
import Panel from '../components/Panel.vue'
import { relativeFromNow } from '../composables/useFormat'
import { useCatalogStore } from '../stores/catalog'
import { useUiStore } from '../stores/ui'

const catalog = useCatalogStore()
const ui = useUiStore()

const items = ref([])
const loading = ref(true)
const issueOpen = ref(false)
const issueStoreId = ref('')
const issueDeviceName = ref('')
const issuedCode = ref(null)
const expiresAt = ref(null)
const remainingSec = ref(0)
let timer = null
const renamingId = ref(null)
const renameValue = ref('')

async function load() {
  loading.value = true
  await catalog.load()
  try {
    items.value = await devicesApi.list()
  } finally {
    loading.value = false
  }
}
onMounted(load)
onUnmounted(() => timer && clearInterval(timer))

function openIssue() {
  issueStoreId.value = catalog.stores[0]?.id || ''
  issueDeviceName.value = ''
  issuedCode.value = null
  issueOpen.value = true
}

async function issue() {
  const res = await devicesApi.issueCode({ store_id: issueStoreId.value, device_name: issueDeviceName.value })
  issuedCode.value = res.code
  expiresAt.value = new Date(res.expires_at)
  tick()
  timer && clearInterval(timer)
  timer = setInterval(tick, 1000)
}

function tick() {
  remainingSec.value = Math.max(0, Math.floor((expiresAt.value - new Date()) / 1000))
  if (remainingSec.value <= 0 && timer) clearInterval(timer)
}

const remainingLabel = computed(() => {
  const m = Math.floor(remainingSec.value / 60)
  const s = remainingSec.value % 60
  return `${m}:${String(s).padStart(2, '0')}`
})

function copyCode() {
  navigator.clipboard?.writeText(issuedCode.value)
  ui.toast('복사했어요.')
}

function startRename(d) {
  renamingId.value = d.id
  renameValue.value = d.name
}
async function saveRename(d) {
  await devicesApi.rename(d.id, renameValue.value)
  renamingId.value = null
  await load()
}

async function deactivate(d) {
  const ok = await ui.confirm({ title: '기기를 비활성화할까요?', message: '이 폰은 더 이상 서버에 접속할 수 없어요.', confirmLabel: '비활성화', danger: true })
  if (!ok) return
  await devicesApi.deactivate(d.id)
  ui.toast('비활성화했어요.')
  await load()
}

const STATUS_LABEL = { ok: '정상', stale: '지연', inactive: '비활성화' }
const STATUS_TONE = { ok: 'success', stale: 'caution', inactive: 'neutral' }
</script>

<template>
  <div class="col gap-20">
    <div class="row gap-12" style="justify-content: space-between">
      <h1 class="display" style="font-size: 26px">기기 관리</h1>
      <button class="btn btn-primary" @click="openIssue">등록 코드 발급</button>
    </div>

    <EmptyState v-if="!loading && !items.length" message="등록된 기기가 없어요." />

    <table v-else class="data-table card">
      <thead><tr><th>기기 이름</th><th>매장</th><th>상태</th><th>마지막 접속</th><th>앱 버전</th><th></th></tr></thead>
      <tbody>
        <tr v-for="d in items" :key="d.id">
          <td>
            <template v-if="renamingId === d.id">
              <input class="input" v-model="renameValue" style="height: 34px" @keyup.enter="saveRename(d)" @blur="saveRename(d)" />
            </template>
            <template v-else>{{ d.name }}</template>
          </td>
          <td>{{ catalog.storeName(d.store_id) }}</td>
          <td>
            <span class="badge" :class="`badge-${d.status === 'ok' ? 'success' : d.status === 'stale' ? 'caution' : 'info'}`">
              <span class="dot" />{{ STATUS_LABEL[d.status] }}
            </span>
          </td>
          <td class="muted">{{ d.last_seen_at ? relativeFromNow(d.last_seen_at) : '-' }}</td>
          <td class="numeric muted">{{ d.app_version }}</td>
          <td class="row gap-8">
            <button class="btn btn-ghost btn-sm" @click="startRename(d)">이름 수정</button>
            <button v-if="d.status !== 'inactive'" class="btn btn-ghost btn-sm" @click="deactivate(d)">비활성화</button>
          </td>
        </tr>
      </tbody>
    </table>

    <Panel v-model="issueOpen" title="등록 코드 발급">
      <template v-if="!issuedCode">
        <div class="field">
          <label>매장</label>
          <select class="select" v-model="issueStoreId">
            <option v-for="s in catalog.stores" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </div>
        <div class="field"><label>기기 이름</label><input class="input" v-model="issueDeviceName" placeholder="예: 별내-폰1" /></div>
      </template>
      <template v-else>
        <div class="col gap-12" style="align-items: center; text-align: center; padding: 20px 0">
          <span class="display" style="font-size: 48px; letter-spacing: 0.1em">{{ remainingSec > 0 ? issuedCode : '만료됐어요' }}</span>
          <span v-if="remainingSec > 0" class="muted numeric">남은 시간 {{ remainingLabel }}</span>
          <button v-if="remainingSec > 0" class="btn btn-secondary" @click="copyCode">코드 복사</button>
          <button v-else class="btn btn-primary" @click="issue">새 코드 발급</button>
          <p class="hint">매장 폰의 앱에 이 코드를 입력해 주세요</p>
        </div>
      </template>
      <template #footer>
        <button class="btn btn-secondary" @click="issueOpen = false">닫기</button>
        <button v-if="!issuedCode" class="btn btn-primary" :disabled="!issueStoreId || !issueDeviceName" @click="issue">발급</button>
      </template>
    </Panel>
  </div>
</template>
