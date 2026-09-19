import { api, qs } from './client'

export const authApi = {
  state: () => api.get('/api/admin/auth/state'),
  me: () => api.get('/api/admin/auth/me'),
  logout: () => api.post('/api/admin/auth/logout'),
  registerOptions: () => api.get('/api/admin/auth/register/options'),
  registerVerify: (credential, device_name) =>
    api.post('/api/admin/auth/register/verify', { credential, device_name }),
  loginOptions: () => api.get('/api/admin/auth/login/options'),
  loginVerify: (credential) => api.post('/api/admin/auth/login/verify', { credential }),
  recoveryLogin: (code) => api.post('/api/admin/auth/recovery/login', { code }),
  recoveryRegenerate: () => api.post('/api/admin/auth/recovery/regenerate'),
  deletePasskey: (credentialId) => api.del(`/api/admin/auth/passkeys/${encodeURIComponent(credentialId)}`),
  qrStart: () => api.post('/api/admin/auth/qr/start'),
  qrStatus: (id) => api.get(`/api/admin/auth/qr/${id}/status`),
  qrApprove: (id) => api.post(`/api/admin/auth/qr/${id}/approve`),
}

export const dashboardApi = {
  get: (storeId) => api.get(`/api/admin/dashboard${qs({ store_id: storeId })}`),
}

export const storesApi = {
  list: () => api.get('/api/admin/stores'),
  create: (body) => api.post('/api/admin/stores', body),
  update: (id, body) => api.put(`/api/admin/stores/${id}`, body),
}

export const employeesApi = {
  list: (params) => api.get(`/api/admin/employees${qs(params)}`),
  get: (id) => api.get(`/api/admin/employees/${id}`),
  create: (body) => api.post('/api/admin/employees', body),
  update: (id, body) => api.put(`/api/admin/employees/${id}`, body),
  resign: (id) => api.post(`/api/admin/employees/${id}/resign`),
  payRates: (id) => api.get(`/api/admin/employees/${id}/pay-rates`),
  changePayRate: (id, body) => api.post(`/api/admin/employees/${id}/pay-rates`, body),
  previewPayRate: (id, hourlyWage) =>
    api.get(`/api/admin/employees/${id}/pay-rates/preview${qs({ hourly_wage: hourlyWage })}`),
  assignments: (id) => api.get(`/api/admin/employees/${id}/assignments`),
  transfer: (id, body) => api.post(`/api/admin/employees/${id}/transfer`, body),
  cancelAssignment: (id, assignmentId) => api.del(`/api/admin/employees/${id}/assignments/${assignmentId}`),
}

export const employeeRequestsApi = {
  list: (status) => api.get(`/api/admin/employee-requests${qs({ status })}`),
  accept: (id, body) => api.post(`/api/admin/employee-requests/${id}/accept`, body),
  link: (id, employeeId) => api.post(`/api/admin/employee-requests/${id}/link`, { employee_id: employeeId }),
  reject: (id, reason) => api.post(`/api/admin/employee-requests/${id}/reject`, { reason }),
}

export const ratesApi = {
  minWages: () => api.get('/api/admin/min-wages'),
  addMinWage: (body) => api.post('/api/admin/min-wages', body),
  insuranceRates: () => api.get('/api/admin/insurance-rates'),
  addInsuranceRate: (body) => api.post('/api/admin/insurance-rates', body),
}

export const holidaysApi = {
  list: (year) => api.get(`/api/admin/holidays${qs({ year })}`),
  upsert: (body) => api.post('/api/admin/holidays', body),
  remove: (date) => api.del(`/api/admin/holidays/${date}`),
}

export const devicesApi = {
  list: () => api.get('/api/admin/devices'),
  issueCode: (body) => api.post('/api/admin/devices/codes', body),
  rename: (id, name) => api.put(`/api/admin/devices/${id}/name`, { name }),
  deactivate: (id) => api.post(`/api/admin/devices/${id}/deactivate`),
}

export const enrollmentsApi = {
  list: (status) => api.get(`/api/admin/enrollments${qs({ status })}`),
  approve: (id) => api.post(`/api/admin/enrollments/${id}/approve`),
  reject: (id, reason) => api.post(`/api/admin/enrollments/${id}/reject`, { reason }),
  revoke: (id) => api.post(`/api/admin/enrollments/${id}/revoke`),
}

export const shiftsApi = {
  list: (params) => api.get(`/api/admin/shifts${qs(params)}`),
  get: (id) => api.get(`/api/admin/shifts/${id}`),
  update: (id, body) => api.put(`/api/admin/shifts/${id}`, body),
  create: (body) => api.post('/api/admin/shifts', body),
  remove: (id) => api.del(`/api/admin/shifts/${id}`),
  review: (ids) => api.post('/api/admin/shifts/review', { ids }),
}

export const payItemsApi = {
  list: (params) => api.get(`/api/admin/pay-items${qs(params)}`),
  create: (body) => api.post('/api/admin/pay-items', body),
  update: (id, body) => api.put(`/api/admin/pay-items/${id}`, body),
  remove: (id) => api.del(`/api/admin/pay-items/${id}`),
}

export const payrollsApi = {
  currentPeriod: () => api.get('/api/admin/payrolls/current-period'),
  needsReview: (periodStart, periodEnd) =>
    api.get(`/api/admin/payrolls/needs-review${qs({ period_start: periodStart, period_end: periodEnd })}`),
  get: (periodStart, periodEnd) =>
    api.get(`/api/admin/payrolls${qs({ period_start: periodStart, period_end: periodEnd })}`),
  run: (periodStart, periodEnd) => api.post('/api/admin/payrolls/run', { period_start: periodStart, period_end: periodEnd }),
  confirm: (periodStart, periodEnd) => api.post('/api/admin/payrolls/confirm', { period_start: periodStart, period_end: periodEnd }),
  reopen: (periodStart, periodEnd) => api.post('/api/admin/payrolls/reopen', { period_start: periodStart, period_end: periodEnd }),
  updateOverrides: (employeeId, body) => api.put(`/api/admin/payrolls/${employeeId}/overrides`, body),
  csvUrl: (periodStart, periodEnd) => `/api/admin/payrolls/${periodStart}/${periodEnd}/csv`,
}

export const reportsApi = {
  hours: (params) => api.get(`/api/admin/reports/hours${qs(params)}`),
  stores: (periodStart, periodEnd) =>
    api.get(`/api/admin/reports/stores${qs({ period_start: periodStart, period_end: periodEnd })}`),
  storesCsvUrl: (periodStart, periodEnd) => `/api/admin/reports/stores/${periodStart}/${periodEnd}/csv`,
}

export const settingsApi = {
  get: () => api.get('/api/admin/settings'),
  update: (body) => api.put('/api/admin/settings', body),
}

export const auditLogsApi = {
  list: (params) => api.get(`/api/admin/audit-logs${qs(params)}`),
}
