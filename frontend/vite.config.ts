import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import { resolve } from 'path'
import fs from 'fs'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    Components({
      resolvers: [ElementPlusResolver()],
    }),
  ],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 3000,
    https: getHttpsConfig(),
    proxy: {
      '/api': {
        target: getProxyTarget(),
        changeOrigin: true,
        secure: true, // Verify SSL certificates
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['vue', 'vue-router', 'pinia'],
        },
      },
    },
  },
})

function getHttpsConfig() {
  const useHttps = process.env.VITE_USE_HTTPS === 'true'
  if (!useHttps) return false

  const certPath = process.env.VITE_SSL_CERT_PATH
  const keyPath = process.env.VITE_SSL_KEY_PATH

  if (certPath && keyPath && fs.existsSync(certPath) && fs.existsSync(keyPath)) {
    return {
      cert: fs.readFileSync(certPath),
      key: fs.readFileSync(keyPath),
    }
  }

  // Generate self-signed cert if no certs provided (dev only)
  console.warn('HTTPS enabled but no certificates found. Using self-signed cert.')
  return true
}

function getProxyTarget() {
  const useHttps = process.env.VITE_USE_HTTPS === 'true'
  // Use 127.0.0.1 explicitly instead of localhost to avoid IPv6 issues
  return useHttps ? 'https://127.0.0.1:8000' : 'http://127.0.0.1:8000'
}
