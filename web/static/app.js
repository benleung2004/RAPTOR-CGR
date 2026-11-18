"use strict";

const $ = (sel) => document.querySelector(sel);
const messagesEl = $("#messages");
const welcomeEl = $("#welcome");
const input = $("#input");
const sendBtn = $("#send");
const form = $("#composer");
const deepBox = $("#deep");
try { deepBox.checked = localStorage.getItem("deep") === "1"; } catch { /* private mode */ }
deepBox.addEventListener("change", () => { try { localStorage.setItem("deep", deepBox.checked ? "1" : "0"); } catch { /* ignore */ } });

const history = [];            // [{role, content}] kept in memory only
let controller = null;         // AbortController of the running request

// ── Theme ──────────────────────────────────────────────────────────────────
function applyTheme(theme) {
  if (theme) document.documentElement.dataset.theme = theme;
  const dark = theme ? theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  $("#hljs-light").disabled = dark;
  $("#hljs-dark").disabled = !dark;
}
function storedTheme() { try { return localStorage.getItem("theme"); } catch { return null; } }
applyTheme(storedTheme());
$("#theme").addEventListener("click", () => {
  const current = document.documentElement.dataset.theme ||
    (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const next = current === "dark" ? "light" : "dark";
  try { localStorage.setItem("theme", next); } catch { /* private mode */ }
  applyTheme(next);
});

function linkCitations(root, sourceCount, onCite) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => n.parentElement.closest("pre, code, .katex") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT,
  });
  const nodes = [];
  while (walker.nextNode()) if (/\[\d{1,2}\]/.test(walker.currentNode.nodeValue)) nodes.push(walker.currentNode);
  for (const node of nodes) {
    const frag = document.createDocumentFragment();
    let last = 0;
    node.nodeValue.replace(/\[(\d{1,2})\]/g, (whole, n, offset) => {
      frag.append(node.nodeValue.slice(last, offset));
      const num = +n;
      if (num >= 1 && num <= sourceCount) {
        const a = document.createElement("a");
        a.href = "#"; a.className = "cite"; a.textContent = n; a.title = `Show textbook source ${n}`;
        a.addEventListener("click", (e) => { e.preventDefault(); onCite(num); });
        frag.append(a);
      } else frag.append(whole);
      last = offset + whole.length;
    });
    frag.append(node.nodeValue.slice(last));
    node.replaceWith(frag);
  }
}

function decorateCode(root, final) {
  root.querySelectorAll("pre code").forEach((block) => {
    if (final) { try { hljs.highlightElement(block); } catch { /* unknown language */ } }
    const pre = block.parentElement;
    if (pre.querySelector(".copy-code")) return;
    const btn = document.createElement("button");
    btn.type = "button"; btn.className = "copy-code"; btn.textContent = "Copy";
    btn.addEventListener("click", () => copyText(block.innerText, btn));
    pre.append(btn);
  });
}

function copyText(text, btn) {
  navigator.clipboard.writeText(text).then(() => {
    const old = btn.textContent; btn.textContent = "Copied"; setTimeout(() => (btn.textContent = old), 1200);
  });
}

// ── Messages ───────────────────────────────────────────────────────────────
function addUserMessage(text) {
  const el = document.createElement("div");
  el.className = "msg user";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  el.append(bubble);
  messagesEl.append(el);
}

function addAssistantMessage() {
  const el = document.createElement("div");
  el.className = "msg assistant";
  el.innerHTML = `<div class="avatar" aria-hidden="true"></div>
    <div class="body"><div class="answer waiting"></div><div class="meta"></div></div>`;
  messagesEl.append(el);
  return { el, answer: el.querySelector(".answer"), meta: el.querySelector(".meta"), body: el.querySelector(".body") };
}

function renderSources(view, sources) {
  const details = document.createElement("details");
  details.className = "sources";
  details.innerHTML = `<summary>${sources.length} textbook sources</summary>`;
  sources.forEach((s, i) => {
    const card = document.createElement("div");
    card.className = "source";
    card.id = `${view.id}-src-${i + 1}`;
    const head = document.createElement("div");
    head.innerHTML = `<span class="cite">${i + 1}</span> <span class="src-title"></span>`;
    head.querySelector(".src-title").textContent = s.title;
    const section = document.createElement("div");
    section.className = "src-section";
    section.textContent = s.section ? `Section: ${s.section}` : "";
    const text = document.createElement("div");
    text.className = "src-text";
    text.textContent = s.text;
    const more = document.createElement("button");
    more.type = "button"; more.className = "more"; more.textContent = "Show full passage";
    more.addEventListener("click", () => {
      card.classList.toggle("expanded");
      more.textContent = card.classList.contains("expanded") ? "Show less" : "Show full passage";
    });
    const actions = document.createElement("div");
    actions.className = "src-actions";
    actions.append(more);
    if (Number.isInteger(s.id)) {
      const open = document.createElement("a");
      open.className = "open-book";
      open.href = `/read?chunk=${s.id}`;
      open.target = "_blank";
      open.rel = "noopener";
      open.textContent = "Open in textbook ↗";
      actions.append(open);
    }
    card.append(head, section, text, actions);
    details.append(card);
  });
  view.body.append(details);
  view.sourcesEl = details;
}

function showSource(view, n) {
  if (!view.sourcesEl) return;
  view.sourcesEl.open = true;
  const card = document.getElementById(`${view.id}-src-${n}`);
  if (!card) return;
  card.scrollIntoView({ behavior: "smooth", block: "center" });
  card.classList.add("flash");
  setTimeout(() => card.classList.remove("flash"), 1500);
}

function scrollToBottom() {
  const nearBottom = window.innerHeight + window.scrollY >= document.body.scrollHeight - 160;
  if (nearBottom) window.scrollTo({ top: document.body.scrollHeight });
}

// ── Streaming request ──────────────────────────────────────────────────────
let viewCounter = 0;

async function ask(question) {
  welcomeEl.hidden = true;
  addUserMessage(question);
  const view = addAssistantMessage();
  view.id = `m${++viewCounter}`;
  const deep = deepBox.checked;
  const waitStart = Date.now();
  view.answer.dataset.wait = "Searching the textbooks…";
  const waitTimer = setInterval(() => {
    if (!view.answer.classList.contains("waiting")) return clearInterval(waitTimer);
    const secs = Math.round((Date.now() - waitStart) / 1000);
    if (view.answer.classList.contains("has-sources")) {
      view.answer.dataset.wait = deep
        ? `Deep reasoning: working through the problem before writing… ${secs} s (usually 30–60 s)`
        : `Writing the answer… ${secs} s`;
    }
  }, 500);
  window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });

  let text = "", sources = [], frame = null;
  const draw = (final) => {
    frame = null;
    view.answer.innerHTML = renderMarkdown(text);
    linkCitations(view.answer, sources.length, (n) => showSource(view, n));
    decorateCode(view.answer, final);
    scrollToBottom();
  };

  setBusy(true);
  controller = new AbortController();
  const priorHistory = history.slice(-4);
  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history: priorHistory, mode: deep ? "deep" : "fast" }),
      signal: controller.signal,
    });
    if (!resp.ok) {
      let msg = `Request failed (${resp.status}).`;
      try { const j = await resp.json(); if (typeof j.detail === "string") msg = j.detail; } catch { /* not JSON */ }
      throw new Error(msg);
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sep;
      while ((sep = buffer.indexOf("\n\n")) >= 0) {
        const raw = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const event = /^event: (.*)$/m.exec(raw)?.[1];
        const dataLine = /^data: (.*)$/m.exec(raw)?.[1];
        if (!event || dataLine === undefined) continue;
        const data = JSON.parse(dataLine);
        if (event === "sources") {
          sources = data;
          view.answer.classList.add("has-sources");
          renderSources(view, sources);
        } else if (event === "delta") {
          text += data;
          view.answer.classList.remove("waiting");
          if (!frame) frame = requestAnimationFrame(() => draw(false));
        } else if (event === "done") {
          showMeta(view, data, text);
        } else if (event === "error") {
          throw new Error(data);
        }
      }
    }
    if (frame) cancelAnimationFrame(frame);
    draw(true);
    if (text) {
      history.push({ role: "user", content: question }, { role: "assistant", content: text });
    }
  } catch (err) {
    if (frame) cancelAnimationFrame(frame);
    if (text) draw(true);
    view.answer.classList.remove("waiting");
    const note = document.createElement("div");
    note.className = "error";
    note.textContent = err.name === "AbortError" ? "Stopped." : err.message || "Network error - please try again.";
    view.answer.append(note);
  } finally {
    clearInterval(waitTimer);
    controller = null;
    setBusy(false);
  }
}

function showMeta(view, stats, text) {
  const seconds = (stats.total_ms / 1000).toFixed(1);
  const parts = [`${seconds} s`];
  if (stats.cached) parts.push("cached");
  else if (stats.model) parts.push(stats.model);
  view.meta.textContent = parts.join(" · ");
  if (stats.mode === "deep") {
    const badge = document.createElement("span");
    badge.className = "mode-badge"; badge.textContent = "deep reasoning";
    view.meta.prepend(badge);
  }
  const copy = document.createElement("button");
  copy.type = "button"; copy.textContent = "Copy answer";
  copy.addEventListener("click", () => copyText(text, copy));
  view.meta.append(copy);
}

function setBusy(busy) {
  sendBtn.textContent = busy ? "Stop" : "Send";
  sendBtn.classList.toggle("stop", busy);
  sendBtn.type = busy ? "button" : "submit";
  updateSendState();
}
function updateSendState() { sendBtn.disabled = !controller && !input.value.trim(); }

// ── Input handling ─────────────────────────────────────────────────────────
function autoGrow() { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 200) + "px"; }
input.addEventListener("input", () => { autoGrow(); updateSendState(); });
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); }
});
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const q = input.value.trim();
  if (!q || controller) return;
  input.value = ""; autoGrow(); updateSendState();
  ask(q);
});
sendBtn.addEventListener("click", () => { if (controller) controller.abort(); });
document.querySelectorAll(".example").forEach((b) => b.addEventListener("click", () => {
  if (controller) return;
  ask(b.textContent.trim());
}));
$("#new-chat").addEventListener("click", () => {
  if (controller) controller.abort();
  history.length = 0;
  messagesEl.innerHTML = "";
  welcomeEl.hidden = false;
  input.focus();
});
updateSendState();
input.focus();
