<script setup>
import { startAuthentication } from '@simplewebauthn/browser'
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { authApi } from '../api'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const auth = useAuthStore()
const state = ref('checking') // checking | need-login | approving | done | error

async function approve() {
  state.value = 'approving'
  try {
    await authApi.qrApprove(route.params.id)
    state.value = 'done'
  } catch {
    state.value = 'error'
  }
}

async function loginThenApprove() {
  try {
    const { options } = await authApi.loginOptions()
    const credential = await startAuthentication({ optionsJSON: options })
    await authApi.loginVerify(credential)
    await auth.refreshMe()
    await approve()
  } catch {
    state.value = 'error'
  }
}

onMounted(async () => {
  if (!auth.checked) await auth.bootstrap()
  if (auth.isAuthenticated) {
    await approve()
  } else {
    state.value = 'need-login'
  }
})
</script>

<template>
  <div class="qr-approve-page">
    <div class="card" style="padding: 32px; max-width: 360px; width: 100%; text-align: center">
      <h2 class="display">PC 로그인 승인</h2>
      <p v-if="state === 'checking' || state === 'approving'" class="muted">확인하고 있어요…</p>
      <template v-if="state === 'need-login'">
        <p class="muted">이 폰의 지문·얼굴 인증으로 PC 로그인을 승인해요.</p>
        <button class="btn btn-primary btn-block btn-lg" @click="loginThenApprove">패스키로 승인</button>
      </template>
      <p v-if="state === 'done'" class="muted">승인했어요. PC 화면을 확인해 주세요.</p>
      <p v-if="state === 'error'" class="input-error">승인하지 못했어요. 다시 시도해 주세요.</p>
    </div>
  </div>
</template>

<style scoped>
.qr-approve-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg);
  padding: 20px;
}
</style>
