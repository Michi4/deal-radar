import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  base: '/v2assets/',
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  build: { outDir: 'dist', emptyOutDir: true, sourcemap: false },
  server: { port: 5173, proxy: { '/searches': 'http://127.0.0.1:8099', '/drivers': 'http://127.0.0.1:8099', '/marketplace': 'http://127.0.0.1:8099', '/favorites': 'http://127.0.0.1:8099', '/metrics.json': 'http://127.0.0.1:8099', '/lab': 'http://127.0.0.1:8099', '/settings': 'http://127.0.0.1:8099', '/listings': 'http://127.0.0.1:8099', '/stream': 'http://127.0.0.1:8099' } }
})
