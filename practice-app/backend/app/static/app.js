// Next3k LevelUp — vanilla JS SPA.
// Screens: start, quiz, results (report card), leaderboard.

const $ = (id) => document.getElementById(id);

const SCREENS = ["start-screen", "quiz-screen", "results-screen", "alt-results-screen", "leaderboard-screen"];
function show(id) {
  for (const s of SCREENS) $(s).classList.toggle("hidden", s !== id);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function trackEvent(name, params = {}) {
  if (typeof gtag === "function") gtag("event", name, params);
}

const state = {
  exam: "architect",                  // current exam selected on the start screen
  mode: "classic",              // 'classic' | 'progressive' | 'arcade'
  sessionId: null,
  total: 0,
  answered: 0,
  correct: 0,                   // running correct count for HUD
  streak: 0,                    // consecutive-correct counter
  bestStreak: 0,
  currentQuestion: null,
  selected: null,
  nextQuestion: null,
  playerName: localStorage.getItem("playerName") || "",
  lastSummary: null,
  // One-time leaderboard submission token, issued by the server when the
  // run legitimately ends. Without it /score returns 401.
  submitToken: null,
  // Per-session secret returned in the start response. Required to abandon
  // the run; without it the abandon call returns 401.
  abandonSecret: null,
  // Progressive
  scoreTotal: 0,
  strikes: 0,
  maxStrikes: 3,
  // Arcade
  timeRemainingMs: 0,
  level: 1,
  correctInLevel: 0,
  tickerHandle: null,
  questionRenderedAt: 0,
  levelUpPending: false,
  lbMode: "classic",
};

// ---------- init ----------

async function init() {
  try {
    const h = await (await fetch("/api/health")).json();
    $("env-badge").textContent = h.env || "?";
  } catch {
    $("env-badge").textContent = "offline";
    $("env-badge").style.background = "var(--bad)";
  }

  if (state.playerName) $("player-name").value = state.playerName;

  await loadExamMeta(state.exam);

  // Segmented exam picker on start screen
  for (const btn of document.querySelectorAll("#exam-seg button")) {
    btn.addEventListener("click", async () => {
      document.querySelectorAll("#exam-seg button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.exam = btn.dataset.exam;
      trackEvent("exam_changed", { exam: btn.dataset.exam });
      await loadExamMeta(state.exam);
    });
  }

  $("quick-start-btn").addEventListener("click", onQuickStart);
  $("start-form").addEventListener("submit", onCustomStart);
  $("submit-btn").addEventListener("click", onSubmitAnswer);
  $("next-btn").addEventListener("click", onNext);
  $("restart-btn").addEventListener("click", () => show("start-screen"));
  $("next-session-btn").addEventListener("click", onStartSuggested);
  $("submit-score-btn").addEventListener("click", onSubmitScore);

  // Mode picker
  for (const btn of document.querySelectorAll("#mode-tabs button")) {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#mode-tabs button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.mode = btn.dataset.mode;
      trackEvent("mode_selected", { mode: btn.dataset.mode });
      updateHeroSub();
    });
  }

  // Quit/abandon button (in-quiz)
  $("abandon-btn").addEventListener("click", onAbandonRun);

  // Level-up modal
  $("lvl-continue-btn").addEventListener("click", onArcadeContinue);
  $("lvl-quit-btn").addEventListener("click", async () => {
    closeLevelUpModal();
    await onAbandonRun();
  });

  // Alt results
  $("alt-submit-score-btn").addEventListener("click", onAltSubmitScore);
  $("alt-replay-btn").addEventListener("click", () => onQuickStart());
  $("alt-home-btn").addEventListener("click", () => show("start-screen"));

  for (const btn of document.querySelectorAll(".navbtn")) {
    btn.addEventListener("click", () => {
      if (btn.classList.contains("github-nav")) {
        trackEvent("github_clicked");
        return;
      }
      const target = btn.dataset.screen;
      if (target === "leaderboard-screen") {
        loadActiveLeaderboard();
        trackEvent("leaderboard_viewed");
      }
      show(target);
    });
  }
  for (const tab of document.querySelectorAll("#lb-exam-tabs .tab")) {
    tab.addEventListener("click", () => {
      document.querySelectorAll("#lb-exam-tabs .tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      loadLeaderboard(tab.dataset.exam);
    });
  }
  for (const tab of document.querySelectorAll("#lb-mode-tabs .tab")) {
    tab.addEventListener("click", () => {
      document.querySelectorAll("#lb-mode-tabs .tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      state.lbMode = tab.dataset.lbMode;
      $("lb-exam-tabs").classList.toggle("hidden", state.lbMode !== "classic");
      loadActiveLeaderboard();
    });
  }

  // Signal to e2e tests (and anyone watching) that all event listeners are wired up.
  document.body.dataset.appReady = "true";
}

let _examCache = null;
async function loadExamMeta(exam) {
  if (!_examCache) _examCache = await (await fetch("/api/exams")).json();
  const ex = _examCache.exams.find((e) => e.id === exam);
  if (!ex) return;

  // Topics tile grid (advanced panel) — section is now {id, title}.
  const list = $("sections-list");
  list.innerHTML = "";
  for (const sec of ex.sections) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "sec-tile";
    btn.dataset.id = sec.id;
    btn.dataset.selected = "false";
    btn.textContent = sec.title;
    btn.addEventListener("click", () => {
      const on = btn.dataset.selected === "true";
      btn.dataset.selected = on ? "false" : "true";
    });
    list.appendChild(btn);
  }

  // Difficulty counts
  for (const span of document.querySelectorAll("#difficulty-chips .ct")) {
    span.textContent = ex.difficulties[span.dataset.diff] ?? 0;
  }
}

// ---------- start ----------

function readDifficulties() {
  return Array.from(
    document.querySelectorAll('#difficulty-chips input:checked')
  ).map((el) => el.value);
}
function readSections() {
  return Array.from(
    document.querySelectorAll('#sections-list .sec-tile[data-selected="true"]')
  ).map((el) => el.dataset.id);
}

function onQuickStart() {
  if (state.mode === "progressive") {
    return startProgressiveSession();
  }
  if (state.mode === "arcade") {
    return startArcadeSession();
  }
  // Classic: One-click happy path: 10 medium questions on the currently-selected exam.
  startSession({
    exam: state.exam,
    num_questions: 10,
    sections: null,
    difficulties: ["medium"],
    player_name: $("player-name").value.trim() || null,
  });
}

function updateHeroSub() {
  const sub = $("hero-cta-sub");
  const isClassic = state.mode === "classic";
  // Exam picker + Advanced panel are classic-only.
  const examSwitch = $("exam-switch");
  const advPanel = $("adv-panel");
  const note = $("all-exams-note");
  if (examSwitch) examSwitch.classList.toggle("hidden", !isClassic);
  if (advPanel) advPanel.classList.toggle("hidden", !isClassic);
  if (note) note.classList.toggle("hidden", isClassic);
  if (!sub) return;
  if (state.mode === "progressive") {
    sub.innerHTML = "<strong>Progressive:</strong> 3 strikes, mixed exams, ladder difficulty. 1 / 2 / 4 pts.";
  } else if (state.mode === "arcade") {
    sub.innerHTML = "<strong>Arcade:</strong> 60-second sprint. Correct answers add points + time. Wrong answers cost 10s. Level up every 10.";
  } else {
    sub.innerHTML = "Defaults to <strong>Cloud Architect</strong> · 10 questions · medium difficulty.";
  }
}

async function onCustomStart(e) {
  e.preventDefault();
  await startSession({
    exam: state.exam,
    num_questions: parseInt($("num").value, 10),
    sections: readSections().length ? readSections() : null,
    difficulties: readDifficulties().length ? readDifficulties() : null,
    player_name: $("player-name").value.trim() || null,
  });
}

async function startSession(body) {
  if (body.player_name) {
    state.playerName = body.player_name;
    localStorage.setItem("playerName", body.player_name);
  }
  const startBtns = [$("quick-start-btn"), $("start-btn")];
  startBtns.forEach((b) => b && (b.disabled = true));

  let resp;
  try {
    resp = await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (err) {
    alert("Network error: " + err);
    startBtns.forEach((b) => b && (b.disabled = false));
    return;
  }
  if (!resp.ok) {
    const j = await resp.json().catch(() => ({}));
    alert("Could not start: " + (j.detail || resp.statusText));
    startBtns.forEach((b) => b && (b.disabled = false));
    return;
  }
  const data = await resp.json();
  state.mode = "classic";
  state.sessionId = data.session_id;
  state.submitToken = null;
  state.abandonSecret = data.abandon_secret || null;
  state.total = data.total;
  state.answered = 0;
  state.correct = 0;
  state.streak = 0;
  state.bestStreak = 0;
  state.lastSummary = null;
  applyModeHud();
  updateHud();
  renderQuestion(data.first_question);
  show("quiz-screen");
  trackEvent("game_start", { mode: "classic", exam: body.exam, num_questions: body.num_questions });
  startBtns.forEach((b) => b && (b.disabled = false));
}

async function onStartSuggested() {
  if (!state.lastSummary?.report_card?.next_session_config) return;
  const body = {
    ...state.lastSummary.report_card.next_session_config,
    player_name: state.playerName || null,
  };
  await startSession(body);
}

// ---------- HUD ----------

function updateHud() {
  if (state.mode === "classic") {
    $("score-n").textContent = state.correct;
  } else {
    $("score-n").textContent = state.scoreTotal;
  }
  const sp = $("streak-pill");
  if (state.streak >= 2) {
    sp.classList.remove("hidden");
    $("streak-n").textContent = state.streak;
  } else {
    sp.classList.add("hidden");
  }
  if (state.mode === "progressive") {
    for (const slot of document.querySelectorAll("#strikes-pill .strike-slot")) {
      const i = parseInt(slot.dataset.i, 10);
      slot.classList.toggle("struck", i < state.strikes);
    }
  }
  if (state.mode === "arcade") {
    $("level-n").textContent = state.level;
    $("level-progress").textContent = `${state.correctInLevel}/10`;
  }
}

function applyModeHud() {
  // Toggle which HUD bits are visible based on state.mode.
  const isClassic = state.mode === "classic";
  const isProg = state.mode === "progressive";
  const isArc = state.mode === "arcade";
  $("progress-bar").classList.toggle("hidden", !isClassic);
  $("progress-text").classList.toggle("hidden", !isClassic);
  $("strikes-pill").classList.toggle("hidden", !isProg);
  $("level-pill").classList.toggle("hidden", !isArc);
  $("arcade-clock").classList.toggle("hidden", !isArc);
  $("abandon-btn").classList.toggle("hidden", isClassic);
  // Confidence + submit button: classic & progressive use submit; arcade is rapid-fire (still allow Lock-in).
  $("submit-btn").classList.toggle("hidden", isArc);
  document.querySelector("#quiz-screen .confidence").classList.toggle("hidden", isArc);
}

// ---------- render question ----------

function renderQuestion(q) {
  state.currentQuestion = q;
  state.selected = null;
  state.questionRenderedAt = Date.now();

  $("q-section").textContent = q.section_title || q.section;
  const dbadge = $("difficulty-badge");
  dbadge.textContent = q.difficulty;
  dbadge.className = "diff-badge " + q.difficulty;

  $("q-text").textContent = q.text;

  const ol = $("q-options");
  ol.innerHTML = "";
  q.options.forEach((opt, idx) => {
    const li = document.createElement("li");
    li.textContent = opt;
    li.dataset.idx = String(idx);
    li.addEventListener("click", () => {
      if (li.classList.contains("disabled")) return;
      state.selected = idx;
      ol.querySelectorAll("li").forEach((el) => el.classList.remove("selected"));
      li.classList.add("selected");
      if (state.mode === "arcade") {
        // Rapid-fire: lock immediately on click.
        ol.querySelectorAll("li").forEach((el) => el.classList.add("disabled"));
        onArcadeAnswer();
      } else {
        $("submit-btn").disabled = false;
      }
    });
    ol.appendChild(li);
  });

  $("submit-btn").disabled = true;
  if (state.mode !== "arcade") $("submit-btn").classList.remove("hidden");
  $("explanation").classList.add("hidden");
  $("answer-doc-links").innerHTML = "";

  if (state.mode === "classic") {
    const pct = Math.round((state.answered / state.total) * 100);
    $("progress-text").textContent = `Question ${state.answered + 1} / ${state.total}`;
    $("progress-fill").style.width = pct + "%";
  }
}

// ---------- submit answer ----------

async function onSubmitAnswer() {
  if (state.mode === "progressive") return onProgressiveAnswer();
  if (state.selected === null) return;
  const conf = document.querySelector('input[name="confidence"]:checked').value;
  $("submit-btn").disabled = true;

  const resp = await fetch(`/api/sessions/${state.sessionId}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question_id: state.currentQuestion.id,
      selected_index: state.selected,
      confidence: conf,
    }),
  });
  if (!resp.ok) {
    alert("Submit failed: " + resp.statusText);
    $("submit-btn").disabled = false;
    return;
  }
  const data = await resp.json();
  state.answered = data.progress.answered;

  if (data.correct) {
    state.correct += 1;
    state.streak += 1;
    state.bestStreak = Math.max(state.bestStreak, state.streak);
  } else {
    state.streak = 0;
  }
  updateHud();

  const ol = $("q-options");
  ol.querySelectorAll("li").forEach((el) => {
    el.classList.add("disabled");
    const idx = parseInt(el.dataset.idx, 10);
    if (idx === data.correct_index) el.classList.add("correct");
    else if (idx === state.selected) el.classList.add("incorrect");
  });

  const verdict = $("verdict");
  if (data.correct) {
    const flair = state.streak >= 5 ? ` 🤖 ${state.streak} in a row. Inhuman.`
                : state.streak >= 3 ? ` 🔥 ${state.streak}-streak.`
                : "";
    verdict.innerHTML = `✅ <strong>Correct!</strong>${flair}`;
    verdict.className = "verdict correct";
  } else {
    verdict.innerHTML = `❌ <strong>Not quite.</strong>`;
    verdict.className = "verdict incorrect";
  }
  $("explain-text").textContent = data.explanation || "";

  const links = $("answer-doc-links");
  links.innerHTML = "";
  for (const d of data.doc_links || []) {
    const a = document.createElement("a");
    a.href = d.url; a.target = "_blank"; a.rel = "noopener";
    a.textContent = d.title;
    links.appendChild(a);
  }
  if ((data.doc_links || []).length) {
    const heading = document.createElement("p");
    heading.className = "doc-heading muted small";
    heading.textContent = "📚 Read more:";
    links.prepend(heading);
  }

  $("explanation").classList.remove("hidden");
  state.nextQuestion = data.next_question;
  if (data.submit_token) state.submitToken = data.submit_token;
}

async function onNext() {
  if (state.mode === "progressive" && !state.nextQuestion) {
    const r = await loadProgressiveSummary();
    return renderAltResults(r);
  }
  if (state.nextQuestion) renderQuestion(state.nextQuestion);
  else await renderResults();
}

// ---------- results / report card ----------

async function renderResults() {
  const r = await (await fetch(`/api/sessions/${state.sessionId}`)).json();
  state.lastSummary = r;
  if (r.submit_token) state.submitToken = r.submit_token;

  // Headline reacts to grade.
  const gradeLetter = r.report_card?.overall_grade;
  const headlines = {
    A: "🏆 That's a pass. The cloud acknowledges you.",
    B: "🎉 Solid. You're dangerous with a bit more practice.",
    C: "📊 Middle of the road. The exam won't be.",
    D: "💀 The cloud has spoken. Revisit your notes.",
    F: "🔥 Rough one. The good news: you can only go up.",
  };
  $("r-headline").textContent = headlines[gradeLetter] || "Run complete";

  $("r-meta").textContent =
    `${r.exam.toUpperCase()} • ${r.answered}/${r.total} answered • best streak: ${state.bestStreak} • ${new Date(r.finished_at || Date.now()).toLocaleString()}`;

  const rc = r.report_card || {};
  const grade = rc.overall_grade || "—";
  const g = $("r-grade");
  g.textContent = grade;
  g.className = "grade " + grade;

  const passEl = $("r-passed");
  if (rc.passed_mock) {
    passEl.textContent = "Mock pass ✓";
    passEl.className = "pass-pill pass";
  } else if (rc.overall_grade) {
    passEl.textContent = "Below 70%";
    passEl.className = "pass-pill fail";
  } else passEl.textContent = "";

  $("r-score").textContent = r.score_pct === null ? "—" : `${r.score_pct}%`;
  const fmtDiff = (d) => d.total ? `${d.pct}% (${d.correct}/${d.total})` : "—";
  $("r-easy").textContent = fmtDiff(r.per_difficulty.easy);
  $("r-medium").textContent = fmtDiff(r.per_difficulty.medium);
  $("r-hard").textContent = fmtDiff(r.per_difficulty.hard);

  // Section title lookup, built from cached /api/exams.
  const titles = {};
  if (_examCache) {
    for (const ex of _examCache.exams)
      for (const s of ex.sections) titles[s.id] = s.title;
  }

  // Sections table
  const tbody = $("r-sections").querySelector("tbody");
  tbody.innerHTML = "";
  const secs = Object.entries(r.per_section).sort(([a], [b]) => a.localeCompare(b));
  for (const [sec, row] of secs) {
    const cls = row.pct < 50 ? "bad" : row.pct < 70 ? "warn" : "good";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${titles[sec] || sec}</strong></td>
      <td>${row.correct}/${row.total} <span class="muted small">(${row.pct}%)</span></td>
      <td>
        <div class="sec-track">
          <div class="sec-bar ${cls}" style="width:${Math.max(2, row.pct)}%"></div>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  }

  // Recommendations
  const recsEl = $("r-recs");
  recsEl.innerHTML = "";
  if (!rc.recommendations || rc.recommendations.length === 0) {
    recsEl.innerHTML = `<p class="muted">All topics strong — nothing to drill 🎉</p>`;
  } else {
    for (const rec of rc.recommendations) {
      const card = document.createElement("div");
      card.className = "rec-card" + (rec.score_pct < 70 ? " weak" : "");
      const docs = (rec.docs || []).map(
        (d) => `<a href="${d.url}" target="_blank" rel="noopener">${d.title}</a>`
      ).join("");
      card.innerHTML = `
        <div class="head"><strong>${rec.section_title || rec.section}</strong><span class="pct">${rec.score_pct}%</span></div>
        <p>${rec.suggested_action}</p>
        <div class="doc-links">${docs}</div>
      `;
      recsEl.appendChild(card);
    }
  }

  $("next-prompt").textContent = rc.next_session_prompt || "";

  // Score-submit block
  $("score-name").value = state.playerName || r.player_name || "";
  $("score-submit-msg").textContent = "";
  $("submit-score-btn").disabled = false;

  show("results-screen");
  trackEvent("game_complete", {
    mode: "classic",
    exam: r.exam,
    score_pct: r.score_pct,
    grade: rc.overall_grade,
    correct: r.answered,
    total: r.total,
    passed: !!rc.passed_mock,
  });
  if (rc.passed_mock) burstConfetti();
}

// ---------- score submit ----------

async function onSubmitScore() {
  const name = $("score-name").value.trim();
  if (!name) {
    $("score-submit-msg").textContent = "Enter a player name.";
    return;
  }
  $("submit-score-btn").disabled = true;
  const resp = await fetch(`/api/sessions/${state.sessionId}/score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player_name: name, submit_token: state.submitToken }),
  });
  if (!resp.ok) {
    const j = await resp.json().catch(() => ({}));
    $("score-submit-msg").textContent = "Failed: " + (j.detail || resp.statusText);
    $("submit-score-btn").disabled = false;
    return;
  }
  state.playerName = name;
  localStorage.setItem("playerName", name);
  $("score-submit-msg").textContent = "Saved ✓ — check the leaderboard.";
  trackEvent("score_submitted", { mode: "classic" });
}

// ---------- leaderboard ----------

async function loadLeaderboard(exam) {
  const r = await (await fetch(`/api/leaderboard/${exam}`)).json();
  const tbody = $("lb-table").querySelector("tbody");
  tbody.innerHTML = "";
  if (!r.entries.length) {
    $("lb-empty").classList.remove("hidden");
    return;
  }
  $("lb-empty").classList.add("hidden");
  r.entries.forEach((e, i) => {
    const mix = Object.entries(e.difficulty_mix).map(([d, n]) => `${d.charAt(0).toUpperCase()}${n}`).join(" ");
    const when = new Date(e.finished_at).toLocaleDateString();
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${i + 1}</td>
      <td><strong>${escapeHtml(e.player_name)}</strong></td>
      <td><strong>${e.score_pct}%</strong> <span class="muted small">(${e.answered}/${e.total})</span></td>
      <td class="muted small">${mix}</td>
      <td class="muted small">${when}</td>
    `;
    tbody.appendChild(tr);
  });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

// ---------- confetti ----------

function burstConfetti() {
  const stage = $("confetti-stage");
  if (!stage) return;
  stage.innerHTML = "";
  const colors = ["#4285f4", "#34a853", "#fbbc04", "#ea4335", "#ffd54a"];
  for (let i = 0; i < 40; i++) {
    const piece = document.createElement("span");
    piece.className = "confetti";
    piece.style.left = Math.random() * 100 + "%";
    piece.style.background = colors[i % colors.length];
    piece.style.animationDelay = (Math.random() * 0.6) + "s";
    piece.style.animationDuration = (1.4 + Math.random() * 1.6) + "s";
    stage.appendChild(piece);
  }
  setTimeout(() => (stage.innerHTML = ""), 3500);
}

init();

// =====================================================================
//                     PROGRESSIVE MODE
// =====================================================================

async function startProgressiveSession() {
  const playerName = $("player-name").value.trim() || null;
  if (playerName) {
    state.playerName = playerName;
    localStorage.setItem("playerName", playerName);
  }
  $("quick-start-btn").disabled = true;
  let resp;
  try {
    resp = await fetch("/api/progressive/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ player_name: playerName, max_strikes: 3 }),
    });
  } catch (err) {
    alert("Network error: " + err);
    $("quick-start-btn").disabled = false;
    return;
  }
  if (!resp.ok) {
    const j = await resp.json().catch(() => ({}));
    alert("Could not start: " + (j.detail || resp.statusText));
    $("quick-start-btn").disabled = false;
    return;
  }
  const data = await resp.json();
  state.mode = "progressive";
  state.sessionId = data.session_id;
  state.submitToken = null;
  state.abandonSecret = data.abandon_secret || null;
  state.maxStrikes = data.max_strikes;
  state.strikes = 0;
  state.scoreTotal = 0;
  state.streak = 0;
  state.bestStreak = 0;
  state.correct = 0;
  state.answered = 0;
  applyModeHud();
  updateHud();
  renderQuestion(data.first_question);
  show("quiz-screen");
  trackEvent("game_start", { mode: "progressive" });
  $("quick-start-btn").disabled = false;
}

async function onProgressiveAnswer() {
  if (state.selected === null) return;
  const conf = document.querySelector('input[name="confidence"]:checked').value;
  $("submit-btn").disabled = true;
  const resp = await fetch(`/api/progressive/sessions/${state.sessionId}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question_id: state.currentQuestion.id,
      selected_index: state.selected,
      confidence: conf,
    }),
  });
  if (!resp.ok) {
    alert("Submit failed: " + resp.statusText);
    $("submit-btn").disabled = false;
    return;
  }
  const data = await resp.json();
  state.answered += 1;

  if (data.correct) {
    state.correct += 1;
    state.scoreTotal += data.points_awarded;
    state.streak += 1;
    state.bestStreak = Math.max(state.bestStreak, state.streak);
    spawnPointToast(`+${data.points_awarded}`);
  } else {
    state.streak = 0;
    state.strikes = (data.progress && data.progress.strikes) ?? state.strikes + 1;
  }
  // Keep score_total in sync (server is source of truth)
  if (data.progress && typeof data.progress.score_total === "number") {
    state.scoreTotal = data.progress.score_total;
  }
  updateHud();

  const ol = $("q-options");
  ol.querySelectorAll("li").forEach((el) => {
    el.classList.add("disabled");
    const idx = parseInt(el.dataset.idx, 10);
    if (idx === data.correct_index) el.classList.add("correct");
    else if (idx === state.selected) el.classList.add("incorrect");
  });

  const verdict = $("verdict");
  if (data.correct) {
    verdict.innerHTML = `✅ <strong>Correct!</strong> +${data.points_awarded} pts.`;
    verdict.className = "verdict correct";
  } else {
    verdict.innerHTML = `❌ <strong>Strike ${state.strikes}/${state.maxStrikes}.</strong>`;
    verdict.className = "verdict incorrect";
  }
  $("explain-text").textContent = data.explanation || "";
  renderDocLinks(data.doc_links);

  $("explanation").classList.remove("hidden");
  if (data.ended) {
    state.nextQuestion = null;
    // After Next is clicked, render alt results.
    state._endedReason = data.ended_reason;
    if (data.submit_token) state.submitToken = data.submit_token;
  } else {
    state.nextQuestion = data.next_question;
  }
}

async function loadProgressiveSummary() {
  const r = await (await fetch(`/api/progressive/sessions/${state.sessionId}`)).json();
  state.lastSummary = r;
  if (r.submit_token) state.submitToken = r.submit_token;
  return r;
}

// =====================================================================
//                       ARCADE MODE
// =====================================================================

async function startArcadeSession() {
  const playerName = $("player-name").value.trim() || null;
  if (playerName) {
    state.playerName = playerName;
    localStorage.setItem("playerName", playerName);
  }
  $("quick-start-btn").disabled = true;
  let resp;
  try {
    resp = await fetch("/api/arcade/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ player_name: playerName, starting_seconds: 60 }),
    });
  } catch (err) {
    alert("Network error: " + err);
    $("quick-start-btn").disabled = false;
    return;
  }
  if (!resp.ok) {
    const j = await resp.json().catch(() => ({}));
    alert("Could not start: " + (j.detail || resp.statusText));
    $("quick-start-btn").disabled = false;
    return;
  }
  const data = await resp.json();
  state.mode = "arcade";
  state.sessionId = data.session_id;
  state.submitToken = null;
  state.abandonSecret = data.abandon_secret || null;
  state.timeRemainingMs = data.time_remaining_ms;
  state.level = 1;
  state.correctInLevel = 0;
  state.scoreTotal = 0;
  state.streak = 0;
  state.bestStreak = 0;
  state.correct = 0;
  state.answered = 0;
  state.levelUpPending = false;
  applyModeHud();
  updateHud();
  renderQuestion(data.first_question);
  show("quiz-screen");
  startArcadeTicker();
  trackEvent("game_start", { mode: "arcade" });
  $("quick-start-btn").disabled = false;
}

function startArcadeTicker() {
  stopArcadeTicker();
  state.tickerHandle = setInterval(tickArcade, 100);
  renderTimer();
}

function stopArcadeTicker() {
  if (state.tickerHandle) {
    clearInterval(state.tickerHandle);
    state.tickerHandle = null;
  }
}

function tickArcade() {
  if (state.levelUpPending) return; // pause during modal
  state.timeRemainingMs = Math.max(0, state.timeRemainingMs - 100);
  renderTimer();
  if (state.timeRemainingMs <= 0) {
    stopArcadeTicker();
    // Force a final answer with elapsed=remaining to let server end the session.
    forceArcadeTimeout();
  }
}

async function forceArcadeTimeout() {
  // Submit a deliberately-wrong selection (or just any selection) with large elapsed
  // so the server transitions to ended_reason="time".
  if (!state.currentQuestion) {
    // No active question — load summary directly.
    return loadArcadeSummaryAndShow();
  }
  await fetch(`/api/arcade/sessions/${state.sessionId}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question_id: state.currentQuestion.id,
      selected_index: 0,
      confidence: "guess",
      client_elapsed_ms: 60000,
    }),
  }).catch(() => {});
  return loadArcadeSummaryAndShow();
}

async function onArcadeAnswer() {
  const conf = document.querySelector('input[name="confidence"]:checked')?.value || "guess";
  const elapsed = Math.min(60000, Date.now() - state.questionRenderedAt);
  const resp = await fetch(`/api/arcade/sessions/${state.sessionId}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question_id: state.currentQuestion.id,
      selected_index: state.selected,
      confidence: conf,
      client_elapsed_ms: elapsed,
    }),
  });
  if (!resp.ok) {
    return; // ignore (likely level-up race)
  }
  const data = await resp.json();
  state.timeRemainingMs = data.time_remaining_ms;
  state.scoreTotal = data.score_total;
  state.correctInLevel = data.correct_in_level;
  state.level = data.level;
  state.answered += 1;
  if (data.correct) {
    state.correct += 1;
    state.streak += 1;
    state.bestStreak = Math.max(state.bestStreak, state.streak);
    if (data.points_awarded) spawnPointToast(`+${data.points_awarded}  +${data.time_bonus_seconds}s`);
  } else {
    state.streak = 0;
    if (data.time_penalty_seconds) spawnPointToast(`−${data.time_penalty_seconds}s`, "bad");
  }
  updateHud();
  renderTimer();

  // Brief inline verdict on the option list (no full explanation panel — too slow for arcade).
  const ol = $("q-options");
  ol.querySelectorAll("li").forEach((el) => {
    const idx = parseInt(el.dataset.idx, 10);
    if (idx === data.correct_index) el.classList.add("correct");
    else if (idx === state.selected) el.classList.add("incorrect");
  });

  if (data.ended) {
    stopArcadeTicker();
    if (data.submit_token) state.submitToken = data.submit_token;
    setTimeout(() => loadArcadeSummaryAndShow(), 350);
    return;
  }
  if (data.level_up_pending) {
    state.levelUpPending = true;
    openLevelUpModal();
    return;
  }
  // Render next quickly.
  setTimeout(() => renderQuestion(data.next_question), 350);
}

async function onArcadeContinue() {
  closeLevelUpModal();
  const resp = await fetch(`/api/arcade/sessions/${state.sessionId}/continue`, {
    method: "POST",
  });
  if (!resp.ok) {
    alert("Continue failed");
    return;
  }
  const data = await resp.json();
  state.level = data.level;
  state.correctInLevel = 0;
  state.timeRemainingMs = data.time_remaining_ms;
  state.levelUpPending = false;
  updateHud();
  renderTimer();
  renderQuestion(data.next_question);
  startArcadeTicker();
}

async function loadArcadeSummaryAndShow() {
  const r = await (await fetch(`/api/arcade/sessions/${state.sessionId}`)).json();
  state.lastSummary = r;
  if (r.submit_token) state.submitToken = r.submit_token;
  renderAltResults(r);
}

function renderTimer() {
  if (state.mode !== "arcade") return;
  const sec = state.timeRemainingMs / 1000;
  const cap = 60;
  const pct = Math.max(0, Math.min(100, (sec / cap) * 100));
  const fill = $("timer-fill");
  if (fill) fill.style.width = pct + "%";
  const bar = $("timer-bar");
  const clock = $("arcade-clock");
  const warn = sec <= 30 && sec > 10;
  const danger = sec <= 10;
  bar.classList.toggle("warn", warn);
  bar.classList.toggle("danger", danger);
  if (clock) {
    clock.classList.toggle("warn", warn);
    clock.classList.toggle("danger", danger);
  }
  const m = Math.floor(sec / 60);
  const s = Math.max(0, Math.floor(sec - m * 60));
  $("timer-text").textContent = `${m}:${String(s).padStart(2, "0")}`;
}

// =====================================================================
//                  Level-up modal
// =====================================================================

const LEVEL_RESETS = { 2: 55, 3: 50, 4: 45, 5: 45 };

function openLevelUpModal() {
  const newLevel = state.level + 1;
  trackEvent("arcade_level_up", { level: newLevel });
  $("lvl-new").textContent = newLevel;
  const reset = LEVEL_RESETS[newLevel] ?? 45;
  $("lvl-reset").textContent = `${reset}s`;
  $("level-up-modal").classList.remove("hidden");
}

function closeLevelUpModal() {
  $("level-up-modal").classList.add("hidden");
  state.levelUpPending = false;
}

// =====================================================================
//                  Abandon / quit
// =====================================================================

async function onAbandonRun() {
  if (!state.sessionId || state.mode === "classic") return;
  const path = state.mode === "arcade" ? "arcade" : "progressive";
  stopArcadeTicker();
  trackEvent("game_abandoned", { mode: state.mode, answered: state.answered, score: state.scoreTotal });
  await fetch(`/api/${path}/sessions/${state.sessionId}/abandon`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ abandon_secret: state.abandonSecret }),
  }).catch(() => {});
  if (path === "arcade") return loadArcadeSummaryAndShow();
  const r = await loadProgressiveSummary();
  renderAltResults(r);
}

// =====================================================================
//                  Alt results renderer
// =====================================================================

function renderAltResults(r) {
  const isArc = state.mode === "arcade";
  $("alt-title").textContent = isArc ? "⚡ Arcade run" : "📈 Progressive run";
  $("alt-headline").textContent = headlineForRun(r, isArc);
  const meta = isArc
    ? `Level ${r.level_reached} · ${r.correct_total}/${r.answered_total} correct · ${r.duration_seconds ?? 0}s · ${new Date(r.finished_at || Date.now()).toLocaleString()}`
    : `${r.answered} answered · ${r.correct} correct · ${r.ended_reason || "abandoned"} · ${new Date(r.finished_at || Date.now()).toLocaleString()}`;
  $("alt-meta").textContent = meta;

  $("alt-score-big").textContent = (r.score_total ?? 0).toLocaleString();
  $("alt-score-sub").textContent = isArc ? `Level ${r.level_reached} · best streak ${r.max_streak}` : `${r.correct} correct · best streak ${r.max_streak}`;

  // Stats cards
  const stats = $("alt-stats");
  stats.innerHTML = "";
  if (isArc) {
    stats.appendChild(statCard("Score", (r.score_total ?? 0).toLocaleString()));
    stats.appendChild(statCard("Level", r.level_reached));
    stats.appendChild(statCard("Best streak", r.max_streak));
    stats.appendChild(statCard("Accuracy", `${r.accuracy_pct ?? 0}%`));
  } else {
    stats.appendChild(statCard("Score", r.score_total ?? 0));
    stats.appendChild(statCard("Correct", r.correct ?? 0));
    stats.appendChild(statCard("Best streak", r.max_streak ?? 0));
    stats.appendChild(statCard("Strikes", `${r.strikes ?? 0}/${r.max_strikes ?? 3}`));
  }

  // Percentile (progressive only)
  const pctBlock = $("alt-percentile-block");
  if (!isArc && typeof r.percentile === "number") {
    pctBlock.classList.remove("hidden");
    $("alt-percentile").textContent = `Top ${(100 - r.percentile).toFixed(1)}%`;
    $("alt-percentile-pct").textContent = `${r.percentile.toFixed(1)}%`;
  } else {
    pctBlock.classList.add("hidden");
  }

  // Difficulty table
  const dt = $("alt-difficulty-table").querySelector("tbody");
  dt.innerHTML = "";
  for (const diff of ["easy", "medium", "hard"]) {
    const row = (r.per_difficulty || {})[diff];
    if (!row) continue;
    const tr = document.createElement("tr");
    const correct = row.correct ?? 0;
    const total = row.total ?? row.served ?? 0;
    const pts = row.points ?? "—";
    tr.innerHTML = `<td><span class="diff-badge ${diff}">${diff}</span></td><td>${correct}/${total}</td><td>${pts}</td>`;
    dt.appendChild(tr);
  }

  // Exam table
  const et = $("alt-exam-table").querySelector("tbody");
  et.innerHTML = "";
  const perExam = r.per_exam || {};
  for (const [exam, row] of Object.entries(perExam)) {
    const tr = document.createElement("tr");
    const correct = row.correct ?? 0;
    const total = row.total ?? row.served ?? 0;
    const pts = row.points ?? "—";
    tr.innerHTML = `<td><strong>${exam.toUpperCase()}</strong></td><td>${correct}/${total}</td><td>${pts}</td>`;
    et.appendChild(tr);
  }

  // Save block — disable for abandoned runs
  const canSubmit = !!r.ended_reason && r.ended_reason !== "abandoned";
  $("alt-score-submit-block").classList.toggle("hidden", !canSubmit);
  $("alt-save-heading").classList.toggle("hidden", !canSubmit);
  if (canSubmit) {
    $("alt-score-name").value = state.playerName || r.player_name || "";
    $("alt-score-submit-msg").textContent = "";
    $("alt-submit-score-btn").disabled = false;
  }

  show("alt-results-screen");
  if (r.ended_reason && r.ended_reason !== "abandoned") {
    const _isArc = state.mode === "arcade";
    trackEvent("game_complete", {
      mode: state.mode,
      score: r.score_total ?? 0,
      ...(_isArc
        ? { level_reached: r.level_reached, accuracy_pct: r.accuracy_pct }
        : { correct: r.correct, strikes: r.strikes }),
    });
  }
}

function headlineForRun(r, isArc) {
  if (r.ended_reason === "abandoned") return "Run abandoned";
  if (isArc) {
    if (r.level_reached >= 4) return "🏆 You broke the cloud.";
    if (r.level_reached >= 3) return "🔥 Solid sprint.";
    if (r.level_reached >= 2) return "👍 Decent run.";
    return "GG — try again, see if you can hit Level 2.";
  }
  if (r.ended_reason === "hard_exhausted") return "🏆 Cleared all the hards. Cloud-broken.";
  return r.score_total >= 30 ? "🔥 Climbed the ladder." : "GG — three strikes.";
}

function statCard(label, val) {
  const div = document.createElement("div");
  div.className = "score-stat";
  div.innerHTML = `<div class="lbl">${label}</div><div class="val">${val}</div>`;
  return div;
}

async function onAltSubmitScore() {
  const name = $("alt-score-name").value.trim();
  if (!name) {
    $("alt-score-submit-msg").textContent = "Enter a player name.";
    return;
  }
  $("alt-submit-score-btn").disabled = true;
  const path = state.mode === "arcade" ? "arcade" : "progressive";
  const resp = await fetch(`/api/${path}/sessions/${state.sessionId}/score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player_name: name, submit_token: state.submitToken }),
  });
  if (!resp.ok) {
    const j = await resp.json().catch(() => ({}));
    $("alt-score-submit-msg").textContent = "Failed: " + (j.detail || resp.statusText);
    $("alt-submit-score-btn").disabled = false;
    return;
  }
  state.playerName = name;
  localStorage.setItem("playerName", name);
  $("alt-score-submit-msg").textContent = "Saved ✓ — check the leaderboard.";
  trackEvent("score_submitted", { mode: state.mode });
}

// =====================================================================
//                  Mode-aware leaderboard
// =====================================================================

async function loadActiveLeaderboard() {
  if (state.lbMode === "classic") {
    const exam = document.querySelector("#lb-exam-tabs .tab.active")?.dataset.exam || "architect";
    return loadLeaderboard(exam);
  }
  if (state.lbMode === "progressive") return loadProgressiveLeaderboard();
  if (state.lbMode === "arcade") return loadArcadeLeaderboard();
}

async function loadProgressiveLeaderboard() {
  const r = await (await fetch("/api/progressive/leaderboard")).json();
  $("lb-thead").innerHTML = `<tr><th>#</th><th>Player</th><th>Score</th><th>Correct</th><th>Strikes</th><th>When</th></tr>`;
  const tbody = $("lb-table").querySelector("tbody");
  tbody.innerHTML = "";
  if (!r.entries.length) { $("lb-empty").classList.remove("hidden"); return; }
  $("lb-empty").classList.add("hidden");
  r.entries.forEach((e, i) => {
    const when = new Date(e.finished_at).toLocaleDateString();
    const tr = document.createElement("tr");
    const ratio = `${e.correct}/${e.answered}`;
    tr.innerHTML = `
      <td>${i + 1}</td>
      <td><strong>${escapeHtml(e.player_name)}</strong></td>
      <td><strong>${e.score_total}</strong></td>
      <td>${ratio}</td>
      <td class="muted small">${e.ended_reason}</td>
      <td class="muted small">${when}</td>
    `;
    tbody.appendChild(tr);
  });
}

async function loadArcadeLeaderboard() {
  const r = await (await fetch("/api/arcade/leaderboard")).json();
  $("lb-thead").innerHTML = `<tr><th>#</th><th>Player</th><th>Score</th><th>Level</th><th>Correct</th><th>Streak</th><th>When</th></tr>`;
  const tbody = $("lb-table").querySelector("tbody");
  tbody.innerHTML = "";
  if (!r.entries.length) { $("lb-empty").classList.remove("hidden"); return; }
  $("lb-empty").classList.add("hidden");
  r.entries.forEach((e, i) => {
    const when = new Date(e.finished_at).toLocaleDateString();
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${i + 1}</td>
      <td><strong>${escapeHtml(e.player_name)}</strong></td>
      <td><strong>${(e.score_total).toLocaleString()}</strong></td>
      <td>${e.level_reached}</td>
      <td>${e.correct_total}/${e.answered_total}</td>
      <td class="muted small">${e.max_streak}</td>
      <td class="muted small">${when}</td>
    `;
    tbody.appendChild(tr);
  });
}

// =====================================================================
//                  Misc helpers
// =====================================================================

function renderDocLinks(docs) {
  const links = $("answer-doc-links");
  links.innerHTML = "";
  for (const d of docs || []) {
    const a = document.createElement("a");
    a.href = d.url; a.target = "_blank"; a.rel = "noopener";
    a.textContent = d.title;
    links.appendChild(a);
  }
  if ((docs || []).length) {
    const heading = document.createElement("p");
    heading.className = "doc-heading muted small";
    heading.textContent = "📚 Read more:";
    links.prepend(heading);
  }
}

function spawnPointToast(text, variant) {
  const stage = $("point-toast-stage");
  if (!stage) return;
  const el = document.createElement("div");
  el.className = "point-toast" + (variant ? ` point-toast-${variant}` : "");
  el.textContent = text;
  stage.appendChild(el);
  setTimeout(() => el.remove(), 1100);
}

