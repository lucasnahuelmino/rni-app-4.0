import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  // process.env NO lee los .env de Vite: loadEnv si. Sin esto, escribir
  // VITE_API_PROXY_TARGET en frontend/.env.local no tendria efecto y el proxy
  // caeria siempre en el 8000 por defecto.
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [vue()],
    server: {
      proxy: {
        '/api': {
          target: env.VITE_API_PROXY_TARGET || 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  }
})
