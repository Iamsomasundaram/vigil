# T1 — Incident Response Ops Theme

- **Status:** Done
- **Axis:** Theme portability (cross-domain learning)
- **Module:** `levels/themes/incident_ops.py`
- **Depends on:** L1-L3 mental model, R1-R4 reliability patterns

---

## Problem / Motivation

Vigil teaches CVE intelligence deeply, but learners also need to see whether the
same agentic patterns transfer to a different operational domain.

## Teaching Goal

**A learner can classify a production incident from alert text and produce a
first-hour response plan with explicit urgency and escalation targets.**

## Goals

- Provide one concrete non-CVE theme using the same thinking patterns.
- Keep response structured and auditable.
- Make it accessible via API and UI with clear interpretation hints.

## Non-Goals

- Full SIEM integration.
- Auto-remediation execution.

## Design

```
alert text + context -> severity/track classifier -> structured response plan
```

## Files Delivered

- **New** `levels/themes/incident_ops.py`.
- **New** `levels/themes/__init__.py`.
- **Edit** `vigil/models.py` (`IncidentOpsReport`).
- **Edit** `vigil/api.py` (`POST /themes/incident/analyse`).
- **Edit** `ui/app.py` (new page `T1 — Incident Response Ops`).
- **New** `tests/test_theme_incident_ops.py`.
- **Edit** `tests/test_foundations_api.py` (theme endpoint test).

## API & CLI Surface

- `POST /themes/incident/analyse` with incident text/context.
- CLI: `python -m levels.themes.incident_ops "payment failures in prod" --service payments-api --customer-impact`.

## Acceptance Criteria

- [x] Structured severity/track/urgency output is returned.
- [x] Theme is reachable from UI and API.
- [x] Automated tests cover classifier behavior and endpoint shape.



