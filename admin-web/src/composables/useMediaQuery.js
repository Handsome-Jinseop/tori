import { onBeforeUnmount, onMounted, ref } from 'vue'

export function useMediaQuery(query) {
  const matches = ref(false)
  let mql

  onMounted(() => {
    mql = window.matchMedia(query)
    matches.value = mql.matches
    mql.addEventListener('change', update)
  })
  onBeforeUnmount(() => mql && mql.removeEventListener('change', update))

  function update(e) {
    matches.value = e.matches
  }

  return matches
}

export function useIsMobile() {
  return useMediaQuery('(max-width: 767px)')
}
