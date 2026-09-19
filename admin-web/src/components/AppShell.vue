<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useIsMobile } from '../composables/useMediaQuery'
import { useAuthStore } from '../stores/auth'
import { useCatalogStore } from '../stores/catalog'
import { payrollsApi } from '../api'
import { periodBounds } from '../utils/period'
import StoreChips from './StoreChips.vue'

const route = useRoute()
const isMobile = useIsMobile()
const auth = useAuthStore()
const catalog = useCatalogStore()

const reviewCount = ref(0)

async function loadReviewCount() {
  try {
    await catalog.load()
    const { start, end } = periodBounds(new Date(), catalog.startDay)
    const res = await payrollsApi.needsReview(start, end)
    reviewCount.value = res.count
  } catch {
    reviewCount.value = 0
  }
}

onMounted(loadReviewCount)
watch(() => route.fullPath, loadReviewCount)

const navGroups = computed(() => [
  { label: '대시보드', items: [{ label: '대시보드', to: '/dashboard' }] },
  {
    label: '근무',
    items: [
      { label: '확인 필요', to: '/shifts/review', badge: reviewCount.value },
      { label: '근무 기록', to: '/shifts' },
      { label: '근무시간 요약', to: '/hours' },
    ],
  },
  {
    label: '정산',
    items: [
      { label: '정산', to: '/payroll' },
      { label: '매장별 리포트', to: '/reports/stores' },
      { label: '보너스·공제', to: '/pay-items' },
    ],
  },
  {
    label: '관리',
    items: [
      { label: '직원 관리', to: '/employees' },
      { label: '매장 관리', to: '/stores' },
      { label: '얼굴 등록 승인', to: '/enrollments' },
      { label: '기기 관리', to: '/devices' },
    ],
  },
  { label: '설정', items: [{ label: '설정', to: '/settings' }] },
])

const mobileTabs = [
  { label: '대시보드', to: '/dashboard', match: ['/dashboard'] },
  { label: '근무', to: '/shifts/review', match: ['/shifts/review', '/shifts', '/hours'] },
  { label: '정산', to: '/payroll', match: ['/payroll', '/reports/stores', '/pay-items'] },
  { label: '관리', to: '/employees', match: ['/employees', '/stores', '/enrollments', '/devices'] },
  { label: '설정', to: '/settings', match: ['/settings'] },
]

function isMobileTabActive(tab) {
  return tab.match.includes(route.path)
}
</script>

<template>
  <div class="shell" :class="{ mobile: isMobile }">
    <aside v-if="!isMobile" class="sidebar">
      <div class="sidebar-top">
        <div class="brand">
          <span class="brand-mark">출</span>
          <span class="display brand-name">출퇴근·급여</span>
        </div>
        <StoreChips v-if="catalog.loaded" v-model="catalog.selectedStoreId" :stores="catalog.stores" />
      </div>
      <nav class="nav">
        <div v-for="group in navGroups" :key="group.label" class="nav-group">
          <div class="nav-group-label">{{ group.label }}</div>
          <router-link
            v-for="item in group.items"
            :key="item.to"
            :to="item.to"
            class="nav-item"
            active-class="active"
          >
            <span>{{ item.label }}</span>
            <span v-if="item.badge" class="nav-badge">{{ item.badge }}</span>
          </router-link>
        </div>
      </nav>
      <div class="sidebar-bottom">
        <div class="col">
          <span style="font-weight: 700">{{ auth.admin?.display_name || '사장님' }}</span>
          <span class="muted" style="font-size: 12.5px">owner</span>
        </div>
        <button class="btn btn-ghost btn-sm" @click="auth.logout().then(() => $router.push('/login'))">
          로그아웃
        </button>
      </div>
    </aside>

    <main class="content">
      <router-view />
    </main>

    <nav v-if="isMobile" class="bottom-tabs">
      <router-link
        v-for="tab in mobileTabs"
        :key="tab.to"
        :to="tab.to"
        class="bottom-tab"
        :class="{ active: isMobileTabActive(tab) }"
      >
        {{ tab.label }}
        <span v-if="tab.label === '근무' && reviewCount" class="tab-dot" />
      </router-link>
    </nav>
  </div>
</template>

<style scoped>
.shell { display: flex; min-height: 100vh; background: var(--bg); }
.sidebar {
  width: var(--sidebar-width);
  flex: none;
  border-right: 1px solid var(--border-soft);
  display: flex;
  flex-direction: column;
  position: sticky;
  top: 0;
  height: 100vh;
}
.sidebar-top { padding: 20px 16px; display: flex; flex-direction: column; gap: 14px; border-bottom: 1px solid var(--border-soft); }
.brand { display: flex; align-items: center; gap: 10px; }
.brand-mark {
  width: 34px; height: 34px; border-radius: 12px; background: var(--accent);
  color: var(--accent-ink); display: flex; align-items: center; justify-content: center;
  font-family: var(--font-display); font-size: 18px; flex: none;
}
.brand-name { font-size: 19px; }
.nav { flex: 1; overflow-y: auto; padding: 12px 12px; }
.nav-group { margin-bottom: 14px; }
.nav-group-label { font-size: 12px; color: var(--text-faint); font-weight: 700; padding: 6px 12px; }
.nav-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 12px; border-radius: var(--radius-md); color: var(--text);
  font-weight: 600; font-size: 14.5px;
}
.nav-item:hover { background: var(--surface-alt); text-decoration: none; }
.nav-item.active { background: var(--accent-soft); color: var(--accent-ink); }
.nav-badge {
  background: var(--warning-icon); color: white; font-size: 11px; font-weight: 700;
  min-width: 18px; height: 18px; border-radius: 999px; display: flex; align-items: center; justify-content: center; padding: 0 5px;
}
.sidebar-bottom {
  padding: 14px 16px; border-top: 1px solid var(--border-soft);
  display: flex; align-items: center; justify-content: space-between;
}
.content { flex: 1; min-width: 0; padding: 28px 32px 60px; max-width: 1280px; }

.shell.mobile { flex-direction: column; }
.shell.mobile .content { padding: 16px 16px calc(var(--bottom-tab-height) + 24px); max-width: 100%; }
.bottom-tabs {
  position: fixed; bottom: 0; left: 0; right: 0; height: var(--bottom-tab-height);
  background: var(--surface); border-top: 1px solid var(--border-soft);
  display: flex; z-index: 100;
  padding-bottom: env(safe-area-inset-bottom);
}
.bottom-tab {
  flex: 1; display: flex; align-items: center; justify-content: center; position: relative;
  font-size: 12.5px; font-weight: 700; color: var(--text-muted);
}
.bottom-tab.active { color: var(--accent-ink); }
.tab-dot { position: absolute; top: 8px; right: calc(50% - 22px); width: 8px; height: 8px; border-radius: 50%; background: var(--warning-icon); }
</style>
