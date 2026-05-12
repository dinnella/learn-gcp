// Vanilla JS SPA — game mode.
// Screens: start, quiz, results (report card), leaderboard.

const $ = (id) => document.getElementById(id);

const SCREENS = ["start-screen", "quiz-screen", "results-screen", "leaderboard-screen"];
function show(id) {
  for (const s of SCREENS) $(s).classList.toggle("hidden", s !== id);
}

const state = {
  sessionId: null,
  total: 0,
  answered: 0,
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

  await loadExamMeta($("exam").value);
  $("exam").addEventListener("change", (e) => loadExamMeta(e.target.value));
  $("start-form").addEventListener("submit", onStart);
  $("submit-btn").addEventListener("click", onSubmitAnswer);
  $("next-btn").addEventListener("click", onNext);
  $("restart-btn").addEventListener("click", () => show("start-screen"));
  $("next-session-btn").addEventListener("click", onStartSuggested);
  $("submit-score-btn").addEventListener("click", onSubmitScore);

  for (const btn of document.querySelectorAll(".navbtn")) {
    btn.addEventListener("click", () => {
      const target = btn.dataset.screen;
      if (target === "leaderboard-screen") loadLeaderboard("pca");
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
}

async function loadExamMeta(exam) {
  const r = await (await fetch("/api/exams")).json();
  const ex = r.exams.find((e) => e.id === exam);
  if (!ex) return;

  // Sections checklist
  const list = $("sections-list");
  list.innerHTML = "";
  for (const sec of ex.sections) {
    const wrap = document.createElement("label");
    wrap.innerHTML = `<input type="checkbox" value="${sec}" /> ${sec}`;
    list.appendChild(wrap);
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
    document.querySelectorAll('#sections-list input:checked')
  ).map((el) => el.value);
}

async function onStart(e) {
  e.preventDefault();
  await startSession({
    exam: $("exam").value,
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
  $("start-btn").disabled = true;
  $("start-btn").textContent = "Starting…";
  let resp;
  try {
    resp = await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (err) {
    alert("Network error: " + err);
    $("start-btn").disabled = false;
    $("start-btn").textContent = "Start →";
    return;
  }
  if (!resp.ok) {
    const j = await resp.json().catch(() => ({}));
    alert("Could not start: " + (j.detail || resp.statusText));
    $("start-btn").disabled = false;
    $("start-btn").textContent = "Start →";
    return;
  }
  const data = await resp.json();
  state.sessionId = data.session_id;
  state.total = data.total;
  state.answered = 0;
  state.lastSummary = null;
  renderQuestion(data.first_question);
  show("quiz-screen");
  $("start-btn").disabled = false;
  $("start-btn").textContent = "Start →";
}

async function onStartSuggested() {
  if (!state.lastSummary?.report_card?.next_session_config) return;
  const body = {
    ...state.lastSummary.report_card.next_session_config,
    player_name: state.playerName || null,
  };
  await startSession(body);
}

// ---------- render question ----------

function renderQuestion(q) {
  state.currentQuestion = q;
  state.selected = null;

  $("q-section").textContent = q.section;
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
  $("progress-text").textContent = `Question ${state.answered + 1} of ${state.total}`;
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

  const ol = $("q-options");
  ol.querySelectorAll("li").forEach((el) => {
    el.classList.add("disabled");
    const idx = parseInt(el.dataset.idx, 10);
    if (idx === data.correct_index) el.classList.add("correct");
    else if (idx === state.selected) el.classList.add("incorrect");
  });

  $("verdict").textContent = data.correct ? "Correct ✓" : "Incorrect ✗";
  $("verdict").className = data.correct ? "correct" : "incorrect";
  $("explain-text").textContent = data.explanation || "";

  const links = $("answer-doc-links");
  links.innerHTML = "";
  for (const d of data.doc_links || []) {
    const a = document.createElement("a");
    a.href = d.url; a.target = "_blank"; a.rel = "noopener";
    a.textContent = d.title;
    links.appendChild(a);
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

  $("r-meta").textContent =
    `${r.exam.toUpperCase()} • ${r.answered}/${r.total} answered • ${new Date(r.finished_at || Date.now()).toLocaleString()}`;

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

  // Sections table
  const tbody = $("r-sections").querySelector("tbody");
  tbody.innerHTML = "";
  const secs = Object.entries(r.per_section).sort(([a], [b]) => a.localeCompare(b));
  for (const [sec, row] of secs) {
    const cls = row.pct < 50 ? "bad" : row.pct < 70 ? "warn" : "";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><code>${sec}</code></td>
      <td>${row.correct}/${row.total} (${row.pct}%)</td>
      <td><span class="sec-bar ${cls}" style="width:${Math.max(2, row.pct)}px"></span></td>
    `;
    tbody.appendChild(tr);
  }

  // Recommendations
  const recsEl = $("r-recs");
  recsEl.innerHTML = "";
  if (!rc.recommendations || rc.recommendations.length === 0) {
    recsEl.innerHTML = `<p class="muted">All sections strong — nothing to drill 🎉</p>`;
  } else {
    for (const rec of rc.recommendations) {
      const card = document.createElement("div");
      card.className = "rec-card" + (rec.score_pct < 70 ? " weak" : "");
      const docs = (rec.docs || []).map(
        (d) => `<a href="${d.url}" target="_blank" rel="noopener">${d.title}</a>`
      ).join("");
      card.innerHTML = `
        <div class="head"><strong>${rec.section}</strong><span class="pct">${rec.score_pct}%</span></div>
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
  $("score-submit-msg").textContent = "Saved ✓ — view it on the Leaderboard tab.";
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
    const mix = Object.entries(e.difficulty_mix).map(([d, n]) => `${d.charAt(0)}:${n}`).join(" ");
    const when = new Date(e.finished_at).toLocaleDateString();
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${i + 1}</td>
      <td>${e.player_name}</td>
      <td><strong>${e.score_pct}%</strong> <span class="muted small">(${e.answered}/${e.total})</span></td>
      <td class="muted small">${mix}</td>
      <td class="muted small">${when}</td>
    `;
    tbody.appendChild(tr);
  });
}

init();
