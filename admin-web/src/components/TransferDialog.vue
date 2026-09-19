<script setup>
import { computed, ref, watch } from 'vue'
import { employeesApi } from '../api'
import { useCatalogStore } from '../stores/catalog'
import { useUiStore } from '../stores/ui'
import { shiftPeriod } from '../utils/period'
import Panel from './Panel.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  employee: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'saved'])
const catalog = useCatalogStore()
const ui = useUiStore()

const newStoreId = ref('')
const reason = ref('')
const keepPrevious = ref(true)
const saving = ref(false)

const otherStores = computed(() => catalog.stores.filter((s) => s.id !== props.employee?.pay_store_id))
const effectiveFrom = computed(() => shiftPeriod(new Date(), catalog.startDay, 1).start)

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      newStoreId.value = otherStores.value[0]?.id || ''
      reason.value = ''
      keepPrevious.value = true
    }
  }
)

async function save() {
  if (!newStoreId.value) return
  saving.value = true
  try {
    await employeesApi.transfer(props.employee.id, {
      new_pay_store_id: newStoreId.value,
      reason: reason.value,
      keep_previous_store: keepPrevious.value,
    })
    ui.toast('이동을 예약했어요.')
    emit('update:modelValue', false)
    emit('saved')
  } catch (e) {
    ui.toast(e.message)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Panel :model-value="modelValue" @update:model-value="(v) => emit('update:modelValue', v)" :title="`${employee?.name || ''} 직원 이동`">
    <template v-if="employee">
      <p class="muted">현재 급여 관리 매장: {{ catalog.storeName(employee.pay_store_id) }}</p>

      <div class="field">
        <label>새 급여 관리 매장</label>
        <select class="select" v-model="newStoreId">
          <option v-for="s in otherStores" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
      </div>

      <div class="field">
        <label>적용일</label>
        <span class="hint">{{ effectiveFrom }}부터 적용돼요. 이동은 다음 달부터 적용됩니다.</span>
      </div>

      <div class="field">
        <label>사유</label>
        <input class="input" v-model="reason" />
      </div>

      <div class="field">
        <label>이전 매장 처리</label>
        <label class="row gap-8"><input type="radio" :value="true" v-model="keepPrevious" /> 계속 근무 가능(겸직)</label>
        <label class="row gap-8"><input type="radio" :value="false" v-model="keepPrevious" /> 근무 가능에서 제거</label>
        <p v-if="!keepPrevious" class="input-error">이전 매장 폰의 얼굴 등록이 해제되고 얼굴 데이터가 삭제돼요.</p>
      </div>

      <p class="hint">새 매장은 지금부터 근무 가능 매장에 추가돼요. 급여는 적용일부터 새 매장으로 넘어가요.</p>
    </template>

    <template #footer>
      <button class="btn btn-secondary" @click="emit('update:modelValue', false)">취소</button>
      <button class="btn btn-primary" :disabled="saving || !newStoreId" @click="save">이동 예약</button>
    </template>
  </Panel>
</template>
