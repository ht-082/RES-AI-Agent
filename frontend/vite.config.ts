import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Windows 호스트를 도커 볼륨으로 마운트하면 파일 변경 이벤트가 컨테이너로 전달되지
    // 않아 HMR이 동작하지 않는다(코드를 고쳐도 브라우저는 옛 코드를 계속 사용).
    // 폴링으로 감시해야 변경이 반영된다.
    watch: {
      usePolling: true,
      interval: 300,
    },
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
        // SSE 스트리밍 응답이 프록시에 모여 있다가 한꺼번에 오지 않도록 버퍼링을 끈다
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            if (String(proxyRes.headers['content-type'] || '').includes('text/event-stream')) {
              proxyRes.headers['cache-control'] = 'no-cache, no-transform'
            }
          })
        },
      },
    },
  },
})
