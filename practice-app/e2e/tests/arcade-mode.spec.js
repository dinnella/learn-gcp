// @ts-check
const { test, expect } = require('@playwright/test');

async function gotoReady(page, url = '/') {
  await page.goto(url);
  await page.waitForFunction(() => document.body.dataset.appReady === 'true', { timeout: 15_000 });
}

test('arcade mode: timer + scorebar + level pill visible, abandon works', async ({ page }) => {
  await gotoReady(page);

  await page.locator('#mode-tabs button[data-mode="arcade"]').click();
  await expect(page.locator('#hero-cta-sub')).toContainText(/Arcade/i);
  await page.locator('#quick-start-btn').click();

  await expect(page.locator('#quiz-screen')).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('#timer-bar')).toBeVisible();
  await expect(page.locator('#timer-text')).toContainText(/^[12]:\d\d$/);
  await expect(page.locator('#level-pill')).toBeVisible();
  await expect(page.locator('#progress-bar')).toBeHidden();
  await expect(page.locator('#submit-btn')).toBeHidden();
  await expect(page.locator('#abandon-btn')).toBeVisible();

  await page.screenshot({ path: 'test-results/screenshots/a1-quiz.png', fullPage: true });

  // Quit the run → alt-results
  await page.locator('#abandon-btn').click();
  await expect(page.locator('#alt-results-screen')).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('#alt-title')).toContainText(/Arcade/);
  await expect(page.locator('#alt-meta')).toContainText(/abandoned|0s|\d+s/);
  await expect(page.locator('#alt-score-submit-block')).toBeHidden();

  await page.screenshot({ path: 'test-results/screenshots/a2-results.png', fullPage: true });
});

test('arcade leaderboard tab loads', async ({ page }) => {
  await gotoReady(page);
  await page.locator('button[data-screen="leaderboard-screen"]').click();
  await expect(page.locator('#leaderboard-screen')).toBeVisible();

  await page.locator('#lb-mode-tabs button[data-lb-mode="arcade"]').click();
  await expect(page.locator('#lb-exam-tabs')).toBeHidden();
  await expect(page.locator('#lb-thead')).toContainText('Level');
});
