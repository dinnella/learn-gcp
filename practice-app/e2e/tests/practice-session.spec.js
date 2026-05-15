// @ts-check
const { test, expect } = require('@playwright/test');
const path = require('path');

// ---------------------------------------------------------------------------
// Helper: wait until init() has finished wiring up event listeners. The app
// awaits /api/health and /api/exams before attaching click handlers, so a
// click that lands before this signal is silently dropped.
// ---------------------------------------------------------------------------
async function gotoReady(page, url = '/') {
  await page.goto(url);
  await page.waitForFunction(() => document.body.dataset.appReady === 'true', { timeout: 15_000 });
}

// ---------------------------------------------------------------------------
// Helper: wait for a stable app state — either results screen is visible,
// or there is a fresh (non-disabled) answer option on screen.
// ---------------------------------------------------------------------------
async function waitForStableState(page, timeout = 15_000) {
  await page.waitForFunction(
    () => {
      const results = document.getElementById('results-screen');
      if (results && !results.classList.contains('hidden')) return true;
      const fresh = document.querySelectorAll('#q-options li:not(.disabled)');
      return fresh.length > 0;
    },
    { timeout }
  );
}

// ---------------------------------------------------------------------------
// Test 1 — Home page smoke test
// ---------------------------------------------------------------------------
test('home page loads with all key elements', async ({ page }) => {
  await gotoReady(page);

  await expect(page.locator('h1')).toContainText('LevelUp');
  await expect(page.locator('#quick-start-btn')).toBeVisible();

  // Exam selector shows PCA as default active tab — assert by data attribute, not display label
  await expect(page.locator('#exam-seg button[data-exam="pca"]')).toHaveClass(/active/);

  // Nav links are present
  await expect(page.locator('button[data-screen="leaderboard-screen"]')).toBeVisible();
  await expect(page.locator('a.github-nav')).toBeVisible();

  await page.screenshot({
    path: 'test-results/screenshots/01-home.png',
    fullPage: true,
  });
});

// ---------------------------------------------------------------------------
// Test 2 — Full practice session → report card → leaderboard
// ---------------------------------------------------------------------------
test('completes a 5-question PCA session and saves score to leaderboard', async ({ page }) => {
  await gotoReady(page);

  // ------------------------------------------------------------------
  // Start a 5-question custom session via the Advanced panel
  // ------------------------------------------------------------------
  await page.locator('details.adv > summary').click();

  // Overwrite the default 10 with 5 for a faster test
  await page.locator('#num').fill('5');

  await page.locator('#start-btn').click();

  // Wait for the quiz screen and first question to render
  await expect(page.locator('#quiz-screen')).toBeVisible({ timeout: 15_000 });
  await page.locator('#q-options li').first().waitFor({ state: 'visible', timeout: 10_000 });

  await page.screenshot({
    path: 'test-results/screenshots/02-quiz-q1.png',
    fullPage: true,
  });

  // ------------------------------------------------------------------
  // Answer questions until the results screen appears.
  // Loop cap of 15 gives a safety margin above the max 10-question session.
  // ------------------------------------------------------------------
  for (let q = 0; q < 15; q++) {
    // Wait until we're in a clean state (new question OR results visible)
    await waitForStableState(page);

    if (await page.locator('#results-screen').isVisible()) break;

    // Select the first option (index 0 — may or may not be correct, doesn't matter)
    await page.locator('#q-options li').first().click();

    // Submit button enables once an option is selected
    await expect(page.locator('#submit-btn')).toBeEnabled({ timeout: 5_000 });
    await page.locator('#submit-btn').click();

    // Wait for the explanation panel to appear (contains the Next button)
    await page.waitForFunction(
      () => {
        const el = document.getElementById('explanation');
        return el && !el.classList.contains('hidden');
      },
      { timeout: 10_000 }
    );

    // Take a mid-session screenshot on the third question to capture the streak HUD
    if (q === 2) {
      await page.screenshot({
        path: 'test-results/screenshots/03-quiz-mid.png',
        fullPage: true,
      });
    }

    // Click Next — advances to the next question or triggers renderResults()
    await page.locator('#next-btn').click();
  }

  // ------------------------------------------------------------------
  // Report card
  // ------------------------------------------------------------------
  await expect(page.locator('#results-screen')).toBeVisible({ timeout: 20_000 });

  // Grade must be a letter (A–F), not the placeholder dash
  const grade = await page.locator('#r-grade').textContent();
  expect(['A', 'B', 'C', 'D', 'F']).toContain(grade?.trim());

  // Score stat row should show a percentage
  await expect(page.locator('#r-score')).not.toHaveText('—');

  await page.screenshot({
    path: 'test-results/screenshots/04-report-card.png',
    fullPage: true,
  });

  // ------------------------------------------------------------------
  // Save score to leaderboard
  // ------------------------------------------------------------------
  await page.locator('#score-name').fill('CI Robot');
  await page.locator('#submit-score-btn').click();

  await expect(page.locator('#score-submit-msg')).toContainText('Saved', {
    timeout: 8_000,
  });

  // ------------------------------------------------------------------
  // Leaderboard — entry must appear
  // ------------------------------------------------------------------
  await page.locator('button[data-screen="leaderboard-screen"]').click();
  await expect(page.locator('#leaderboard-screen')).toBeVisible();

  await expect(page.locator('#lb-table')).toContainText('CI Robot', {
    timeout: 10_000,
  });

  await page.screenshot({
    path: 'test-results/screenshots/05-leaderboard.png',
    fullPage: true,
  });
});

// ---------------------------------------------------------------------------
// Test 3 — Quick-start button
// ---------------------------------------------------------------------------
test('quick-start button starts a session immediately', async ({ page }) => {
  await gotoReady(page);

  await page.locator('#quick-start-btn').click();

  // Quiz screen should appear with question text and 4 options
  await expect(page.locator('#quiz-screen')).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('#q-text')).not.toBeEmpty({ timeout: 10_000 });
  await expect(page.locator('#q-options li')).toHaveCount(4, { timeout: 5_000 });

  // Submit button must be disabled until an option is selected
  await expect(page.locator('#submit-btn')).toBeDisabled();

  // Selecting an option enables the submit button
  await page.locator('#q-options li').first().click();
  await expect(page.locator('#submit-btn')).toBeEnabled({ timeout: 3_000 });
});

// ---------------------------------------------------------------------------
// Test 4 — Report card: next_session_config can be used to start a new session
// ---------------------------------------------------------------------------
test('report card next-session button starts a follow-up session', async ({ page }) => {
  await gotoReady(page);

  // Start a 1-question session using the advanced form
  await page.locator('details.adv > summary').click();
  await page.locator('#num').fill('1');
  await page.locator('#start-btn').click();

  await page.locator('#q-options li').first().waitFor({ state: 'visible', timeout: 15_000 });
  await page.locator('#q-options li').first().click();
  await expect(page.locator('#submit-btn')).toBeEnabled({ timeout: 5_000 });
  await page.locator('#submit-btn').click();

  await page.waitForFunction(
    () => {
      const el = document.getElementById('explanation');
      return el && !el.classList.contains('hidden');
    },
    { timeout: 10_000 }
  );
  await page.locator('#next-btn').click();

  // Results screen
  await expect(page.locator('#results-screen')).toBeVisible({ timeout: 20_000 });

  // The "Start that session" follow-up button must be present
  await expect(page.locator('#next-session-btn')).toBeVisible({ timeout: 5_000 });
  await page.locator('#next-session-btn').click();

  // Should start a new session immediately
  await expect(page.locator('#quiz-screen')).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('#q-options li')).toHaveCount(4, { timeout: 5_000 });
});
