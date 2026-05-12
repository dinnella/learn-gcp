// Vanilla JS SPA — zero build step.
//
// Three screens:
//   #start-screen   pick exam + section filters + length
//   #quiz-screen    one question at a time, with confidence + explanation
//   #results-screen score + per-section breakdown

const $ = (id) => document.getElementById(id);

const screens = ["start-screen", "quiz-screen", "results-screen"];
function show(id) {
  for (const s of screens) {
    $(s).classList.toggle("hidden", s !== id);
  }
}

const state = {
  sessionId: null,
  total: 0,
  answered: 0,
  currentQuestion: null,
  selected: null,
};

// ---------- env badge + initial section list ----------

async function init() {
  try {
    const h = await (await fetch("/api/health")).json();
    $("env-badge").textContent = h.env || "?";
  } catch (e) {
    $("env-badge").textContent = "offline";
    $("env-badge").style.background = "var(--bad)";
  }

  await loadSections($("exam").value);
  $("exam").addEventListener("change", (e) => loadSections(e.target.value));
  $("start-form").addEventListener("submit", onStart);
  $("submit-btn").addEventListener("click", onSubmitAnswer);
  $("next-btn").addEventListener("click", onNext);
  $("restart-btn").addEventListener("click", () => location.reload());
}

async function loadSections(exam) {
  const r = await (await fetch("/api/exams")).json();
  const ex = r.exams.find((e) => e.id === exam);
  const list = $("sections-list");
  list.innerHTML = "";
  if (!ex) return;
  for (const sec of ex.sections) {
    const id = `sec-${sec}`;
    const wrap = document.createElement("label");
    wrap.innerHTML = `<input type="checkbox" id="${id}" value="${sec}" /> ${sec}`;
    list.appendChild(wrap);
  }
}

// ---------- start a session ----------

async function onStart(e) {
  e.preventDefault();
  const exam = $("exam").value;
  const num = parseInt($("num").value, 10);
  const sections = Array.from(
    document.querySelectorAll('#sections-list input:checked')
  ).map((el) => el.value);

  $("start-btn").disabled = true;
  $("start-btn").textContent = "Starting…";

  let resp;
  try {
    resp = await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        exam,
        num_questions: num,
        sections: sections.length ? sections : null,
      }),
    });
  } catch (err) {
    alert("Network error: " + err);
    $("start-btn").disabled = false;
    $("start-btn").textContent = "Start";
    return;
  }
  if (!resp.ok) {
    const j = await resp.json().catch(() => ({}));
    alert("Start failed: " + (j.detail || resp.statusText));
    $("start-btn").disabled = false;
    $("start-btn").textContent = "Start";
    return;
  }
  const data = await resp.json();
  state.sessionId = data.session_id;
  state.total = data.total;
  state.answered = 0;
  renderQuestion(data.first_question);
  show("quiz-screen");
}

// ---------- render a question ----------

function renderQuestion(q) {
  state.currentQuestion = q;
  state.selected = null;

  $("q-section").textContent = q.section;
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

  // Highlight options
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
  $("explanation").classList.remove("hidden");

  state.nextQuestion = data.next_question;
}

async function onNext() {
  if (state.nextQuestion) {
    renderQuestion(state.nextQuestion);
  } else {
    await renderResults();
  }
}

// ---------- results ----------

async function renderResults() {
  const r = await (await fetch(`/api/sessions/${state.sessionId}`)).json();
  $("r-score").textContent =
    r.score_pct === null ? "—" : `${r.score_pct}% (${Math.round((r.score_pct / 100) * r.answered)}/${r.answered})`;

  const tbody = $("r-sections").querySelector("tbody");
  tbody.innerHTML = "";
  const sections = Object.entries(r.per_section).sort(([a], [b]) => a.localeCompare(b));
  for (const [sec, row] of sections) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><code>${sec}</code></td>
      <td>${row.correct}/${row.total} (${row.pct}%)</td>
      <td><span class="sec-bar" style="width:${Math.max(2, row.pct)}px"></span></td>
    `;
    tbody.appendChild(tr);
  }
  show("results-screen");
}

init();
