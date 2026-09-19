import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      workbox: {
        // 화면 뼈대(정적 파일)만 캐시하고, 근무·급여 데이터는 항상 서버에서 최신 값을 가져옵니다.
        navigateFallbackDenylist: [/^\/api\//],
        runtimeCaching: [],
      },
      manifest: {
        name: '출퇴근·급여 관리',
        short_name: '출퇴근·급여',
        description: '식당 직원 출퇴근·급여 관리 시스템 관리자 웹앱',
        theme_color: '#F5C542',
        background_color: '#F4EFE3',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
        ],
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
