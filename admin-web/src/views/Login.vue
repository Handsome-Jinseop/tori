<script setup>
import { startAuthentication, startRegistration } from '@simplewebauthn/browser'
import QRCode from 'qrcode'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { authApi } from '../api'
import { useIsMobile } from '../composables/useMediaQuery'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const isMobile = useIsMobile()

const mode = ref('idle') // idle | recovery | show-codes
const status = ref('') // '', 'pending', 'error'
const errorMessage = ref('')
const recoveryCode = ref('')
const recoveryCodes = ref(null)
const qrDataUrl = ref('')
let qrPollTimer = null

async function afterLoggedIn() {
  await auth.refreshMe()
  router.push('/dashboard')
}

async function handlePasskeyLogin() {
  status.value = 'pending'
  errorMessage.value = ''
  try {
    const { options } = await authApi.loginOptions()
    const credential = await startAuthentication({ optionsJSON: options })
    await authApi.loginVerify(credential)
    await afterLoggedIn()
  } catch (e) {
    status.value = 'error'
    errorMessage.value = '로그인하지 못했어요. 다시 시도해 주세요.'
  }
}

async function handleFirstRegister() {
  status.value = 'pending'
  errorMessage.value = ''
  try {
    const { options } = await authApi.registerOptions()
    const credential = await startRegistration({ optionsJSON: options })
    const res = await authApi.registerVerify(credential, isMobile.value ? '내 폰' : '이 컴퓨터')
    if (res.recovery_codes) {
      recoveryCodes.value = res.recovery_codes
      mode.value = 'show-codes'
      status.value = ''
      return
    }
    await afterLoggedIn()
  } catch (e) {
    status.value = 'error'
    errorMessage.value = '등록하지 못했어요. 다시 시도해 주세요.'
  }
}

async function handleRecoveryLogin() {
  status.value = 'pending'
  errorMessage.value = ''
  try {
    await authApi.recoveryLogin(recoveryCode.value.trim())
    await afterLoggedIn()
  } catch (e) {
    status.value = 'error'
    errorMessage.value = '복구 코드가 올바르지 않아요.'
  }
}

async function startQr() {
  const { request_id } = await authApi.qrStart()
  const url = `${location.origin}/auth/approve/${request_id}`
  qrDataUrl.value = await QRCode.toDataURL(url, { margin: 1, width: 220, color: { dark: '#2E2A24', light: '#FFFDF7' } })
  qrPollTimer = setInterval(async () => {
    try {
      const res = await authApi.qrStatus(request_id)
      if (res.status === 'approved') {
        clearInterval(qrPollTimer)
        await afterLoggedIn()
      }
    } catch {
      // keep polling
    }
  }, 2000)
}

async function finishSetupWithCodes() {
  await auth.refreshMe()
  router.push('/dashboard')
}

onMounted(() => {
  if (!isMobile.value && !auth.setupRequired) {
    startQr()
  }
})
onBeforeUnmount(() => qrPollTimer && clearInterval(qrPollTimer))
</script>

<template>
  <div class="login-page">
    <div class="login-card card">
      <div class="brand-mark-lg">출</div>
      <h1 class="display" style="font-size: 30px">출퇴근·급여 관리</h1>

      <template v-if="mode === 'show-codes'">
        <p class="muted" style="text-align: center">
          복구 코드예요. 폰을 잃어버렸을 때 로그인할 수 있어요. 지금 한 번만 보여드려요 — 안전한 곳에 저장해 주세요.
        </p>
        <div class="recovery-list">
          <span v-for="c in recoveryCodes" :key="c" class="numeric">{{ c }}</span>
        </div>
        <button class="btn btn-secondary btn-block" @click="navigator.clipboard?.writeText(recoveryCodes.join('\n'))">
          복사
        </button>
        <button class="btn btn-primary btn-block btn-lg" @click="finishSetupWithCodes">시작하기</button>
      </template>

      <template v-else-if="auth.setupRequired">
        <p class="muted" style="text-align: center">
          아직 관리자 계정이 없어요. 이 기기의 지문·얼굴 인증으로 사장님 계정을 만들어요.
        </p>
        <button class="btn btn-primary btn-block btn-lg" :disabled="status === 'pending'" @click="handleFirstRegister">
          패스키로 계정 만들기
        </button>
        <p v-if="errorMessage" class="input-error" style="text-align: center">{{ errorMessage }}</p>
      </template>

      <template v-else-if="mode === 'recovery'">
        <div class="field">
          <label>복구 코드</label>
          <input class="input" v-model="recoveryCode" placeholder="xxxx-xxxx-xxxx" />
        </div>
        <button class="btn btn-primary btn-block btn-lg" :disabled="!recoveryCode || status === 'pending'" @click="handleRecoveryLogin">
          로그인
        </button>
        <p v-if="errorMessage" class="input-error" style="text-align: center">{{ errorMessage }}</p>
        <button class="btn btn-ghost btn-block" @click="mode = 'idle'; errorMessage = ''">뒤로</button>
      </template>

      <template v-else>
        <button class="btn btn-primary btn-block btn-lg" :disabled="status === 'pending'" @click="handlePasskeyLogin">
          패스키로 로그인
        </button>
        <p v-if="status === 'pending'" class="muted" style="text-align: center">폰에서 승인해 주세요…</p>
        <p v-if="errorMessage" class="input-error" style="text-align: center">{{ errorMessage }}</p>

        <div v-if="!isMobile" class="qr-area">
          <img v-if="qrDataUrl" :src="qrDataUrl" alt="QR 로그인" width="160" height="160" />
          <p class="muted" style="font-size: 13px">폰으로 QR을 스캔해 승인하세요</p>
        </div>

        <button class="btn btn-ghost btn-block" @click="mode = 'recovery'">복구 코드로 로그인</button>
      </template>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg);
  padding: 20px;
}
.login-card {
  width: 100%;
  max-width: 380px;
  padding: 36px 28px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}
.brand-mark-lg {
  width: 64px; height: 64px; border-radius: 20px; background: var(--accent);
  color: var(--accent-ink); display: flex; align-items: center; justify-content: center;
  font-family: var(--font-display); font-size: 30px;
}
.qr-area { display: flex; flex-direction: column; align-items: center; gap: 8px; padding-top: 8px; }
.recovery-list {
  width: 100%;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  background: var(--surface-alt);
  border-radius: var(--radius-md);
  padding: 14px;
}
.recovery-list span { text-align: center; font-size: 14px; }
</style>
