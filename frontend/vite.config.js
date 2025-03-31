import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 8080,  // Use a port that worked
    host: '127.0.0.1',  // Explicitly use IP instead of localhost
    strictPort: true,  // Don't try other ports if this one is taken

    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      }
    }
  }
})
