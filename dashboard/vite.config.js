import { defineConfig } from 'vite'

export default defineConfig({
  base: '/dashboard/',
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true
      }
    }
  },
  build: {
    outDir: 'dist'
  }
})
