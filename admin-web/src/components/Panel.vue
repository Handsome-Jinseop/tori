<script setup>
import { useIsMobile } from '../composables/useMediaQuery'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  wide: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])
const isMobile = useIsMobile()

function close() {
  emit('update:modelValue', false)
}
</script>

<template>
  <transition name="panel-fade">
    <div v-if="modelValue" class="panel-overlay" @click.self="close">
      <transition :name="isMobile ? 'sheet-slide' : 'panel-slide'">
        <div v-if="modelValue" class="panel" :class="{ mobile: isMobile, wide }">
          <div class="panel-header">
            <h3 class="display">{{ title }}</h3>
            <button class="btn btn-ghost btn-sm" @click="close">닫기</button>
          </div>
          <div class="panel-body scrollbar-thin">
            <slot />
          </div>
          <div v-if="$slots.footer" class="panel-footer">
            <slot name="footer" />
          </div>
        </div>
      </transition>
    </div>
  </transition>
</template>

<style scoped>
.panel-overlay {
  position: fixed;
  inset: 0;
  background: rgba(46, 42, 36, 0.32);
  z-index: 800;
  display: flex;
  justify-content: flex-end;
}
.panel {
  background: var(--surface);
  width: 440px;
  max-width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-pop);
}
.panel.wide { width: 620px; }
.panel.mobile {
  width: 100%;
  height: auto;
  max-height: 88vh;
  margin-top: auto;
  border-radius: var(--radius-xl) var(--radius-xl) 0 0;
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px;
  border-bottom: 1px solid var(--border-soft);
  flex: none;
}
.panel-body { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px; }
.panel-footer {
  flex: none;
  padding: 16px 20px;
  border-top: 1px solid var(--border-soft);
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.panel-fade-enter-active, .panel-fade-leave-active { transition: opacity 0.2s ease; }
.panel-fade-enter-from, .panel-fade-leave-to { opacity: 0; }
.panel-slide-enter-active, .panel-slide-leave-active { transition: transform 0.25s ease; }
.panel-slide-enter-from, .panel-slide-leave-to { transform: translateX(100%); }
.sheet-slide-enter-active, .sheet-slide-leave-active { transition: transform 0.25s ease; }
.sheet-slide-enter-from, .sheet-slide-leave-to { transform: translateY(100%); }
</style>
