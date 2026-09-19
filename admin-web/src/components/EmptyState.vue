<script setup>
defineProps({
  message: { type: String, required: true },
})
</script>

<template>
  <div class="empty-state">
    <p>{{ message }}</p>
    <slot />
  </div>
</template>
