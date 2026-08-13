import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  build: {
    // 提高大包警告门限，避免重型 3D/echarts chunk 干扰构建日志
    chunkSizeWarningLimit: 900,
    // 按依赖拆分稳定缓存 chunk：依赖不变则哈希不变，提高浏览器缓存命中
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            // 仅拆分重型并且本身就是慢加载路纱依赖的库（3D/echarts）：
            // 给其稳定命名，依赖不变则哈希不变，提高浏览器缓存命中，且不影响初始加载构建部分。
            { name: 'vendor-three', test: /node_modules[\\/]three/ },
            { name: 'vendor-echarts', test: /node_modules[\\/](echarts|zrender|vue-echarts)/ },
          ],
        },
      },
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    hmr: {
      overlay: false,
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})