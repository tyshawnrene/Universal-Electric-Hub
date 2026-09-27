import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Forward API calls to the Flask backend during development. Render serves
    // the production build from Flask, so production requests remain same-origin.
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${process.env.BACKEND_PORT || process.env.PORT || 5000}`,
        changeOrigin: true,
      },
    },
  },
})
