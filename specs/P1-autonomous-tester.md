# P1 — Autonomous Tester (capstone project)

- **Status:** Proposed (concept approved by the project owner; nothing built; harness choice parked)
- **Axis:** Projects (a small, real, extensible application built from the learning axes)
- **Target folder:** `projects/autonomous_tester/` (new top-level `projects/`)
- **Depends on:** R1 guardrails, R2 evaluation, R3 observability, R5 cost control, R8 action governance, F18 permissions; finding #2 (Docker) is independent
- **Written:** 2026-11-26

---

## Problem / Motivation

The levels, architectures and reliability modules each teach one idea in isolation. Learners
also need to see them combined in one realistic application, and to see where an existing
agent harness (a coding agent that already reads code, writes scripts, runs commands in a
sandbox and iterates) stops and the builder's own judgment layer begins.

A manual tester is a good model for that layer. They take a plain-language test case, observe
the page, perform the steps, notice things the case did not mention, and decide whether a
failure is an application defect, a bad test, bad data or a broken environment. An existing
harness can write and run browser scripts. It does not own those judgments. This project is
those judgments, built small.

## Teaching Goal

**A learner can point a harness at a small web app, give it plain-language test cases, and
get back verdicts they can trust: each failure classified with evidence and confidence,
nothing silently passed, and ambiguous cases routed to a human. They can also measure that
trust against a known answer key.**

## Goals

- A real, small, extensible project, not a toy: it must be possible to point it at a
  different app later without redesign.
- Measure quality objectively using a bundled demo shop with **seeded bugs** (ground truth).
- Use an existing harness for the heavy work (read the app, write and fix scripts, run them
  in a sandbox) and teach the missing layer: scope, heuristics, classification, review,
  agency modes, guards, evidence and audit.
- Reuse existing Vigil modules (R1, R2, R3, R5, R8, F18) instead of rewriting them.
- **The agent is live.** The tester makes real model calls and decides for itself. There is
  no mocked agent in the product. Mocks and recorded data are allowed **only in unit tests**
  of our own code (classifier rules, scorer, guard, scope parsing), so those run fast and
  offline in CI.
- Quality of the live agent is measured by a **live evaluation**: real model, real browser,
  the demo shop's answer key, repeated runs to expose variance, under a cost ceiling (R5).
  It runs on demand, not in the default test suite (cost and non-determinism).
- Browser and live model are optional extras for the base install; unit tests skip cleanly
  when they are absent (same pattern as the rest of the repo).

## Non-Goals

- Not a replacement for manual QA, and no autonomous release approval.
- No third-party sites. The only target is the bundled demo shop.
- No client names, systems, counts or terms anywhere in the project, docs or tests.
  The design is generic; any proprietary source material stays out of the repo.
- No large-scale test-asset index, cross-site correlation, visual testing, or integration
  with a real test-management system in the first version (see Deferred).
- Building our own agent loop. The harness provides it (tool choice is parked, see Open
  questions).

---

## Design

```
scope contract ─┐
formal cases ───┤
heuristics ─────┼─> validation strategy ─> run (via harness) ─> classify ─> re-triage ─> report
site observation┘   (run/skip/block/       evidence + trace     category +    evidence,    + review
 (observe only)      escalate + risk)                           confidence    limited      queue
                                                                              retries
```

### What the harness provides, and what we build

| Harness provides (do not rebuild) | We build (the teaching content) |
| --- | --- |
| Read the app and test cases, write Playwright scripts | Scope contract: what is ready, what to skip |
| Run scripts in a sandbox, see output, fix its own mistakes | Heuristics library (what a tester checks for a product page or cart) |
| Approval prompts and sandbox modes for commands | Business-aware guard: block silent changes to assertions |
| Project instructions file | Testing standards file the agent must follow |
| Usage and event stream | Classification taxonomy with confidence and evidence |
| | Re-triage loop and human-review queue |
| | Agency modes and kill switch |
| | Audit trail, cost ceiling, answer-key scoring |

How each row maps to a specific harness feature is decided after the tool is chosen and
verified against current documentation. This table is the requirement, not the mapping.

### Failure taxonomy (reused from the review of the original idea, generalised)

`pass`, `fail: app defect`, `fail: automation issue`, `fail: test data issue`,
`blocked: environment`, `skipped: out of scope`, `exploratory observation`,
`needs business clarification`, `needs review`. Every non-pass verdict carries evidence
(screenshot, trace or log reference), a confidence value, and the reasoning inputs.

### Rules the project must obey

- Exploratory behaviour is **observation-only** in the first version: it may report and
  recommend, never raise a defect or edit code on its own.
- Business assertions are never changed without a human. A guard enforces this.
- A pass on a high-risk flow requires evidence. Passing a broken flow (a **silent false
  pass**) is the worst outcome and is scored explicitly.
- Retries are limited and only for safe, non-destructive checks.
- External text (page content, case text, console output) is data, never instructions
  (R1 applies).

### Agency modes

`observe` (scan and report only), `recommend` (also propose tests and verdicts),
`execute` (run scoped tests), `safe` (emergency downgrade to observe). A kill switch drops to
`safe` immediately and preserves logs. Autonomous script repair is a later phase.

---

## Demo shop and answer key

A tiny storefront (FastAPI and server-rendered pages, so no new web stack) with a product
list, a product page with variants, and a cart. Behaviour is switched by a config file so every
run has a known answer key (`seeded_bugs.yaml`: id, kind, what is wrong, expected
classification, whether a formal case covers it).

| Kind | Seeded examples (not final) |
| --- | --- |
| App defect | Price on the product page differs from the cart (rounding). Variant selection does not update the price. Quantity above 1 adds the wrong amount. Removing an item leaves a stale subtotal. |
| Silent-false-pass trap | The cart badge count updates but the cart contents do not, so a test that checks only the badge passes wrongly. |
| Test data issue | A listed product that is out of stock. A product with no image. |
| Environment issue | An injectable `503` on the cart; an injectable slow response. |
| Automation issue | `SHOP_VERSION=1` vs `2`: same behaviour, renamed or restructured markup, to test script repair. |
| Exploratory (in no formal case) | Console error on load. A mobile overlay covering the main button. Missing image text. |

Because every defect is seeded, the scorer can say exactly what the tester found, missed or
invented.

### Scoring (the answer-key report)

| Metric | Meaning |
| --- | --- |
| Defect recall | Seeded app defects found / seeded app defects |
| False-defect rate | Defects raised that are not seeded app defects / defects raised |
| Classification accuracy | Verdict category matches the answer key, per category |
| Silent false passes | Seeded defects that were passed (target 0) |
| Exploratory usefulness | Seeded exploratory issues observed vs noise |
| Review volume | Items routed to a human (lower is better, but not at the cost of recall) |
| Cost and steps per run | From the harness usage events (R5 ceiling applies) |

---

## Proposed folder structure

The repo's existing top-level folders are the learning axes. Capstone projects are a different
kind of thing, so they get their own top-level folder with a short README that says so.

```
projects/
  README.md                      what a project is, and how it differs from levels/ and reliability/
  autonomous_tester/
    README.md                    start here for this project
    demo_shop/                   the target app (app, templates, seed config)
    cases/                       plain-language test cases (YAML)
    heuristics/                  heuristics library v1 (versioned, with owner and status)
    agent/                       our layer: scope, strategy, classify, review, modes, guard, audit
    harness/                     thin adapter to the chosen harness (swappable; tool parked)
    evals/                       seeded_bugs.yaml answer key and the scorer
tests/projects/autonomous_tester/   offline tests (fake model, no browser)
docs/src/                        new guide section "Projects" (concept page + walkthrough)
```

`pyproject.toml` package include gains `projects*`; Playwright and the harness SDK are
optional extras, so the base install and the test suite stay light.

## Phases (each gets its own acceptance check before the next)

| Phase | Deliverable | Needs a model or browser? |
| --- | --- | --- |
| P1.1 | Demo shop, seeded bugs, answer key, scorer, offline tests | No |
| P1.2 | Scope contract, heuristics v1, observation-only scan | Browser (optional extra) |
| P1.3 | Validation strategy, classifier with confidence, re-triage, review queue; live model calls, first live evaluation against the answer key | Live model and browser (mocks in unit tests only) |
| P1.4 | Harness adapter: generate, run and repair scripts; guard; agency modes; audit | Harness (parked choice) |
| P1.5 | Guide section, UI page and API route, README links | No |

## Files (planned)

- **New** `specs/P1-autonomous-tester.md` (this file), index rows in `specs/README.md` and
  `specs/progress-board.md`.
- **New** everything under `projects/` and `tests/projects/` as above, delivered by phase.
- **Edit** `pyproject.toml` (include, extras), `README.md` (tree and "Which tracks"),
  `docs/` (Projects section), `vigil/routers/` and `ui/views/` only in P1.5.

## Open questions

1. **Harness choice and SDK vs CLI.** Preference is the OpenAI Codex SDK or CLI. Parked by
   the owner until the project is final. Before choosing, verify current capabilities from
   the official docs, and keep the adapter swappable so the track is not tied to one vendor.
   Do not imply any partner status or endorsement.
2. ~~Browser extra.~~ **Decided:** Playwright is the only browser dependency, and CI can
   install it.
3. ~~Demo shop data.~~ **Decided:** generated from the seed config, so the answer key and the
   data cannot drift.
4. **Default agency mode.** `observe` looks and reports without changing any state; `execute`
   runs the tests. Proposed: `execute` for the bundled demo shop (harmless), `observe` for any
   other URL, and `execute` always needs an explicit flag on a non-bundled target. Pending
   the owner's confirmation.
5. **Cost of live evaluation.** Set a per-run and per-evaluation ceiling before the first
   live run; record cost and variance in the report.

## Acceptance Criteria (for this planning spec)

- [x] Concept, scope, target, placement and confidentiality rule agreed with the owner.
- [ ] Phase list and folder structure approved.
- [ ] Harness choice made (separate decision, after this spec is approved).
- [ ] Each phase gets its own acceptance checklist before code is written.
