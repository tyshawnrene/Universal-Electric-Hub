import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Forward API calls to the Flask backend (backend/app.py) during development.
    proxy: {
      '/api': 'http://localhost:5000',
    },
  },
})
