import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export const DEFAULT_API_TARGET = 'http://localhost:5002'

export function resolveApiTarget(env: Partial<Pick<NodeJS.ProcessEnv, 'VITE_API_TARGET'>> = process.env) {
  return env.VITE_API_TARGET || DEFAULT_API_TARGET
}

const apiTarget = resolveApiTarget()

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true
      }
    }
  }
})
