<script setup>
import { useUiStore } from '../stores/ui'

const ui = useUiStore()
</script>

<template>
  <div v-if="ui.confirmState" class="overlay" @click.self="ui.resolveConfirm(false)">
    <div class="dialog card">
      <h3 class="display">{{ ui.confirmState.title }}</h3>
      <p class="muted">{{ ui.confirmState.message }}</p>
      <div class="row gap-8" style="justify-content: flex-end; margin-top: 8px">
        <button class="btn btn-secondary" @click="ui.resolveConfirm(false)">
          {{ ui.confirmState.cancelLabel }}
        </button>
        <button
          class="btn"
          :class="ui.confirmState.danger ? 'btn-danger' : 'btn-primary'"
          @click="ui.resolveConfirm(true)"
        >
          {{ ui.confirmState.confirmLabel }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(46, 42, 36, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}
.dialog {
  width: 100%;
  max-width: 380px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
</style>
