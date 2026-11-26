# P1 — Autonomous Tester (capstone project)

- **Status:** Proposed (concept, harness and default modes decided by the project owner; nothing built)
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
- Building our own agent loop. The Codex harness provides it.
- A generic harness-adapter layer. **Decided:** this project uses the Codex SDK only; it does
  not abstract over other harnesses (Claude Agent SDK, Copilot SDK, etc.). Where Codex has no
  native capability, we build our own orchestration around it (see below). No partner status
  or endorsement is implied.

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

**Rule:** use a native Codex capability when one exists; build our own orchestration layer
only for the right-hand column. Each right-hand row is checked against current Codex
documentation before it is built, because some may be partly covered (for example by Codex
hooks or configuration). The mapping from each row to a Codex feature is written in the guide
as it is verified; this table is the requirement.

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
    codex/                       our orchestration around the Codex SDK (Codex-specific, not a generic adapter)
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
| P1.4 | Codex integration: generate, run and repair scripts; guard; agency modes; audit | Codex SDK (live) |
| P1.5 | Guide section, UI page and API route, README links | No |

## Files (planned)

- **New** `specs/P1-autonomous-tester.md` (this file), index rows in `specs/README.md` and
  `specs/progress-board.md`.
- **New** everything under `projects/` and `tests/projects/` as above, delivered by phase.
- **Edit** `pyproject.toml` (include, extras), `README.md` (tree and "Which tracks"),
  `docs/` (Projects section), `vigil/routers/` and `ui/views/` only in P1.5.

## Credentials and the existing OpenAI key

Vigil's other learning topics already use one key, `OPENAI_API_KEY`, loaded from `.env` (see
`.env.example`). This project reuses it so learners configure one key, with these rules:

- The tester's own model calls (strategy, classification, re-triage) go through Vigil's
  existing OpenAI client and read `OPENAI_API_KEY`.
- Codex documents `CODEX_API_KEY` for non-interactive use and its TypeScript SDK. The Codex
  integration therefore **passes the key to the Codex process explicitly**, mapping
  `OPENAI_API_KEY` to `CODEX_API_KEY` in that child process's environment only. Never write
  the key to disk, a prompt, a log, a trace or generated code. To be verified on the
  installed Codex version before the first live run.
- Codex runs with its working directory set to the generated-test workspace, which never
  contains `.env` or any key file. This avoids the reported behaviour of picking up a project
  `.env` and billing an unintended account.
- Live runs and live evaluations are billed per token. Show an estimate before a live
  evaluation and enforce the R5 ceiling (labelled as an estimate, as everywhere else in Vigil).

---

## P1.1 detailed plan: demo shop, answer key, scorer

Everything in P1.1 runs offline with no model and no browser.

### The shop

A small FastAPI app using only the standard library for HTML (f-strings, no new template
dependency). In-memory cart keyed by a session cookie.

| Route | Purpose |
| --- | --- |
| `GET /` | Product list |
| `GET /product/{sku}` | Name, image, price, variant selector, quantity, add-to-cart |
| `POST /cart/add` | Add a SKU, variant and quantity |
| `GET /cart` | Lines, per-line price, subtotal |
| `POST /cart/remove` | Remove a line |
| `GET /health` | Liveness |

Stable `data-testid` attributes on every element a test needs. Products are **generated from
the seed config** (6 products: name, base price, variants with price deltas, stock, image or
none), so data and answer key cannot drift.

### Profiles (a run = one profile)

| Profile | Meaning |
| --- | --- |
| `clean` | No seeded bugs. Anything the tester reports as a defect here is a false defect. |
| `all_bugs` | Every seeded app defect, data issue and exploratory issue active. |
| `env_down` | The cart returns an injected `503`; product pages respond slowly. |
| `v2_markup` | No behaviour change; renamed and restructured markup (`SHOP_VERSION=2`). Tests written against v1 break for automation reasons only. |

### Seeded issues (answer key v1, not final until reviewed)

| ID | Kind | What is wrong | Expected verdict | Found by |
| --- | --- | --- | --- | --- |
| B01 | App defect | Cart shows the price 1 cent lower than the product page for one SKU | fail: app defect | formal case |
| B02 | App defect | Choosing a larger variant does not update the displayed price (the cart still charges it) | fail: app defect | formal case |
| B03 | App defect | Adding quantity 3 adds 2 | fail: app defect | formal case |
| B04 | App defect | Removing a line leaves the subtotal stale until reload | fail: app defect | formal case |
| B05 | App defect, silent-pass trap | The header badge count rises but no line appears in the cart for one SKU. A weakly written case that checks only the badge passes wrongly | fail: app defect (a pass here is a silent false pass) | formal case plus tester judgment |
| D01 | Test data | One product is out of stock and correctly cannot be added; a case that adds it fails for data reasons | fail: test data issue | formal case |
| D02 | Test data | One product has no image | fail: test data issue | formal case |
| E01 | Environment | Cart returns an injected `503` | blocked: environment | formal case |
| E02 | Environment | Product page responds after a long delay | blocked: environment | formal case |
| A01 | Automation | `v2_markup` renames the add-to-cart test id and moves the price element | fail: automation issue | formal case |
| X01 | Exploratory | A console error on product page load | exploratory observation | no formal case |
| X02 | Exploratory | A banner covers the add-to-cart button on a narrow mobile width | exploratory observation | no formal case |
| X03 | Exploratory | Product images have no alt text | exploratory observation | no formal case |

### Formal cases (plain language, `cases/*.yaml`)

About 8 cases with an id, title, plain-language steps, expected result, priority and the area
they cover. One of them (the cart-count case) is **deliberately weakly written** to bait B05.
Cases never name the seeded bugs.

### Answer key (`evals/seeded_bugs.yaml`)

Per issue: `id`, `kind`, `title`, `active_in` (profiles), `covered_by` (case ids or none),
`expected_verdict`, `detectable_by` (`formal` or `exploratory`), and how it can be observed
(route or element). The key is data, loaded and validated by code.

### Scorer (`evals/scorer.py`)

Input: a run result (list of verdicts: case or observation id, category, confidence, evidence
reference) and the profile used. Output: the metrics table from the Scoring section, plus a
per-issue found, missed or invented list. A pydantic model defines the run-result schema so
P1.3 and P1.4 produce exactly what the scorer reads.

### Offline tests (`tests/projects/autonomous_tester/`)

- Each seeded issue is **really present** when its profile is active and **absent** under
  `clean` (checked over HTTP). This keeps the answer key honest.
- Every answer-key id exists in the shop code and every seeded bug has a key entry.
- Generated data is deterministic for a given seed config.
- Scorer: a perfect run scores full recall and zero false defects; a run that passes B05
  counts one silent false pass; a defect raised under `clean` counts as a false defect; a
  wrong category lowers classification accuracy.
- Cases load and validate; none mention a seeded bug id.

### Files (P1.1)

- **New** `projects/README.md`, `projects/__init__.py`, `projects/autonomous_tester/README.md`.
- **New** `projects/autonomous_tester/demo_shop/` (app, catalog generator, seed config,
  profiles), `cases/`, `evals/` (answer key, scorer, run-result schema).
- **New** `tests/projects/autonomous_tester/` (with `__init__.py`).
- **Edit** `pyproject.toml`: include `projects*`; new optional extra `tester` (FastAPI, YAML
  parsing; Playwright is added in P1.2).
- **Edit** `README.md`: tree entry and a short "Projects" pointer.

### Acceptance criteria (P1.1)

- [ ] Shop runs locally under each of the four profiles; `clean` behaves correctly end to end.
- [ ] All 13 seeded issues are observable over HTTP under their profiles and absent under `clean`.
- [ ] Answer key validates and matches the shop code in both directions.
- [ ] Scorer reports every metric and per-issue found, missed or invented.
- [ ] Offline tests above pass; whole suite and ruff stay green; no model or browser needed.
- [ ] No client names, systems or counts anywhere in the files.
- [ ] `projects/README.md` explains how `projects/` differs from `levels/`, `architectures/`
      and `reliability/`.

---

## Open questions

1. ~~Harness choice.~~ **Decided:** Codex SDK, no generic adapter. Still to verify from the
   official docs before P1.4 (checked 2026-11-26 against OpenAI's authentication and
   non-interactive pages):
   - Auth: Codex supports sign-in with ChatGPT or with an API key. API-key use is billed
     through the OpenAI Platform at standard API rates. The documented variable for
     non-interactive use and the TypeScript SDK is `CODEX_API_KEY`, not `OPENAI_API_KEY`.
     A key is loaded with `codex login --with-api-key`.
   - **Billing risk:** community reports say some versions silently used an `OPENAI_API_KEY`
     found in the environment or a project `.env`. Set the auth method explicitly, keep the
     key out of the repo, and check the installed version's behaviour before the first live run.
   - There is also a Python SDK in the Codex repo (`sdk/python`). Since Vigil is Python, decide
     between it and the TypeScript SDK after checking maturity and feature parity.
   - Known open report: overlapping runs on one new TypeScript thread can split into separate
     conversations. Design for one turn at a time per thread.
   - Capabilities still to confirm: hooks, subagents, MCP, `codex exec` output format, usage
     events and any built-in spend limit.
2. ~~Browser extra.~~ **Decided:** Playwright is the only browser dependency, and CI can
   install it.
3. ~~Demo shop data.~~ **Decided:** generated from the seed config, so the answer key and the
   data cannot drift.
4. ~~Default agency mode.~~ **Decided:** `observe` looks and reports without changing any
   state; `execute` runs the tests. The bundled demo shop defaults to `execute` (harmless).
   Any other URL defaults to `observe`, and `execute` there needs an explicit flag.
5. **Cost of live evaluation.** Set a per-run and per-evaluation ceiling before the first
   live run; record cost and variance in the report.

## Acceptance Criteria (for this planning spec)

- [x] Concept, scope, target, placement and confidentiality rule agreed with the owner.
- [ ] Phase list and folder structure approved.
- [x] Harness choice made: Codex SDK only; own orchestration where Codex has no native capability.
- [ ] Codex auth, cost and capability checks verified against the installed version (before P1.4).
- [ ] Each phase gets its own acceptance checklist before code is written.
