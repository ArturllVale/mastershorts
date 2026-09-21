import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import seo from './vite-plugin-seo'

import fs from 'fs'

// Backend target for the dev proxy. Defaults to localhost:8000 when running
// locally on the host machine, or http://backend:8000 when inside a Docker container.
const isDocker = fs.existsSync('/.dockerenv') || process.env.IS_DOCKER;
const backend = process.env.VITE_PROXY_TARGET || (isDocker ? 'http://backend:8000' : 'http://localhost:8000');
const renderer = process.env.VITE_RENDER_TARGET || (isDocker ? 'http://renderer:3100' : 'http://localhost:3100');

// https://vitejs.dev/config/
export default defineConfig({
  // seo() runs on build only. It injects the crawler-visible homepage content
  // into #root and emits the static /alternatives pages, sitemap.xml and
  // llms.txt. See vite-plugin-seo.js.
  plugins: [react(), seo()],
  server: {
    allowedHosts: [
      'openshorts.app',
      'www.openshorts.app'
    ],
    proxy: {
      '/api': { target: backend, changeOrigin: true },
      '/videos': { target: backend, changeOrigin: true },
      '/thumbnails': { target: backend, changeOrigin: true },
      '/gallery': { target: backend, changeOrigin: true },
      '/video': { target: backend, changeOrigin: true },
      '/render': { target: renderer, changeOrigin: true },
    }
  }
})
