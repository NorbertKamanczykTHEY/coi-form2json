import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Dev: same-origin proxy to the backend (no CORS), like nginx in the container.
const target = process.env.API_UPSTREAM ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { '/api': target, '/healthz': target } },
})
