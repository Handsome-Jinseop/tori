import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', name: 'login', component: () => import('../views/Login.vue'), meta: { public: true } },
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'dashboard', component: () => import('../views/Dashboard.vue') },
  { path: '/shifts/review', name: 'review', component: () => import('../views/ReviewQueue.vue') },
  { path: '/shifts', name: 'shifts', component: () => import('../views/ShiftRecords.vue') },
  { path: '/hours', name: 'hours', component: () => import('../views/HoursSummary.vue') },
  { path: '/payroll', name: 'payroll', component: () => import('../views/Payroll.vue') },
  { path: '/reports/stores', name: 'store-reports', component: () => import('../views/StoreReports.vue') },
  { path: '/pay-items', name: 'pay-items', component: () => import('../views/PayItems.vue') },
  { path: '/employees', name: 'employees', component: () => import('../views/Employees.vue') },
  { path: '/stores', name: 'stores', component: () => import('../views/Stores.vue') },
  { path: '/enrollments', name: 'enrollments', component: () => import('../views/Enrollments.vue') },
  { path: '/devices', name: 'devices', component: () => import('../views/Devices.vue') },
  { path: '/settings', name: 'settings', component: () => import('../views/Settings.vue') },
  {
    path: '/auth/approve/:id',
    name: 'qr-approve',
    component: () => import('../views/QrApprove.vue'),
    meta: { public: true },
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.checked) {
    await auth.bootstrap()
  }
  if (to.meta.public) {
    if (to.name === 'login' && auth.isAuthenticated) return { name: 'dashboard' }
    return true
  }
  if (!auth.isAuthenticated) {
    return { name: 'login' }
  }
  return true
})
