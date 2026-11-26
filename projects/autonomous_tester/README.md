# Autonomous Tester (P1)

A small tester that does what a manual tester does: reads a plain-language test case, checks the
app, notices things the case never mentioned, and decides whether a failure is an app defect, a
bad test, bad data or a broken environment. It is measured against a demo shop with **known,
seeded bugs**, so you can say exactly what it found, missed or invented.

Plan and decisions: [`specs/P1-autonomous-tester.md`](../../specs/P1-autonomous-tester.md).

## Status

| Phase | What | State |
| --- | --- | --- |
| P1.1 | Demo shop, seeded bugs, answer key, scorer | **Done** (offline, no model, no browser) |
| P1.2 | Scope contract, heuristics, observation-only scan (adds Playwright) | Not started |
| P1.3 | Strategy, classifier with confidence, re-triage, review queue; first live evaluation | Not started |
| P1.4 | Codex integration, guard, agency modes, audit | Not started |
| P1.5 | Guide section, UI page, API route | Not started |

The agent itself is **live** when it arrives: real model calls, no mocked agent. Mocks are used
only in unit tests of our own code.

## Try the shop

With Docker Compose it is already running at http://localhost:8100 (profile `all_bugs`; change it with
`SHOP_PROFILE=clean docker compose up -d demo-shop`). Without Docker:

```bash
pip install -e ".[tester]"
python -m projects.autonomous_tester.demo_shop --profile all_bugs --port 8100
```

Open http://127.0.0.1:8100 and use it like a customer. The shop is deliberately broken under
`all_bugs`, so keep it on `127.0.0.1`. Profiles:

| Profile | What it is |
| --- | --- |
| `clean` | No seeded issues. The correct shop. |
| `all_bugs` | App defects, data issues and exploratory issues switched on |
| `env_down` | The cart returns 503 and product pages are slow |
| `v2_markup` | Same behaviour, renamed markup |

Try it as a tester first: read [`cases/cases.yaml`](cases/cases.yaml), run the cases by hand
against `all_bugs`, write down what you find, then compare with the answer key
(`evals/seeded_bugs.yaml`). The key is the answer sheet, so do the test first.

## Score a run

A tester run is a `RunResult` (see `evals/models.py`): one verdict per case or observation,
each with a category, a confidence and an evidence reference. Score it:

```bash
python -m projects.autonomous_tester.evals.scorer run_result.json
```

| Metric | Meaning |
| --- | --- |
| Defect recall | Seeded app defects found / seeded app defects |
| False-defect rate | Defects raised that the key does not support / defects raised |
| Classification accuracy | Case verdicts whose category matches the key |
| Silent false passes | Seeded defects whose covering case was passed (target 0) |
| Exploratory found / noise | Seeded exploratory issues observed / observations matching none |
| Review volume | Verdicts sent to a human |

Exploratory matching uses simple term matching, which is a deterministic baseline.

## Folders

| Folder | Contents |
| --- | --- |
| `demo_shop/` | The app under test: seed config, catalog generator, pages, routes |
| `cases/` | The plain-language test cases (YAML) and their loader |
| `evals/` | The answer key, run-result schema and scorer |
| `heuristics/`, `agent/`, `codex/` | Arrive in later phases |

Tests: `tests/projects/autonomous_tester/` (offline; skipped if the `tester` extra is missing).
