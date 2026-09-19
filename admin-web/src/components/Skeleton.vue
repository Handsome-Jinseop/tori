<script setup>
defineProps({
  rows: { type: Number, default: 4 },
  height: { type: String, default: '52px' },
})
</script>

<template>
  <div class="col gap-8">
    <div v-for="i in rows" :key="i" class="skeleton" :style="{ height }" />
  </div>
</template>
