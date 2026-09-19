import { defineStore } from 'pinia'
import { settingsApi, storesApi } from '../api'

export const useCatalogStore = defineStore('catalog', {
  state: () => ({
    stores: [],
    settings: null,
    selectedStoreId: '',
    loaded: false,
  }),
  getters: {
    startDay: (state) => state.settings?.default_period_start_day ?? 1,
    storeName: (state) => (id) => state.stores.find((s) => s.id === id)?.name ?? '-',
  },
  actions: {
    async load() {
      if (this.loaded) return
      const [stores, settings] = await Promise.all([storesApi.list(), settingsApi.get()])
      this.stores = stores
      this.settings = settings
      this.loaded = true
    },
    async refreshSettings() {
      this.settings = await settingsApi.get()
    },
    async refreshStores() {
      this.stores = await storesApi.list()
    },
  },
})
