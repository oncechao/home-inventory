import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
    // GitHub Codespaces 转发端口时用 *.app.github.dev 域名访问（preview 也沿用这里的设置）
    allowedHosts: ['.app.github.dev'],
  },
})
