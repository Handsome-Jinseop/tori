<script setup>
import { computed, ref } from 'vue'
import { FLAG_META, sortFlagsBySeverity } from '../constants/flags'

const props = defineProps({
  flags: { type: Array, default: () => [] },
  reviewed: { type: Boolean, default: false },
  max: { type: Number, default: 2 },
})

const sorted = computed(() => sortFlagsBySeverity(props.flags || []))
const shown = computed(() => sorted.value.slice(0, props.max))
const overflowCount = computed(() => Math.max(0, sorted.value.length - props.max))
const showAll = ref(false)
</script>

<template>
  <span class="flag-badges" v-if="sorted.length">
    <span
      v-for="f in shown"
      :key="f"
      class="badge"
      :class="[`badge-${FLAG_META[f]?.severity || 'info'}`, { reviewed }]"
      :title="FLAG_META[f]?.label || f"
    >
      <span class="dot" />{{ FLAG_META[f]?.label || f }}
    </span>
    <span
      v-if="overflowCount > 0"
      class="badge badge-info"
      :class="{ reviewed }"
      style="cursor: pointer"
      @click.stop="showAll = !showAll"
    >
      +{{ overflowCount }}
    </span>
    <span v-if="showAll" class="flag-popover card">
      <span
        v-for="f in sorted"
        :key="f"
        class="badge"
        :class="`badge-${FLAG_META[f]?.severity || 'info'}`"
      >
        <span class="dot" />{{ FLAG_META[f]?.label || f }}
      </span>
    </span>
  </span>
  <span v-else class="faint">-</span>
</template>

<style scoped>
.flag-badges { display: inline-flex; gap: 4px; flex-wrap: wrap; position: relative; align-items: center; }
.flag-popover {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 6px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  z-index: 50;
  min-width: 160px;
}
</style>
