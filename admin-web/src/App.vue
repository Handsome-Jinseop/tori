<script setup>
import { useRoute } from 'vue-router'
import AppShell from './components/AppShell.vue'
import Toast from './components/Toast.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'

const route = useRoute()
</script>

<template>
  <template v-if="route.meta.public">
    <router-view />
  </template>
  <AppShell v-else />
  <Toast />
  <ConfirmDialog />
</template>
