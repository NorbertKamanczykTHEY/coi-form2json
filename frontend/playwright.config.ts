import { defineConfig } from '@playwright/test'

// E2E against running dev servers (README "Test E2E"): E2E_URL (front) and E2E_TOKEN (JWT from make_token).
export default defineConfig({
  testDir: 'e2e',
  timeout: 15 * 60_000,
  expect: { timeout: 15_000 },
  use: { baseURL: process.env.E2E_URL ?? 'http://localhost:5173', viewport: { width: 1366, height: 900 }, locale: 'pl-PL' },
  reporter: 'list',
})
