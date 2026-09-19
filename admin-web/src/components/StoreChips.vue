<script setup>
const props = defineProps({
  stores: { type: Array, default: () => [] },
  modelValue: { type: String, default: '' },
  includeAll: { type: Boolean, default: true },
})
const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <div class="chip-row">
    <button v-if="includeAll" class="chip" :class="{ active: modelValue === '' }" @click="emit('update:modelValue', '')">
      전체
    </button>
    <button
      v-for="s in stores"
      :key="s.id"
      class="chip"
      :class="{ active: modelValue === s.id }"
      @click="emit('update:modelValue', s.id)"
    >
      {{ s.name }}
    </button>
  </div>
</template>
