# F21 — Fine-tuning, Adapters, and Build-vs-Tune Decisions

- **Status:** Done
- **Axis:** Foundations (GenAI literacy / frontier)
- **Target:** `levels/foundations/finetuning.py`
- **Depends on:** F6, F12, F14

---

## Problem / Motivation

Fine-tuning is often reached for prematurely. Engineers need a clear decision
model for when prompting, few-shot, RAG, or parameter-efficient fine-tuning
(LoRA) is the right adaptation strategy, plus the ability to validate a
fine-tuning dataset before spending on training.

## Teaching Goal

**A learner can choose an adaptation strategy from task characteristics and
validate a fine-tuning dataset for readiness — without running real training.**

## Goals

- Deterministic build-vs-tune advisor ranking prompt/few-shot/RAG/LoRA/full.
- Chat-style dataset validator: role checks, empty completions, duplicates,
  quality score, and readiness gate.
- API + UI so the decision and validation are runnable.
- Offline-only and fully deterministic for tests.

## Non-Goals

- Running actual fine-tuning or hosting adapters.
- Provider-specific training APIs.

## Proposed Files

- **New** `levels/foundations/finetuning.py`
- **Edit** `vigil/models.py` recommendation + dataset report models
- **Edit** `vigil/api.py` `/foundations/adaptation/recommend`, `/foundations/finetune/validate`
- **Edit** `ui/app.py` Fine-tune Advisor page
- **New** `tests/test_finetuning.py`

## API & CLI Surface

- `POST /foundations/adaptation/recommend`
- `POST /foundations/finetune/validate`
- CLI: `python -m levels.foundations.finetuning --data-volume 1500 --strict-format`

## Acceptance Criteria

- [x] Advisor recommends RAG for fresh-knowledge and LoRA for stable/strict/high-data.
- [x] Dataset validator flags duplicates, empty completions, and role errors.
- [x] API and UI expose both advisor and validator; tests are deterministic.
