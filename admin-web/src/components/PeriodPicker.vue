<script setup>
import { computed, ref, watch } from 'vue'
import { periodBounds, shiftPeriod } from '../utils/period'

const props = defineProps({
  modelValue: { type: Object, required: true }, // { start, end }
  startDay: { type: Number, default: 1 },
})
const emit = defineEmits(['update:modelValue'])

const thisPeriod = computed(() => periodBounds(new Date(), props.startDay))
const lastPeriod = computed(() => shiftPeriod(new Date(), props.startDay, -1))

const preset = ref('this')
const customStart = ref(props.modelValue.start)
const customEnd = ref(props.modelValue.end)

function choose(kind) {
  preset.value = kind
  if (kind === 'this') emit('update:modelValue', { ...thisPeriod.value })
  else if (kind === 'last') emit('update:modelValue', { ...lastPeriod.value })
  else emit('update:modelValue', { start: customStart.value, end: customEnd.value })
}

watch([customStart, customEnd], () => {
  if (preset.value === 'custom' && customStart.value && customEnd.value) {
    emit('update:modelValue', { start: customStart.value, end: customEnd.value })
  }
})
</script>

<template>
  <div class="period-picker">
    <div class="chip-row">
      <button class="chip" :class="{ active: preset === 'this' }" @click="choose('this')">이번 달</button>
      <button class="chip" :class="{ active: preset === 'last' }" @click="choose('last')">지난 달</button>
      <button class="chip" :class="{ active: preset === 'custom' }" @click="choose('custom')">직접 지정</button>
    </div>
    <div v-if="preset === 'custom'" class="row gap-8" style="margin-top: 8px">
      <input type="date" class="input" v-model="customStart" />
      <span class="muted">~</span>
      <input type="date" class="input" v-model="customEnd" />
    </div>
  </div>
</template>
