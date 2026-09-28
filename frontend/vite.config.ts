import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

const frontendPort = Number(process.env.FRONTEND_PORT || 5173)
const backendPort = Number(process.env.BACKEND_PORT || 8000)
const devProxyTarget = process.env.VITE_DEV_PROXY_TARGET || `http://127.0.0.1:${backendPort}`

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') }
  },
  server: {
    // Local development is loopback-only by default. Teams that intentionally
    // need LAN access can still override this with the Vite CLI --host option.
    host: '127.0.0.1',
    port: frontendPort,
    strictPort: true,
    proxy: {
      '/api': {
        target: devProxyTarget,
        changeOrigin: true
      }
    }
  },
  build: { outDir: 'dist', chunkSizeWarningLimit: 1500 }
})
