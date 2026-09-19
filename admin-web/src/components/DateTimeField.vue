<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: null }, // ISO datetime string (UTC) or null
  label: { type: String, default: '' },
  allowEmpty: { type: Boolean, default: false },
  emptyLabel: { type: String, default: '근무 중' },
})
const emit = defineEmits(['update:modelValue'])

function toLocalParts(iso) {
  if (!iso) return { date: '', time: '' }
  const d = new Date(iso)
  const kst = new Date(d.toLocaleString('en-US', { timeZone: 'Asia/Seoul' }))
  const pad = (n) => String(n).padStart(2, '0')
  return {
    date: `${kst.getFullYear()}-${pad(kst.getMonth() + 1)}-${pad(kst.getDate())}`,
    time: `${pad(kst.getHours())}:${pad(kst.getMinutes())}`,
  }
}

const parts = computed(() => toLocalParts(props.modelValue))

function emitFromParts(dateStr, timeStr) {
  if (!dateStr || !timeStr) {
    emit('update:modelValue', null)
    return
  }
  // KST 벽시계 -> UTC ISO 변환
  const [y, m, d] = dateStr.split('-').map(Number)
  const [hh, mm] = timeStr.split(':').map(Number)
  const asKstString = `${dateStr}T${timeStr}:00+09:00`
  const utcDate = new Date(asKstString)
  emit('update:modelValue', utcDate.toISOString())
}

function onDateChange(e) {
  emitFromParts(e.target.value, parts.value.time || '09:00')
}
function onTimeChange(e) {
  emitFromParts(parts.value.date || new Date().toISOString().slice(0, 10), e.target.value)
}
function clear() {
  emit('update:modelValue', null)
}
</script>

<template>
  <div class="field">
    <label v-if="label">{{ label }}</label>
    <div class="row gap-8">
      <input type="date" class="input datetime-date" :value="parts.date" @change="onDateChange" />
      <input type="time" class="input datetime-time" :value="parts.time" @change="onTimeChange" />
      <button v-if="allowEmpty && modelValue" type="button" class="btn btn-ghost btn-sm" @click="clear">
        {{ emptyLabel }}로
      </button>
    </div>
    <span v-if="allowEmpty && !modelValue" class="hint">{{ emptyLabel }}</span>
  </div>
</template>

<style scoped>
.datetime-date { flex: 1.3; }
.datetime-time { flex: 1; font-variant-numeric: tabular-nums; font-size: 18px; font-weight: 700; text-align: center; }
</style>
