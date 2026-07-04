# Vigil Progress Board

Last updated: 2026-07-04

## Done

- F1 — Real Embeddings & Vector RAG
- F2 — Multimodal Inputs
- F3 — Multi-Provider & Local Models
- F5 — Context-Window Management
- F9 — Learning Scaffolding

## Pending Approved Ideas

These are the remaining approved/spec'd ideas that are not yet implemented.

| Priority | Spec | Target                               | Concept                                                    | Status |
| -------- | ---- | ------------------------------------ | ---------------------------------------------------------- | ------ |
| 6        | F4   | `levels/foundations/tokenization.py` | Tokenization & context economics (`tiktoken`)              | Draft  |
| 7        | F6   | `levels/foundations/prompting.py`    | Prompt engineering patterns: zero/few-shot, CoT, templates | Draft  |
| 8        | F7   | `architectures/frameworks/`          | Framework bridge: LangGraph / CrewAI / LlamaIndex          | Draft  |
| 9        | F8   | `mcp/vigil_server.py`                | Model Context Protocol (MCP) tool servers                  | Draft  |
| 10       | F10  | `vigil/api.py`, R2/R5                | Auth, rate limiting, caching, faithfulness eval            | Draft  |

## Recommended Next Pick-Up

1. **F4** — tokenization is the cleanest remaining foundation and unlocks better context/cost intuition.
2. **F6** — prompt engineering techniques build directly on token budgeting.
3. **F7** — framework bridge after the prompting/token basics are in place.
4. **F8** — MCP works best once tool/server patterns are already familiar.
5. **F10** — production hardening is broadest, so keep it last.

## Notes

- The repository-wide priority path for foundations is complete through F9.
- `specs/README.md` is the canonical index; this board is the quick pick-up view.
- Revisit the spec statuses before implementation, because some specs may move from Draft to Approved independently of coding work.
