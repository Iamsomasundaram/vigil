# F19 — AI Supply Chain and Dependency Security

- **Status:** Done
- **Axis:** Production hardening and governance
- **Target:** model/tool/prompt/dependency integrity controls
- **Depends on:** F10, R1

---

## Problem / Motivation

Industry teams increasingly treat prompts, model configs, tool schemas, and
embedding pipelines as supply-chain assets. Tampering and accidental drift in
these artifacts can introduce silent risk.

## Teaching Goal

**A learner can track and verify critical AI artifacts with provenance metadata,
integrity checks, and controlled promotion workflows.**

## Goals

- Track artifact manifest: prompts, model policies, tool schemas, retriever configs.
- Add checksum/signature validation and drift detection.
- Add environment promotion gates and provenance logging.
- Integrate with eval gates before promotion.

## Non-Goals

- Enterprise PKI rollout.

## Proposed Files

- **New** `reliability/r8_supply_chain.py`
- **New** `data/manifests/ai_artifacts.json`
- **Edit** `vigil/api.py` artifact integrity endpoints
- **Edit** `ui/app.py` supply-chain status page
- **New** `tests/test_supply_chain.py`

## Acceptance Criteria

- [x] Integrity violations are detected and surfaced clearly.
- [x] Promotion requires passing integrity and eval checks.
- [x] Provenance logs are queryable and test-covered.

