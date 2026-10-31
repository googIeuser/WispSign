import { svelte } from '@sveltejs/vite-plugin-svelte'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vitest/config'

export default defineConfig(({ mode }) => ({

  base: './',
  plugins: [tailwindcss(), svelte()],

  resolve: mode === 'test' ? { conditions: ['browser'] } : undefined,
  test: { environment: 'jsdom', include: ['src/**/*.test.ts'] },
}))
