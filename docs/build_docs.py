"""
Static HTML documentation generator for Vigil (additive, no runtime deps).

Scans the repository, specs, and API to emit a single self-contained
`docs/pages/reference.html` covering structure, modules, functions, endpoints, and specs.
Output: `docs/pages/reference.html` (linked from the guide built by `docs/build_site.py`).
Run:  python docs/build_site.py   (builds the guide and calls this)
"""

from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPECS = ROOT / "specs"
DOCS = ROOT / "docs"

# Directories shown in the structure/modules views (curated, code-only).
_CODE_DIRS = [
    "levels",
    "levels/foundations",
    "levels/themes",
    "architectures",
    "architectures/frameworks",
    "reliability",
    "vigil",
    "vigil/routers",
    "vigil_mcp",
    "ui",
    "tests",
]

# Modules whose public functions are surfaced in the "Key modules" section.
_KEY_MODULES = [
    ("levels/l0_single_call.py", "L0 — single LLM call"),
    ("levels/l1_chain.py", "L1 — prompt chain + structured output"),
    ("levels/l4_tool_use.py", "L4 — tool use / ReAct loop"),
    ("levels/l5_memory.py", "L5 — memory & feedback"),
    ("levels/l6_autonomous.py", "L6 — autonomous monitor"),
    ("levels/foundations/retrieval_quality.py", "F11/F12/F16 — retrieval + metrics + hybrid"),
    ("levels/foundations/factuality.py", "F13 — factuality / citations"),
    ("levels/foundations/finetuning.py", "F21 — build-vs-tune advisor"),
    ("levels/foundations/model_selection.py", "F22 — Claude model selection"),
    ("reliability/r1_guardrails.py", "R1 — guardrails"),
    ("reliability/r6_online_eval_drift.py", "F17 — online drift"),
    ("reliability/r9_release_safety.py", "F20 — release safety"),
    ("vigil/inference.py", "Inference seam (providers/routing/fallback)"),
    ("vigil/claude_provider.py", "Claude Messages bridge"),
    ("vigil_mcp/vigil_client.py", "MCP client path"),
]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _natural_key(s: str):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


# ─── Specs ─────────────────────────────────────────────────────────────────

def _spec_meta(path: Path) -> dict[str, str]:
    text = _read(path)
    title = path.stem
    status = "Unknown"
    concept = ""
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break
    m = re.search(r"- \*\*Status:\*\*\s*(.+)", text)
    if m:
        status = m.group(1).strip()
    tm = re.search(r"## Teaching Goal\s*\n+\*\*(.+?)\*\*", text, re.DOTALL)
    if tm:
        concept = tm.group(1).strip().replace("\n", " ")
    return {"file": path.name, "title": title, "status": status, "concept": concept}


def _group(prefix: str) -> list[dict[str, str]]:
    return [_spec_meta(p) for p in sorted(SPECS.glob(f"{prefix}*.md"), key=lambda x: _natural_key(x.stem))]


def _badge(status: str) -> str:
    color = {
        "Done": "#16a34a",
        "Implemented": "#16a34a",
        "Approved": "#2563eb",
        "In Progress": "#d97706",
        "Draft": "#6b7280",
    }.get(status, "#6b7280")
    return f'<span class="badge" style="background:{color}">{html.escape(status)}</span>'


def _spec_table(title: str, rows: list[dict[str, str]]) -> str:
    if not rows:
        return ""
    body = "\n".join(
        f"<tr><td class='code'>{html.escape(r['file'])}</td>"
        f"<td>{html.escape(r['title'])}</td>"
        f"<td>{_badge(r['status'])}</td>"
        f"<td>{html.escape(r['concept'])}</td></tr>"
        for r in rows
    )
    anchor = title.split()[0].lower()
    return f"""
    <section id="spec-{anchor}">
      <h2>{html.escape(title)}</h2>
      <table>
        <thead><tr><th>Spec</th><th>Title</th><th>Status</th><th>Teaching goal</th></tr></thead>
        <tbody>{body}</tbody>
      </table>
    </section>
    """


# ─── Repository structure ──────────────────────────────────────────────────

def _structure() -> str:
    lines: list[str] = ["vigil/"]
    for d in _CODE_DIRS:
        p = ROOT / d
        if not p.exists():
            continue
        files = sorted(f.name for f in p.glob("*.py") if f.name != "__init__.py")
        lines.append(f"├── {d}/")
        for f in files:
            lines.append(f"│     {f}")
    tree = html.escape("\n".join(lines))
    return f"""
    <section id="structure">
      <h2>Repository structure</h2>
      <p class="muted">Auto-scanned Python modules by area (excludes caches and generated files).</p>
      <pre class="tree">{tree}</pre>
    </section>
    """


# ─── API endpoints ─────────────────────────────────────────────────────────

def _api_routes() -> list[dict[str, str]]:
    # Routes live in vigil/routers/*.py (and, for older layouts, vigil/api.py).
    files = sorted((ROOT / "vigil" / "routers").glob("*.py")) + [ROOT / "vigil" / "api.py"]
    routes: list[dict[str, str]] = []
    pat = re.compile(r'@(?:app|router)\.(get|post|delete|put)\(\s*"([^"]+)"')
    for f in files:
        lines = _read(f).splitlines()
        for i, line in enumerate(lines):
            m = pat.search(line)
            if not m:
                continue
            method, path = m.group(1).upper(), m.group(2)
            summary = ""
            for j in range(i + 1, min(i + 8, len(lines))):
                ds = re.search(r'"""\s*(.+)', lines[j])
                if ds:
                    summary = ds.group(1).strip().rstrip('"').strip()
                    break
            routes.append({"method": method, "path": path, "summary": summary})
    return routes


def _api_section() -> str:
    routes = _api_routes()
    body = "\n".join(
        f"<tr><td class='code'>{r['method']}</td>"
        f"<td class='code'>{html.escape(r['path'])}</td>"
        f"<td>{html.escape(r['summary'])}</td></tr>"
        for r in routes
    )
    return f"""
    <section id="api">
      <h2>API endpoints <span class="muted">({len(routes)})</span></h2>
      <table>
        <thead><tr><th>Method</th><th>Path</th><th>Purpose</th></tr></thead>
        <tbody>{body}</tbody>
      </table>
    </section>
    """


# ─── Key modules & functions ───────────────────────────────────────────────

def _public_functions(rel: str, limit: int = 8) -> list[str]:
    text = _read(ROOT / rel)
    names = re.findall(r"^(?:async def|def)\s+([a-zA-Z][a-zA-Z0-9_]*)\(", text, re.MULTILINE)
    return [n for n in names if not n.startswith("_")][:limit]


def _modules_section() -> str:
    rows = []
    for rel, desc in _KEY_MODULES:
        if not (ROOT / rel).exists():
            continue
        funcs = ", ".join(f"{n}()" for n in _public_functions(rel)) or "—"
        rows.append(
            f"<tr><td class='code'>{html.escape(rel)}</td>"
            f"<td>{html.escape(desc)}</td>"
            f"<td class='code small'>{html.escape(funcs)}</td></tr>"
        )
    return f"""
    <section id="modules">
      <h2>Key modules &amp; functions</h2>
      <table>
        <thead><tr><th>Module</th><th>Role</th><th>Public functions</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>
    """


# ─── How to run ────────────────────────────────────────────────────────────

def _run_section() -> str:
    return """
    <section id="run">
      <h2>How to run</h2>
      <pre class="tree"># Install (choose extras as needed)
pip install -e .              # L0-L4 core
pip install -e ".[full]"      # API + UI
pip install -e ".[claude]"    # optional Anthropic bridge

# API server
uvicorn vigil.api:app --reload

# Learning UI
streamlit run ui/app.py

# Tests
python -m pytest -q

# Regenerate this documentation
python docs/build_docs.py</pre>
    </section>
    """


# ─── Cert mapping ──────────────────────────────────────────────────────────

CERT_ROWS = [
    ("Agentic Architecture & Orchestration", "27%", "Strong", "L0-L6, A1-A4"),
    ("Prompt Engineering & Structured Output", "20%", "Strong", "F6, L1 structured output"),
    ("Tool Design & MCP Integration", "18%", "Strong", "L4, F8, MCP client (F22)"),
    ("Context Management & Reliability", "15%", "Strong", "F5, R1-R5, F17"),
    ("Claude Code Configuration & Workflows", "20%", "External", "Anthropic Academy"),
]


def _cert_table() -> str:
    body = "\n".join(
        f"<tr><td>{html.escape(d)}</td><td>{w}</td><td>{html.escape(c)}</td><td>{html.escape(m)}</td></tr>"
        for d, w, c, m in CERT_ROWS
    )
    return f"""
    <section id="cert">
      <h2>Claude Certified Architect - Foundations mapping</h2>
      <table>
        <thead><tr><th>Domain</th><th>Weight</th><th>Coverage</th><th>Where</th></tr></thead>
        <tbody>{body}</tbody>
      </table>
      <p class="muted">Claude-branded specifics (Claude Code, Messages API, model tiers,
      Bedrock/Vertex) also need Anthropic Academy courses; this project covers the
      transferable architecture, RAG, evaluation, and governance foundations.</p>
    </section>
    """


# ─── Page ──────────────────────────────────────────────────────────────────

def build() -> Path:
    board = _read(SPECS / "progress-board.md")
    suite = ""
    sm = re.search(r"Full suite:\s*\*\*(.+?)\*\*", board)
    if sm:
        suite = sm.group(1)

    reliability = _group("R")
    extensions = _group("E")
    foundations = _group("F")
    themes = _group("T")
    total = len(reliability) + len(extensions) + len(foundations) + len(themes)
    n_routes = len(_api_routes())

    nav = """
    <nav>
      <a href="../index.html">← Back to the guide</a>
      <a href="#structure">Structure</a>
      <a href="#modules">Modules</a>
      <a href="#api">API</a>
      <a href="#run">Run</a>
      <a href="#spec-reliability">Specs</a>
      <a href="#cert">Cert</a>
    </nav>
    """

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Vigil — GenAI Learning Lab Documentation</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
         line-height:1.6; color:#0f172a; background:#f8fafc; }}
  header {{ background:linear-gradient(135deg,#1e1b4b,#4c1d95); color:#fff; padding:48px 24px; }}
  header h1 {{ margin:0 0 8px; font-size:2rem; }}
  header p {{ margin:0; opacity:.9; }}
  nav {{ position:sticky; top:0; background:#111827; padding:10px 24px; display:flex; gap:18px; flex-wrap:wrap; z-index:5; }}
  nav a {{ color:#c7d2fe; text-decoration:none; font-size:.9rem; font-weight:600; }}
  nav a:hover {{ color:#fff; }}
  main {{ max-width:1040px; margin:0 auto; padding:24px; }}
  section {{ background:#fff; border:1px solid #e2e8f0; border-radius:12px; padding:20px 24px; margin:18px 0; }}
  h2 {{ margin-top:0; color:#4c1d95; font-size:1.25rem; }}
  table {{ width:100%; border-collapse:collapse; font-size:.92rem; }}
  th, td {{ text-align:left; padding:8px 10px; border-bottom:1px solid #eef2f7; vertical-align:top; }}
  th {{ color:#64748b; font-weight:600; }}
  .code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size:.85rem; color:#334155; }}
  .small {{ font-size:.78rem; }}
  .badge {{ color:#fff; padding:2px 8px; border-radius:999px; font-size:.72rem; font-weight:700; }}
  .stats {{ display:flex; gap:16px; flex-wrap:wrap; }}
  .stat {{ background:#fff; border:1px solid #e2e8f0; border-radius:12px; padding:16px 20px; flex:1; min-width:150px; }}
  .stat .n {{ font-size:1.5rem; font-weight:800; color:#4c1d95; }}
  .muted {{ color:#64748b; font-size:.88rem; }}
  pre.tree {{ background:#0f172a; color:#e2e8f0; padding:16px 18px; border-radius:10px; overflow:auto;
             font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size:.82rem; line-height:1.5; }}
  footer {{ text-align:center; color:#94a3b8; padding:24px; font-size:.85rem; }}
</style>
</head>
<body>
<header>
  <h1>🛡️ Vigil — GenAI Learning Lab</h1>
  <p>From a single LLM call to autonomous agents — with reliability, governance, and Claude-architect foundations.</p>
</header>
{nav}
<main>
  <div class="stats">
    <div class="stat"><div class="n">{total}</div><div class="muted">documented specs</div></div>
    <div class="stat"><div class="n">L0-L6</div><div class="muted">capability levels</div></div>
    <div class="stat"><div class="n">A1-A4</div><div class="muted">architectures</div></div>
    <div class="stat"><div class="n">{n_routes}</div><div class="muted">API endpoints</div></div>
    <div class="stat"><div class="n">{html.escape(suite or 'green')}</div><div class="muted">test suite</div></div>
  </div>
  {_structure()}
  {_modules_section()}
  {_api_section()}
  {_run_section()}
  {_spec_table("Reliability & Safety (R)", reliability)}
  {_spec_table("Axis Extensions (E)", extensions)}
  {_spec_table("Foundations & Frontier (F)", foundations)}
  {_spec_table("Theme Tracks (T)", themes)}
  {_cert_table()}
</main>
<footer>Generated by docs/build_docs.py · Vigil GenAI Learning Project</footer>
</body>
</html>
"""
    (DOCS / "pages").mkdir(parents=True, exist_ok=True)
    out = DOCS / "pages" / "reference.html"
    out.write_text(page, encoding="utf-8")
    return out


if __name__ == "__main__":
    path = build()
    print(f"Wrote {path}")
