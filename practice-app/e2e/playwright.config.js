// @ts-check
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',

  // Per-test timeout (the full session takes ~30s with 5 questions)
  timeout: 90_000,

  // Retry once on CI to absorb timing flakes; no retries locally
  retries: process.env.CI ? 1 : 0,

  // One worker: tests share the same running stack, no parallelism needed
  workers: 1,

  reporter: [
    ['list'],
    ['html', { open: 'never', outputFolder: 'playwright-report' }],
  ],

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:8080',
    headless: true,

    // Always capture a screenshot at test end (pass or fail)
    screenshot: 'on',
    // Keep video on failure for debugging
    video: 'retain-on-failure',
    // Keep trace on failure for step-by-step replay
    trace: 'retain-on-failure',
  },

  outputDir: 'test-results',
});
