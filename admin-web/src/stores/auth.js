import { defineStore } from 'pinia'
import { authApi } from '../api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    admin: null,
    setupRequired: false,
    checked: false,
    loading: true,
  }),
  getters: {
    isAuthenticated: (state) => !!state.admin,
  },
  actions: {
    async bootstrap() {
      this.loading = true
      try {
        const state = await authApi.state()
        this.setupRequired = state.setup_required
        if (!this.setupRequired) {
          try {
            this.admin = await authApi.me()
          } catch {
            this.admin = null
          }
        }
      } finally {
        this.checked = true
        this.loading = false
      }
    },
    async refreshMe() {
      try {
        this.admin = await authApi.me()
      } catch {
        this.admin = null
      }
    },
    async logout() {
      await authApi.logout()
      this.admin = null
    },
  },
})
