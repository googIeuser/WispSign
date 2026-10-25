import { svelte } from '@sveltejs/vite-plugin-svelte'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vitest/config'

export default defineConfig(({ mode }) => ({
  // Relative asset URLs: the built app is loaded from local files.
  base: './',
  plugins: [tailwindcss(), svelte()],
  // Component tests mount in jsdom, so resolve Svelte's browser build there.
  resolve: mode === 'test' ? { conditions: ['browser'] } : undefined,
  test: { environment: 'jsdom', include: ['src/**/*.test.ts'] },
}))
