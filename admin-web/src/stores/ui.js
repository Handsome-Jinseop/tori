import { defineStore } from 'pinia'

let toastSeq = 0

export const useUiStore = defineStore('ui', {
  state: () => ({
    toasts: [],
    confirmState: null, // { title, message, confirmLabel, cancelLabel, danger, resolve }
  }),
  actions: {
    toast(message) {
      const id = ++toastSeq
      this.toasts.push({ id, message })
      setTimeout(() => {
        this.toasts = this.toasts.filter((t) => t.id !== id)
      }, 2600)
    },
    confirm({ title, message, confirmLabel = '확인', cancelLabel = '취소', danger = false }) {
      return new Promise((resolve) => {
        this.confirmState = { title, message, confirmLabel, cancelLabel, danger, resolve }
      })
    },
    resolveConfirm(result) {
      if (this.confirmState) {
        this.confirmState.resolve(result)
        this.confirmState = null
      }
    },
  },
})
