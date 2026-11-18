"use strict";

(function theme() {
  try { const t = localStorage.getItem("theme"); if (t) document.documentElement.dataset.theme = t; } catch { /* ignore */ }
})();

const passagesEl = document.getElementById("passages");
const earlierBtn = document.getElementById("earlier");
const laterBtn = document.getElementById("later");
const focusId = Number(new URLSearchParams(location.search).get("chunk"));
let firstId = null, lastId = null;

function passageEl(chunk) {
  const el = document.createElement("article");
  el.className = "passage" + (chunk.id === focusId ? " focus" : "");
  el.dataset.id = chunk.id;
  const section = document.createElement("div");
  section.className = "p-section";
  section.textContent = chunk.section || "Excerpt";
  const body = document.createElement("div");
  body.innerHTML = renderMarkdown(chunk.text, { breaks: true });   // keep textbook line breaks (pseudocode)
  el.append(section, body);
  return el;
}

async function load(id, before, after) {
  const resp = await fetch(`/api/context/${id}?before=${before}&after=${after}`);
  if (!resp.ok) throw new Error(resp.status === 404 ? "This passage was not found." : `Request failed (${resp.status}).`);
  return resp.json();
}

async function init() {
  if (!Number.isInteger(focusId)) throw new Error("No passage selected.");
  const data = await load(focusId, 3, 3);
  document.title = `${data.title} · CS Textbook Tutor`;
  document.getElementById("book-title").textContent = data.title;
  document.getElementById("full-text").href = data.full_text_url;
  document.getElementById("github").href = data.github_url;
  data.chunks.forEach((c) => passagesEl.append(passageEl(c)));
  firstId = data.chunks[0].id; lastId = data.chunks.at(-1).id;
  earlierBtn.hidden = !data.has_before; laterBtn.hidden = !data.has_after;
  passagesEl.querySelector(".focus")?.scrollIntoView({ block: "center" });
}

earlierBtn.addEventListener("click", async () => {
  const data = await load(firstId, 5, 0);
  const older = data.chunks.filter((c) => c.id < firstId);
  const anchor = passagesEl.firstChild;
  older.forEach((c) => passagesEl.insertBefore(passageEl(c), anchor));
  if (older.length) firstId = older[0].id;
  earlierBtn.hidden = !data.has_before;
});

laterBtn.addEventListener("click", async () => {
  const data = await load(lastId, 0, 5);
  const newer = data.chunks.filter((c) => c.id > lastId);
  newer.forEach((c) => passagesEl.append(passageEl(c)));
  if (newer.length) lastId = newer.at(-1).id;
  laterBtn.hidden = !data.has_after;
});

init().catch((e) => {
  const err = document.getElementById("error");
  err.textContent = e.message; err.hidden = false;
  document.getElementById("book-title").textContent = "Passage unavailable";
});
