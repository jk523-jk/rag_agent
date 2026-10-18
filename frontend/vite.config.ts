import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'

// 开发期 /api 代理到后端。
// 目标地址与端口都从环境变量读，避免 run.py 换端口启动时代理仍打 8000：
//   VITE_DEV_PORT       前端端口（run.py --frontend-port 会注入）
//   VITE_API_TARGET     后端地址（run.py --backend-port 会注入 http://127.0.0.1:<port>）
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const devPort = Number(env.VITE_DEV_PORT || 5173)
  const apiTarget = env.VITE_API_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [vue(), tailwindcss()],
    resolve: {
      alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
    },
    server: {
      port: devPort,
      strictPort: true,
      proxy: { '/api': { target: apiTarget, changeOrigin: true } },
    },
  }
})
