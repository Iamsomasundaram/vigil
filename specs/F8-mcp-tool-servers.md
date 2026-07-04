# F8 — Model Context Protocol (MCP) Tool Servers

- **Status:** Draft
- **Axis:** Foundations (GenAI literacy) — modern tool interoperability
- **New module:** `mcp/` (server) + client wiring in `levels/l4_tool_use.py`
- **Depends on:** L4 (function/tool calling)

---

## Problem / Motivation

L4 teaches tool use via hard-coded OpenAI function schemas. The industry is converging on
the **Model Context Protocol (MCP)** — a standard way for agents to _discover_ and call
tools exposed by external servers, decoupling tools from any one app. A learner who only
sees inline functions misses how real agent ecosystems plug tools together.

## Teaching Goal

**A learner exposes Vigil's NVD/EPSS tools as an MCP server, then has the agent discover
and call them over MCP instead of inline definitions.** They learn tool discovery,
capability negotiation, transport (stdio), and why MCP decouples tools from agents.

## Goals

- **MCP server** — `mcp/vigil_server.py` exposing `fetch_nvd_data` and `fetch_epss_score`
  as MCP tools (stdio transport).
- **MCP client path** — L4 can source its tool list from the MCP server (discovery) and
  route calls through it, behind a `--mcp` flag / env toggle.
- **Parity** — same analysis result whether tools are inline or via MCP.
- **Isolation** — MCP deps behind an extra; inline path stays the default.

## Non-Goals

- Remote/HTTP MCP transport, auth, or a public tool registry (future).
- Replacing inline tools as the default teaching path (MCP is additive).

## Design

```
inline (default):  agent ── TOOLS[] ──► execute_tool() ── httpx ─► NVD/EPSS
mcp (--mcp):       agent ── list_tools() ─► MCP client ─► stdio ─► vigil_server ─► NVD/EPSS
```

## Proposed Files

- **New** `mcp/__init__.py`, `mcp/vigil_server.py` — MCP server exposing the two tools.
- **Edit** `levels/l4_tool_use.py` — optional MCP-sourced tool discovery + dispatch.
- **Edit** `vigil/api.py` — `GET /l4/tools?source=mcp` to show discovered tools.
- **Edit** `pyproject.toml` — extra `mcp = ["mcp>=1.0"]`.
- **New** `tests/test_mcp.py` — server lists tools; client invokes one (in-process/stubbed).
- **Edit** `README.md` — how to run the MCP server.

## Data Models (`vigil/models.py`)

```python
class DiscoveredTool(_Base):
    name: str
    description: str
    input_schema: dict
    source: str   # "inline" | "mcp"
```

## API & CLI Surface

- CLI: `python mcp/vigil_server.py` (run server); `python levels/l4_tool_use.py CVE-... --mcp`.
- `GET /l4/tools?source=mcp` → `list[DiscoveredTool]`.
- Env: `VIGIL_TOOL_SOURCE=inline|mcp`.

## Tests (`tests/test_mcp.py`)

- Server advertises both tools with valid input schemas.
- Client discovers tools and invokes `fetch_epss_score` (external HTTP stubbed).
- L4 produces an equivalent verdict via MCP vs inline.
- Skips gracefully if `mcp` extra absent.

## Acceptance Criteria

- [ ] NVD/EPSS tools are reachable over MCP via discovery.
- [ ] L4 yields equivalent results inline vs MCP.
- [ ] MCP deps isolated; inline remains default; tests skip without extra.

## Open Questions

- stdio only for now (simplest), or also a local HTTP transport? Proposal: stdio first.
