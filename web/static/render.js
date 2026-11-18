"use strict";

// ── Markdown + maths rendering ─────────────────────────────────────────────
marked.setOptions({ gfm: true, breaks: false });
const MATH_RE = /(```[\s\S]*?(?:```|$)|`[^`\n]*`)|(\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\)|\$(?=\S)[^$\n]+?(?<=\S)\$)/g;

function renderMarkdown(md, options = {}) {
  const maths = [];
  const protectedMd = md.replace(MATH_RE, (whole, code, math) => {
    if (code) return code;
    maths.push(math);
    return `MATHPH${maths.length - 1}END`;
  });
  let html = marked.parse(protectedMd, { gfm: true, breaks: !!options.breaks });
  html = html.replace(/MATHPH(\d+)END/g, (_, i) => {
    const m = maths[+i];
    const display = m.startsWith("$$") || m.startsWith("\\[");
    const tex = display ? m.slice(2, -2) : m.startsWith("\\(") ? m.slice(2, -2) : m.slice(1, -1);
    try { return katex.renderToString(tex, { displayMode: display, throwOnError: false, output: "html" }); }
    catch { return m; }
  });
  return DOMPurify.sanitize(html);
}
