<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: [Number, null], default: null },
  placeholder: { type: String, default: '' },
  invalid: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const display = computed(() =>
  props.modelValue === null || props.modelValue === undefined ? '' : props.modelValue.toLocaleString('ko-KR')
)

function onInput(e) {
  const digits = e.target.value.replace(/[^0-9]/g, '')
  emit('update:modelValue', digits === '' ? null : Number(digits))
  e.target.value = digits === '' ? '' : Number(digits).toLocaleString('ko-KR')
}
</script>

<template>
  <div class="amount-input" :class="{ invalid }">
    <input
      class="input"
      :class="{ invalid }"
      inputmode="numeric"
      :value="display"
      :placeholder="placeholder"
      @input="onInput"
    />
    <span class="suffix">원</span>
  </div>
</template>

<style scoped>
.amount-input { position: relative; }
.amount-input .input { padding-right: 40px; text-align: right; }
.amount-input .input.invalid { border-color: var(--warning-icon); }
.amount-input .suffix {
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  font-size: 14px;
  pointer-events: none;
}
</style>
