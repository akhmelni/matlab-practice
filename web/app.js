"use strict";

const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const IS_MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
const MOD = IS_MAC ? "⌘" : "Ctrl+";
const RUN_KEY = `${MOD}'`;
const SUBMIT_KEY = IS_MAC ? "⌘↵" : "Ctrl+Enter";

const SERVER_DOWN = "Can't reach the app server. Start it again with start.bat (Windows) or ./start.sh (Mac).";
const POLL_MS = 2000;

const VERDICT_LABEL = {
  accepted: "Accepted",
  wrong: "Wrong Answer",
  error: "Error",
  timeout: "Time Limit Exceeded",
  blocked: "Blocked",
  flagged: "Flagged",
  pending: "Checking with Claude…",
};

const state = {
  problems: [],
  current: null,       // problem id
  detail: null,        // GET /api/problems/<id>
  active: "code",      // "code" | "scratch"
  dirty: false,
  saveTimer: null,
  viewedSub: null,     // full submission shown in the Submissions tab
  resultSid: null,     // submission id shown in the Result panel
  busy: false,
  polls: new Map(),    // "<pid>/<sid>" -> timer
  showSource: false,
  banners: { server: null, octave: null, claude: null },
  issues: { code: [], scratch: [] },
};

// ---------- API ----------

class ServerDown extends Error {}

async function api(path, body, extra = {}) {
  const opts = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), ...extra };
  let res;
  try {
    res = await fetch(path, opts);
  } catch {
    setBanner("server", SERVER_DOWN);
    throw new ServerDown(SERVER_DOWN);
  }
  setBanner("server", null);
  if (!res.ok) {
    let msg = `Server error ${res.status} on ${path}`;
    try { const j = await res.json(); if (j && j.error) msg += `: ${j.error}`; } catch {}
    throw new Error(msg);
  }
  return res.json();
}

// ---------- banner + status footer ----------

function setBanner(key, msg) {
  if (state.banners[key] === msg) return;
  state.banners[key] = msg;
  const items = [];
  if (state.banners.server) items.push(`<div class="banner-item bad">${esc(state.banners.server)}</div>`);
  if (state.banners.octave) items.push(`<div class="banner-item bad">${esc(state.banners.octave)}</div>`);
  if (state.banners.claude) items.push(`<div class="banner-item warn">${esc(state.banners.claude)}</div>`);
  $("#banner").innerHTML = items.join("");
  $("#banner").hidden = !items.length;
}

async function loadStatus() {
  try {
    const s = await api("/api/status");
    const oct = s.octave || {};
    const cl = s.claude || {};
    setBanner("octave", oct.found ? null : "Octave isn't installed or wasn't found — see INSTALL.md. Run and Submit won't work until it is.");
    setBanner("claude", cl.found ? null : "Claude review is off — Claude Code wasn't found, so submissions won't be reviewed and there are no hints.");
    $("#status-footer").innerHTML = `
      <div class="${oct.found ? "" : "bad"}" title="${esc(oct.path || "")}">
        <span class="sdot ${oct.found ? "ok" : "bad"}"></span>${oct.found ? `Octave ${esc(oct.version || "")}` : "Octave not found"}</div>
      <div class="${cl.found ? "" : "warn"}">
        <span class="sdot ${cl.found ? "ok" : "warn"}"></span>${cl.found ? "Claude review on" : "Claude review off"}</div>
      ${s.work_dir ? `<div class="workdir" title="${esc(s.work_dir)}">Your files: ${esc(s.work_dir)}</div>` : ""}`;
  } catch (e) {
    $("#status-footer").innerHTML = `<div class="bad"><span class="sdot bad"></span>Server offline</div>`;
  }
}

// ---------- markdown + math ----------

// Math spans are swapped for placeholders before marked runs (so `_` and `*` inside
// math aren't turned into emphasis) and put back afterwards as plain text, which
// KaTeX auto-render then typesets. Code spans/blocks are left alone.
const MATH_RE = /(```[\s\S]*?```|`[^`\n]+`)|(\\\$)|(\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\)|(?<![\\$])\$(?=[^\s$])(?:\\.|[^$\\\n])*?[^\s\\]\$|(?<![\\$])\$[^\s$\\]\$)/g;

const safeMarked = new marked.Marked({ gfm: true, breaks: false });
safeMarked.use({ renderer: { html: (html) => esc(typeof html === "string" ? html : html.text) } });

function renderMd(md, { safe = false } = {}) {
  const stash = [];
  const protectedMd = String(md || "").replace(MATH_RE, (m, code, dollar, math) => {
    if (code) return m;
    stash.push(dollar ? '<span class="dollar">$</span>' : esc(math));
    return `KTXMATH${stash.length - 1}XEND`;
  });
  const html = (safe ? safeMarked : marked).parse(protectedMd);
  return html.replace(/KTXMATH(\d+)XEND/g, (_, i) => stash[Number(i)]);
}

function typeset(el) {
  if (!window.renderMathInElement) return;
  renderMathInElement(el, {
    delimiters: [
      { left: "$$", right: "$$", display: true },
      { left: "\\[", right: "\\]", display: true },
      { left: "\\(", right: "\\)", display: false },
      { left: "$", right: "$", display: false },
    ],
    throwOnError: false,
    ignoredClasses: ["dollar"],
  });
}

function setMd(el, md, opts) {
  el.innerHTML = renderMd(md, opts);
  typeset(el);
}

// ---------- editors ----------

CodeMirror.commands.toggleComment = (cm) => {
  const from = cm.getCursor("from").line, to = cm.getCursor("to").line;
  const lines = [];
  for (let i = from; i <= to; i++) lines.push(cm.getLine(i));
  const allCommented = lines.filter((l) => l.trim()).every((l) => /^\s*%/.test(l));
  cm.operation(() => {
    lines.forEach((l, k) => {
      if (!l.trim()) return;
      const next = allCommented ? l.replace(/^(\s*)% ?/, "$1") : l.replace(/^(\s*)/, "$1% ");
      cm.replaceRange(next, { line: from + k, ch: 0 }, { line: from + k, ch: l.length });
    });
  });
};

const baseOptions = {
  mode: "octave",
  indentUnit: 4,
  tabSize: 4,
  indentWithTabs: false,
  lineNumbers: true,
  matchBrackets: true,
  spellcheck: false,
  autocorrect: false,
  autocapitalize: false,
};

const editKeys = {
  Tab: (cm) => {
    if (cm.somethingSelected()) return cm.indentSelection("add");
    const col = cm.getCursor().ch;
    cm.replaceSelection(" ".repeat(4 - (col % 4)), "end");
  },
  "Shift-Tab": (cm) => cm.indentSelection("subtract"),
  "Cmd-/": "toggleComment",
  "Ctrl-/": "toggleComment",
};

function toAnnotations(issues, cm) {
  const last = cm.lastLine();
  return (issues || []).map((i) => {
    const line = Math.min(Math.max((i.line || 1) - 1, 0), last);
    const ch = Math.max((i.col || 1) - 1, 0);
    let endLine = Math.min(Math.max((i.end_line || i.line || 1) - 1, line), last);
    let endCh = i.end_col ? i.end_col - 1 : ch + 1;           // end_col is exclusive, 1-based
    if (endLine === line && endCh <= ch) endCh = ch + 1;
    const lineLen = cm.getLine(endLine).length;
    if (endLine === line && ch >= lineLen) endCh = Math.max(ch, lineLen); // past end of line: CodeMirror clips
    return {
      from: CodeMirror.Pos(line, ch),
      to: CodeMirror.Pos(endLine, endCh),
      severity: i.severity === "warning" ? "warning" : "error",
      message: i.message || i.rule || "Problem here",
    };
  });
}

function makeLinter(which) {
  return (text, done, _opts, cm) => {
    const pid = state.current;
    if (!pid || (which === "scratch" && !hasScratch())) { setIssues(which, []); return done([]); }
    const file = which === "scratch" ? "scratch.m" : (state.detail && state.detail.file) || null;
    api(`/api/problems/${pid}/check`, { code: text, file })
      .then((r) => {
        if (pid !== state.current) return done([]);
        const anns = toAnnotations(r.issues, cm);
        setIssues(which, anns);
        done(anns);
      })
      .catch(() => done(cm.state.lint ? cm.state.lint.marked.map((m) => m.__annotation).filter(Boolean) : []));
  };
}

function makeEditor(which) {
  const wrap = document.createElement("div");
  wrap.className = "editor-wrap";
  wrap.dataset.file = which;
  $("#editors").appendChild(wrap);
  const cm = CodeMirror(wrap, {
    ...baseOptions,
    extraKeys: editKeys,
    gutters: ["CodeMirror-lint-markers", "CodeMirror-linenumbers"],
    lint: { getAnnotations: makeLinter(which), async: true, delay: 500 },
  });
  cm.on("change", (_cm, change) => {
    if (change.origin === "setValue") return;
    markDirty();
  });
  return { cm, wrap };
}

const editors = { code: makeEditor("code"), scratch: makeEditor("scratch") };
const subViewer = CodeMirror($("#sub-code"), { ...baseOptions, readOnly: true });

function hasScratch() { return !!state.detail && state.detail.scratch !== null && state.detail.scratch !== undefined; }
function fileName(which) { return which === "scratch" ? "scratch.m" : (state.detail ? state.detail.file : "solution.m"); }

function setIssues(which, anns) {
  state.issues[which] = anns;
  renderFileTabs();
}

function renderFileTabs() {
  const files = hasScratch() ? ["code", "scratch"] : ["code"];
  $("#file-tabs").innerHTML = files.map((w) => {
    const n = state.issues[w].length;
    return `<button data-file="${w}" class="${w === state.active ? "active" : ""}" title="${w === "scratch" ? "Try-it script: Run runs this file" : "Your solution file: this is what Submit checks"}">
      ${esc(fileName(w))}${n ? `<span class="issue-badge">${n}</span>` : ""}</button>`;
  }).join("");
  const n = state.issues[state.active].length;
  $("#issue-count").textContent = n ? `${n} MATLAB issue${n === 1 ? "" : "s"}` : "";
  $("#issue-count").title = n ? state.issues[state.active].map((a) => `line ${a.from.line + 1}: ${a.message}`).join("\n") : "";
}

function switchFile(which) {
  if (which === "scratch" && !hasScratch()) which = "code";
  state.active = which;
  for (const [w, ed] of Object.entries(editors)) ed.wrap.hidden = w !== which;
  editors[which].cm.refresh();
  renderFileTabs();
}

$("#file-tabs").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-file]");
  if (!b) return;
  switchFile(b.dataset.file);
  editors[state.active].cm.focus();
});

// ---------- syntax highlighting on/off (remembered in this browser) ----------

function setHighlighting(on) {
  for (const cm of [editors.code.cm, editors.scratch.cm, subViewer]) {
    cm.setOption("mode", on ? "octave" : "text/plain");
    cm.setOption("matchBrackets", on);
  }
  $("#hl-toggle").checked = on;
  try { localStorage.setItem("highlighting", on ? "on" : "off"); } catch {}
}
$("#hl-toggle").addEventListener("change", (e) => setHighlighting(e.target.checked));

function savedHighlighting() {
  try { return localStorage.getItem("highlighting") !== "off"; } catch { return true; }
}

// ---------- autosave ----------

function setSaveState(text) { $("#save-state").textContent = text; }

function payload() {
  return { code: editors.code.cm.getValue(), scratch: hasScratch() ? editors.scratch.cm.getValue() : null };
}

function markDirty() {
  state.dirty = true;
  setSaveState("Unsaved");
  clearTimeout(state.saveTimer);
  state.saveTimer = setTimeout(save, 700);
}

async function save() {
  clearTimeout(state.saveTimer);
  if (!state.current || !state.dirty) return;
  state.dirty = false;
  const body = payload();
  try {
    await api(`/api/problems/${state.current}/save`, body);
    if (state.detail) { state.detail.code = body.code; if (hasScratch()) state.detail.scratch = body.scratch; }
    setSaveState(state.dirty ? "Unsaved" : "Saved");
  } catch {
    state.dirty = true;
    setSaveState("Not saved");
    clearTimeout(state.saveTimer);
    state.saveTimer = setTimeout(save, 5000); // keep trying until the server is back
  }
}

function saveNow() {
  if (!state.current || !state.dirty) return;
  try {
    fetch(`/api/problems/${state.current}/save`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload()), keepalive: true,
    });
    state.dirty = false;
  } catch {}
}
window.addEventListener("pagehide", saveNow);
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") saveNow(); });

// ---------- tabs ----------

function showTab(group, tab) {
  const nav = document.querySelector(`.tabs[data-group="${group}"]`);
  nav.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  nav.parentElement.querySelectorAll(":scope > .tab-body").forEach((p) => p.classList.toggle("active", p.dataset.panel === tab));
  if (tab === "submissions" && !$("#sub-view").hidden) subViewer.refresh();
}

document.querySelectorAll(".tabs").forEach((nav) => {
  nav.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-tab]");
    if (b) showTab(nav.dataset.group, b.dataset.tab);
  });
});

// ---------- problem list ----------

async function loadList() {
  state.problems = await api("/api/problems");
  renderList();
}

function renderList() {
  if (!state.problems.length) {
    $("#problem-list").innerHTML = `<p class="muted pad">No problems yet.</p>`;
    return;
  }
  let html = "", set = null;
  for (const p of state.problems) {
    if (p.set !== set) {
      if (set !== null) html += `</ul>`;
      set = p.set;
      html += `<div class="set-head">${esc(set)}</div><ul>`;
    }
    const statusTitle = { solved: "Solved", attempted: "Attempted", new: "Not tried yet" }[p.status] || "";
    html += `
      <li data-id="${esc(p.id)}" class="${p.id === state.current ? "active" : ""}" title="${esc(p.title)}">
        <span class="dot ${esc(p.status)}" title="${statusTitle}"></span>
        <span class="num">${Number(p.number)}.</span>
        <span class="name">${esc(p.title)}</span>
        ${p.example ? `<span class="tag" title="Hand-made example problem">example</span>` : ""}
        ${p.fails > 0 ? `<span class="fails" title="${p.fails} failed submission${p.fails === 1 ? "" : "s"}">${p.fails}</span>` : ""}
      </li>`;
  }
  html += `</ul>`;
  $("#problem-list").innerHTML = html;
}

$("#problem-list").addEventListener("click", (e) => {
  const li = e.target.closest("li[data-id]");
  if (li) location.hash = li.dataset.id;
});

// ---------- open a problem ----------

const RESULT_EMPTY = () => `<p class="muted">Submit to check your solution. Shortcut: ${SUBMIT_KEY}</p>`;
const OUTPUT_EMPTY = () => hasScratch()
  ? `<p class="muted">Run executes <code>scratch.m</code>, which calls your function. Shortcut: ${RUN_KEY}</p>`
  : `<p class="muted">Run executes <code>${esc(fileName("code"))}</code>. Shortcut: ${RUN_KEY}</p>`;

async function openProblem(id) {
  await save();
  let p;
  try {
    p = await api(`/api/problems/${encodeURIComponent(id)}`);
  } catch (e) {
    $("#statement").innerHTML = `<pre class="block stderr">${esc(e.message)}</pre>`;
    return;
  }
  state.current = id;
  state.detail = p;
  state.resultSid = null;
  state.issues = { code: [], scratch: [] };
  document.title = `${p.title} · MATLAB Practice`;

  renderDescription();

  editors.code.cm.setValue(p.code || "");
  editors.code.cm.clearHistory();
  editors.scratch.cm.setValue(p.scratch || "");
  editors.scratch.cm.clearHistory();
  state.dirty = false;
  setSaveState("");
  switchFile("code");
  $("#run-btn").title = hasScratch() ? `Run scratch.m, which calls your function (${RUN_KEY})` : `Run ${p.file} (${RUN_KEY})`;
  $("#submit-btn").title = `Check ${p.file} against the tests (${SUBMIT_KEY})`;

  renderSubs();
  closeSub();
  $("#result").innerHTML = RESULT_EMPTY();
  $("#output").innerHTML = OUTPUT_EMPTY();
  showTab("left", "description");
  showTab("console", "result");
  renderList();
  for (const s of p.submissions || []) if (isPending(s)) startPoll(id, s.id);
  editors.code.cm.focus();
}

function renderDescription() {
  const p = state.detail;
  $("#p-title").innerHTML = `<span class="muted">${esc(p.set)} · ${Number(p.number)}.</span> ${esc(p.title)}`;
  setMd($("#statement"), p.statement_md);
  setMd($("#submit-md"), p.submit_md);

  const hasSource = !!p.source_url;
  $("#source-toggle").hidden = !hasSource;
  if (hasSource) {
    $("#source-img").src = p.source_url;
    $("#source-link").href = p.source_url;
  } else {
    $("#source-img").removeAttribute("src");
  }
  applySourceToggle();

  const ctx = p.context || [];
  $("#context").innerHTML = ctx.map((c, i) => {
    const meta = state.problems.find((x) => x.id === c.id);
    const label = meta ? `${esc(meta.set)} · ${Number(meta.number)}. ${esc(c.title)}` : esc(c.title);
    return `<details class="context-block"><summary>Refers to: ${label}</summary><div class="markdown" data-ctx="${i}"></div></details>`;
  }).join("");
  ctx.forEach((c, i) => setMd($(`#context [data-ctx="${i}"]`), c.statement_md));

  renderHintStatus();
}

function applySourceToggle() {
  const on = state.showSource && !!(state.detail && state.detail.source_url);
  $("#source-box").hidden = !on;
  $("#source-toggle").textContent = on ? "Hide original" : "Show original";
}
$("#source-toggle").addEventListener("click", () => { state.showSource = !state.showSource; applySourceToggle(); });

function renderHintStatus() {
  const p = state.detail;
  if (!p) return;
  const t = p.hint_threshold || 5;
  const f = p.fails || 0;
  $("#hint-status").innerHTML = f >= t
    ? `<span class="hint-on">Hints are on</span> — each failed submission now comes with a hint (${f} failed).`
    : `Hints unlock after ${t} failed submissions (${f}/${t}).`;
}

function route() {
  const id = decodeURIComponent(location.hash.slice(1));
  const target = state.problems.find((p) => p.id === id) || state.problems[0];
  if (target && target.id !== state.current) openProblem(target.id);
}
window.addEventListener("hashchange", route);

// ---------- result rendering (shared by Result panel and Submissions tab) ----------

function isPending(s) { return s.verdict === "pending" || (s.review && s.review.status === "pending"); }

function figuresHTML(figs) {
  if (!figs || !figs.length) return "";
  return `<div class="out-label">Figures</div><div class="figures">${figs.map((u, i) =>
    `<a href="${esc(u)}" target="_blank" rel="noopener"><img src="${esc(u)}" alt="Figure ${i + 1}" loading="lazy"></a>`).join("")}</div>`;
}

function issuesHTML(issues, intro) {
  if (!issues || !issues.length) return "";
  return `<div class="issues"><div class="issues-intro">${esc(intro)}</div><ul>${issues.map((i) =>
    `<li>${i.file ? `<span class="muted">${esc(i.file)}</span> ` : ""}line ${Number(i.line)}: ${esc(i.message)}</li>`).join("")}</ul></div>`;
}

function caseHTML(c, open) {
  const bad = c.status !== "passed";
  const field = (label, val, hiddenIfNull) => {
    if (val === null || val === undefined) {
      return hiddenIfNull ? `<div class="kv"><span class="k">${label}</span><span class="v hidden-val">hidden</span></div>` : "";
    }
    return `<div class="kv"><span class="k">${label}</span><pre class="v">${esc(val)}</pre></div>`;
  };
  const body = bad ? `<div class="case-body">
      ${field("Input", c.input, false)}
      ${field("Expected", c.expected, true)}
      ${field("Your output", c.actual, false)}
      ${c.message ? `<div class="kv"><span class="k">Message</span><pre class="v msg-text">${esc(c.message)}</pre></div>` : ""}
    </div>` : "";
  return `<details class="test ${esc(c.status)}" ${bad && open ? "open" : ""}>
    <summary><span class="mark">${bad ? "✗" : "✓"}</span><span class="case-name">${esc(c.name)}</span>
      ${bad && c.message ? `<span class="msg">${esc(String(c.message).split("\n")[0])}</span>` : ""}</summary>
    ${body}
  </details>`;
}

function reviewHTML(r, verdict) {
  r = r || { status: "unavailable" };
  let body;
  if (r.status === "pending") {
    body = `<p class="muted"><span class="spinner"></span>Claude is reading your code…</p>`;
  } else if (r.status === "done") {
    const chips = [];
    if (r.matlab_ok === false) chips.push(`<span class="chip bad">Uses non-MATLAB syntax</span>`);
    if (r.gaming === true) chips.push(`<span class="chip bad">Works around the tests</span>`);
    if (r.rules_ok === false) chips.push(`<span class="chip bad">Breaks the problem's rules</span>`);
    if (!chips.length) chips.push(`<span class="chip ok">Clean MATLAB, no tricks</span>`);
    body = `<div class="chips">${chips.join("")}</div>
      ${r.summary ? `<div class="markdown review-summary">${renderMd(r.summary, { safe: true })}</div>` : ""}
      ${r.notes && r.notes.length ? `<ul class="review-notes">${r.notes.map((n) => `<li>${renderMd(n, { safe: true }).replace(/^<p>|<\/p>\s*$/g, "")}</li>`).join("")}</ul>` : ""}`;
  } else if (r.status === "skipped") {
    body = `<p class="muted">Not reviewed${verdict === "blocked" ? " — fix the MATLAB issues first." : "."}</p>`;
  } else {
    body = `<p class="muted">Not reviewed (Claude isn't available right now — Claude Code missing, not signed in, or offline).</p>`;
  }
  return `<section class="block-card review ${verdict === "flagged" ? "flagged" : ""}"><h3>Claude review</h3>${body}</section>`;
}

function hintHTML(h) {
  if (!h) return "";
  return `<section class="block-card hint"><h3>${bulbSVG()} Hint <span class="muted">level ${Number(h.level)} of 3</span></h3>
    <div class="markdown">${renderMd(h.text, { safe: true })}</div></section>`;
}

function bulbSVG() {
  return `<svg class="bulb" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M8 1a5 5 0 0 0-3 9c.6.5 1 1.1 1 1.8V12h4v-.2c0-.7.4-1.3 1-1.8A5 5 0 0 0 8 1zm-2 12v.5c0 .8.7 1.5 1.5 1.5h1c.8 0 1.5-.7 1.5-1.5V13H6z"/></svg>`;
}

function resultHTML(s) {
  const v = s.verdict;
  const pending = v === "pending";
  let html = `<div class="summary">
    <span class="verdict ${esc(v)}">${pending ? `<span class="spinner"></span>` : ""}${esc(VERDICT_LABEL[v] || v)}</span>
    ${s.total ? `<span class="muted">${Number(s.passed)}/${Number(s.total)} tests passed</span>` : ""}
  </div>`;
  if (pending) html += `<p class="muted">All tests passed. Claude is checking the code itself before it counts as solved.</p>`;
  if (v === "flagged") html += `<p class="flag-note">The tests pass, but Claude found a problem with how it was solved. See the review below.</p>`;
  if (v === "blocked") html += issuesHTML(s.issues, "Fix these before submitting:");
  if (s.error) html += `<div class="out-label">Error</div><pre class="block stderr">${esc(s.error)}</pre>`;

  const cases = s.cases || [];
  if (cases.length) {
    const bad = cases.filter((c) => c.status !== "passed");
    const good = cases.filter((c) => c.status === "passed");
    html += `<div class="out-label">Test cases</div>` + [...bad, ...good].map((c, i) => caseHTML(c, i < 3)).join("");
  }
  if (s.stdout) html += `<div class="out-label">Printed output</div><pre class="block">${esc(s.stdout)}</pre>`;
  html += figuresHTML(s.figures);
  if (v !== "blocked" || (s.review && s.review.status !== "skipped")) html += reviewHTML(s.review, v);
  html += hintHTML(s.hint);
  return html;
}

function renderInto(el, s) {
  el.innerHTML = resultHTML(s);
  typeset(el);
}

// ---------- run ----------

function setBusy(on, label) {
  state.busy = on;
  $("#run-btn").disabled = on;
  $("#submit-btn").disabled = on;
  setSaveState(on ? label : state.dirty ? "Unsaved" : "Saved");
}

async function run() {
  if (!state.current || state.busy) return;
  clearTimeout(state.saveTimer);
  setBusy(true, "Running…");
  showTab("console", "output");
  $("#output").innerHTML = `<p class="muted"><span class="spinner"></span>Running ${esc(hasScratch() ? "scratch.m" : fileName("code"))} in Octave…</p>`;
  const pid = state.current;
  try {
    const body = payload();
    state.dirty = false;
    const r = await api(`/api/problems/${pid}/run`, body);
    if (pid !== state.current) return;
    let html = "";
    if (r.blocked) {
      html += issuesHTML(r.issues, "Fix these before running:");
    } else {
      if (r.stdout) html += `<div class="out-label">Output</div><pre class="block">${esc(r.stdout)}</pre>`;
      if (r.stderr) html += `<div class="out-label">Warnings / stderr</div><pre class="block stderr">${esc(r.stderr)}</pre>`;
      if (r.error) html += `<div class="out-label">Error</div><pre class="block stderr">${esc(r.error)}</pre>`;
      html += figuresHTML(r.figures);
      if (r.timed_out) html += `<p class="stopped">Stopped after ${Math.round(r.seconds || 0)}s — is there a loop that never ends?</p>`;
      if (!html) html = `<p class="muted">No output. Leave the semicolon off a line (or use <code>disp</code>) to print a value.</p>`;
      if (!r.timed_out && r.seconds != null) html += `<p class="muted small">Finished in ${Number(r.seconds).toFixed(1)}s</p>`;
    }
    $("#output").innerHTML = html;
  } catch (e) {
    markDirty();
    $("#output").innerHTML = `<pre class="block stderr">${esc(e.message)}</pre>`;
  } finally {
    setBusy(false);
  }
}

// ---------- submit + polling ----------

async function submit() {
  if (!state.current || state.busy) return;
  clearTimeout(state.saveTimer);
  setBusy(true, "Checking…");
  showTab("console", "result");
  $("#result").innerHTML = `<p class="muted"><span class="spinner"></span>Running the tests in Octave…</p>`;
  const pid = state.current;
  try {
    const body = payload();
    state.dirty = false;
    const s = await api(`/api/problems/${pid}/submit`, body);
    if (pid !== state.current) return;
    state.resultSid = s.id;
    renderInto($("#result"), s);
    upsertSub(s);
    applyFails(s);
    refreshList();
    if (isPending(s)) startPoll(pid, s.id);
  } catch (e) {
    markDirty();
    $("#result").innerHTML = `<pre class="block stderr">${esc(e.message)}</pre>`;
  } finally {
    setBusy(false);
  }
}

function summaryOf(s) {
  const { code, cases, stdout, ...rest } = s;
  return rest;
}

function upsertSub(s) {
  if (!state.detail) return;
  const subs = state.detail.submissions || (state.detail.submissions = []);
  const i = subs.findIndex((x) => x.id === s.id);
  if (i >= 0) subs[i] = summaryOf(s); else subs.unshift(summaryOf(s));
  renderSubs();
}

function applyFails(s) {
  if (state.detail && typeof s.fails_after === "number") {
    state.detail.fails = s.fails_after;
    renderHintStatus();
  }
}

async function refreshList() {
  try { await loadList(); } catch {}
}

function startPoll(pid, sid) {
  const key = `${pid}/${sid}`;
  if (state.polls.has(key)) return;
  const tick = async () => {
    let s;
    try {
      s = await api(`/api/problems/${pid}/submissions/${sid}`);
    } catch {
      state.polls.set(key, setTimeout(tick, POLL_MS * 2));
      return;
    }
    if (pid === state.current) {
      upsertSub(s);
      applyFails(s);
      if (state.resultSid === sid) renderInto($("#result"), s);
      if (state.viewedSub && state.viewedSub.id === sid) showSub(s);
    }
    if (isPending(s)) {
      state.polls.set(key, setTimeout(tick, POLL_MS));
    } else {
      state.polls.delete(key);
      refreshList();
    }
  };
  state.polls.set(key, setTimeout(tick, POLL_MS));
}

// ---------- submissions tab ----------

function ago(iso) {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return esc(iso);
  const s = (Date.now() - t) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function renderSubs() {
  const subs = (state.detail && state.detail.submissions) || [];
  $("#sub-count").textContent = subs.length ? subs.length : "";
  $("#sub-list").innerHTML = subs.length
    ? subs.map((s) => `
      <button class="sub-row" data-id="${esc(s.id)}">
        <span class="verdict ${esc(s.verdict)}">${s.verdict === "pending" ? `<span class="spinner"></span>Checking…` : esc(VERDICT_LABEL[s.verdict] || s.verdict)}</span>
        <span class="hint-mark" title="${s.hint ? `Came with a hint (level ${Number(s.hint.level)})` : ""}">${s.hint ? bulbSVG() : ""}</span>
        <span class="score">${s.total ? `${Number(s.passed)}/${Number(s.total)} passed` : ""}</span>
        <span class="when" title="${esc(s.time)}">${ago(s.time)}</span>
      </button>`).join("")
    : `<p class="muted pad">No submissions yet.</p>`;
}

$("#sub-list").addEventListener("click", async (e) => {
  const row = e.target.closest(".sub-row");
  if (!row) return;
  try {
    const s = await api(`/api/problems/${state.current}/submissions/${encodeURIComponent(row.dataset.id)}`);
    showSub(s);
    if (isPending(s)) startPoll(state.current, s.id);
  } catch (err) {
    $("#sub-list").insertAdjacentHTML("afterbegin", `<pre class="block stderr">${esc(err.message)}</pre>`);
  }
});

function showSub(s) {
  const first = !state.viewedSub || state.viewedSub.id !== s.id;
  state.viewedSub = s;
  $("#sub-list").hidden = true;
  $("#sub-view").hidden = false;
  $("#sub-view-meta").innerHTML = `<span class="verdict ${esc(s.verdict)}">${esc(VERDICT_LABEL[s.verdict] || s.verdict)}</span>
    ${s.total ? ` · ${Number(s.passed)}/${Number(s.total)} passed` : ""} · ${esc(new Date(s.time).toLocaleString())}`;
  if (first) {
    subViewer.setValue(s.code || "");
    subViewer.refresh();
  }
  renderInto($("#sub-result"), s);
}

function closeSub() {
  state.viewedSub = null;
  $("#sub-view").hidden = true;
  $("#sub-list").hidden = false;
}
$("#sub-back").addEventListener("click", closeSub);

$("#sub-load").addEventListener("click", () => {
  if (!state.viewedSub) return;
  const cm = editors.code.cm;
  if (cm.getValue() !== state.viewedSub.code && !confirm(`Replace the code in ${fileName("code")} with this submission?`)) return;
  cm.setValue(state.viewedSub.code || "");
  switchFile("code");
  markDirty();
  save();
  cm.focus();
});

// ---------- keys ----------

$("#run-btn").addEventListener("click", run);
$("#submit-btn").addEventListener("click", submit);
document.addEventListener("keydown", (e) => {
  const mod = e.metaKey || e.ctrlKey;
  if (!mod) return;
  if (e.key === "Enter") { e.preventDefault(); submit(); }
  else if (e.key === "'") { e.preventDefault(); run(); }
  else if (e.key === "s") { e.preventDefault(); save(); }
});

// ---------- start ----------

async function start() {
  setHighlighting(savedHighlighting());
  loadStatus();
  try {
    await loadList();
  } catch {
    $("#problem-list").innerHTML = `<p class="muted pad">Waiting for the app server…</p>`;
    setTimeout(start, 3000);
    return;
  }
  route();
  // Re-check the server and tools now and then so the banner clears / appears by itself.
  setInterval(loadStatus, 30000);
}

$("#result").innerHTML = RESULT_EMPTY();
start();
