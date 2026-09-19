<script setup>
import { useUiStore } from '../stores/ui'

const ui = useUiStore()
</script>

<template>
  <div class="toast-stack">
    <transition-group name="toast">
      <div v-for="t in ui.toasts" :key="t.id" class="toast">{{ t.message }}</div>
    </transition-group>
  </div>
</template>

<style scoped>
.toast-stack {
  position: fixed;
  left: 50%;
  bottom: 28px;
  transform: translateX(-50%);
  z-index: 900;
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
  pointer-events: none;
}
.toast {
  background: var(--text);
  color: var(--surface);
  padding: 12px 20px;
  border-radius: var(--radius-pill);
  font-size: 14px;
  font-weight: 600;
  box-shadow: var(--shadow-pop);
}
.toast-enter-active, .toast-leave-active { transition: all 0.25s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(10px); }
</style>
