<script setup>
defineProps({
  label: { type: String, required: true },
  tone: { type: String, default: 'neutral' }, // neutral | success | caution | warning | info | accent
})
</script>

<template>
  <span class="status-pill" :class="`tone-${tone}`"><span class="dot" />{{ label }}</span>
</template>

<style scoped>
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: var(--radius-pill);
}
.dot { width: 7px; height: 7px; border-radius: 50%; }
.tone-neutral { background: var(--border-soft); color: var(--text-muted); }
.tone-neutral .dot { background: var(--text-faint); }
.tone-success { background: var(--success-bg); color: var(--success-fg); }
.tone-success .dot { background: var(--success-icon); }
.tone-caution { background: var(--caution-bg); color: var(--caution-fg); }
.tone-caution .dot { background: var(--caution-icon); }
.tone-warning { background: var(--warning-bg); color: var(--warning-fg); }
.tone-warning .dot { background: var(--warning-icon); }
.tone-info { background: var(--info-bg); color: var(--info-fg); }
.tone-info .dot { background: var(--info-icon); }
.tone-accent { background: var(--accent-soft); color: var(--accent-ink); }
.tone-accent .dot { background: var(--accent-strong); }
</style>
