// Next3k LevelUp — vanilla JS SPA.
// Screens: start, quiz, results (report card), leaderboard.

const $ = (id) => document.getElementById(id);

const SCREENS = ["start-screen", "quiz-screen", "results-screen", "leaderboard-screen"];
function show(id) {
  for (const s of SCREENS) $(s).classList.toggle("hidden", s !== id);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

const state = {
  exam: "pca",                  // current exam selected on the start screen
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

  for (const btn of document.querySelectorAll(".navbtn")) {
    btn.addEventListener("click", () => {
      const target = btn.dataset.screen;
      if (target === "leaderboard-screen") loadLeaderboard(state.exam);
      show(target);
    });
  }
  for (const tab of document.querySelectorAll("#leaderboard-screen .tab")) {
    tab.addEventListener("click", () => {
      document.querySelectorAll("#leaderboard-screen .tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      loadLeaderboard(tab.dataset.exam);
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
  // One-click happy path: 10 medium questions on the currently-selected exam.
  startSession({
    exam: state.exam,
    num_questions: 10,
    sections: null,
    difficulties: ["medium"],
    player_name: $("player-name").value.trim() || null,
  });
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
  state.sessionId = data.session_id;
  state.total = data.total;
  state.answered = 0;
  state.correct = 0;
  state.streak = 0;
  state.bestStreak = 0;
  state.lastSummary = null;
  updateHud();
  renderQuestion(data.first_question);
  show("quiz-screen");
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
  $("score-n").textContent = state.correct;
  const sp = $("streak-pill");
  if (state.streak >= 2) {
    sp.classList.remove("hidden");
    $("streak-n").textContent = state.streak;
  } else {
    sp.classList.add("hidden");
  }
}

// ---------- render question ----------

function renderQuestion(q) {
  state.currentQuestion = q;
  state.selected = null;

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
      $("submit-btn").disabled = false;
    });
    ol.appendChild(li);
  });

  $("submit-btn").disabled = true;
  $("submit-btn").classList.remove("hidden");
  $("explanation").classList.add("hidden");
  $("answer-doc-links").innerHTML = "";

  const pct = Math.round((state.answered / state.total) * 100);
  $("progress-text").textContent = `Question ${state.answered + 1} / ${state.total}`;
  $("progress-fill").style.width = pct + "%";
}

// ---------- submit answer ----------

async function onSubmitAnswer() {
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
}

async function onNext() {
  if (state.nextQuestion) renderQuestion(state.nextQuestion);
  else await renderResults();
}

// ---------- results / report card ----------

async function renderResults() {
  const r = await (await fetch(`/api/sessions/${state.sessionId}`)).json();
  state.lastSummary = r;

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
    body: JSON.stringify({ player_name: name }),
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
