// @ts-check
const { test, expect } = require('@playwright/test');

async function gotoReady(page, url = '/') {
  await page.goto(url);
  await page.waitForFunction(() => document.body.dataset.appReady === 'true', { timeout: 15_000 });
}

test('progressive mode: HUD, strikes, and results show percentile + per-exam', async ({ page }) => {
  await gotoReady(page);

  // Pick progressive mode and start.
  await page.locator('#mode-tabs button[data-mode="progressive"]').click();
  await expect(page.locator('#hero-cta-sub')).toContainText(/Progressive/i);
  await page.locator('#quick-start-btn').click();

  await expect(page.locator('#quiz-screen')).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('#strikes-pill')).toBeVisible();
  await expect(page.locator('#abandon-btn')).toBeVisible();
  await expect(page.locator('#progress-bar')).toBeHidden();
  // First question should be medium.
  await expect(page.locator('#difficulty-badge')).toHaveText('medium');

  await page.screenshot({ path: 'test-results/screenshots/p1-quiz.png', fullPage: true });

  // Force-end the run by abandoning.
  await page.locator('#abandon-btn').click();
  await expect(page.locator('#alt-results-screen')).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('#alt-title')).toContainText(/Progressive/);
  await expect(page.locator('#alt-meta')).toContainText(/abandoned/i);

  // Abandoned runs cannot save score.
  await expect(page.locator('#alt-score-submit-block')).toBeHidden();

  // Per-difficulty + per-exam tables present.
  await expect(page.locator('#alt-difficulty-table')).toBeVisible();
  await expect(page.locator('#alt-exam-table')).toBeVisible();

  await page.screenshot({ path: 'test-results/screenshots/p2-results.png', fullPage: true });
});

test('progressive leaderboard tab loads', async ({ page }) => {
  await gotoReady(page);
  await page.locator('button[data-screen="leaderboard-screen"]').click();
  await expect(page.locator('#leaderboard-screen')).toBeVisible();

  await page.locator('#lb-mode-tabs button[data-lb-mode="progressive"]').click();
  // exam sub-tabs hidden in progressive mode
  await expect(page.locator('#lb-exam-tabs')).toBeHidden();
  // Headers should change for progressive view
  await expect(page.locator('#lb-thead')).toContainText('Strikes');
});
