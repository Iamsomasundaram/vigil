# F22 — Claude Model Selection & Context Engineering

- **Status:** Done
- **Axis:** Foundations (Claude-architect alignment)
- **Target:** `levels/foundations/model_selection.py`, `vigil/claude_provider.py`, `vigil_mcp/vigil_client.py`
- **Depends on:** F3, F8, F21

---

## Problem / Motivation

The Claude Architect certifications test model selection (Haiku/Sonnet/Opus), the
Claude Messages API shape, and MCP integration. This spec adds that Claude-specific
alignment **without changing** the existing OpenAI-based inference seam.

## Teaching Goal

**A learner can pick a Claude tier from constraints, see how OpenAI-style messages
map to the Claude Messages API, and run an MCP client tool loop.**

## Goals

- Deterministic Claude tier advisor (complexity/latency/cost/volume/stakes).
- Additive Claude Messages API bridge (system param + content blocks), offline-testable mapping.
- Additive MCP client path with an injectable, offline tool loop.
- API + UI + tests, all additive.

## Non-Goals

- Replacing or modifying `vigil/inference.py` behavior.
- Requiring the `anthropic` package for existing functionality.

## Files Delivered

- **New** `levels/foundations/model_selection.py`
- **New** `vigil/claude_provider.py` (lazy `anthropic` import, clean error if absent)
- **New** `vigil_mcp/vigil_client.py`
- **Edit** `vigil/models.py` (additive models)
- **Edit** `vigil/api.py` (additive endpoints)
- **Edit** `ui/app.py` (new F22 page)
- **Edit** `pyproject.toml` (new optional `claude` extra)
- **New** `tests/test_model_selection.py`, `tests/test_claude_bridge.py`

## API & CLI Surface

- `POST /foundations/model-select`
- `POST /claude/map-messages`
- `POST /mcp/tool-loop`
- CLI: `python -m levels.foundations.model_selection --complexity high --high-stakes`

## Acceptance Criteria

- [x] Advisor recommends Haiku/Sonnet/Opus correctly by constraints.
- [x] Message mapping puts system prompt in the Claude `system` param.
- [x] MCP client loop runs offline via injectable invoker.
- [x] All additions are optional and do not change existing behavior.
