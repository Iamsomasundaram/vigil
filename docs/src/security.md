---
title: "API security defaults"
summary: How the API decides who may call it, what they may call, and how much, plus the two modes that keep local learning easy and production safe.
section: Reliability
order: 11
---

# API security defaults

**The question this page answers:** if I run Vigil anywhere other than my laptop, what stops a stranger from spending my LLM budget or switching off the monitor?

Most Vigil endpoints call a paid model. An open API is an open wallet. The hardening layer in `vigil/hardening.py` applies five rules to every request, in this order:

{{flow: Request size | API key | Scope | Rate limit | Concurrency cap | Your handler}}

## Two modes

| `VIGIL_ENV` | Keys set? | What happens |
| --- | --- | --- |
| `dev` (default) | no | API is open and a startup warning says so. Nothing to configure, so a first run just works. |
| `dev` | yes | Keys are enforced. |
| `prod` | no | **The app refuses to start.** It fails closed rather than run unauthenticated. |
| `prod` | yes | Keys are enforced, and the `/docs` pages need a key too. |

Never expose a `dev` instance on a network. The default exists for learning, not for hosting.

## Keys and scopes

Set `VIGIL_API_KEYS` to a comma-separated list. Each entry is `name:key:scope`:

```text
VIGIL_API_KEYS=reader:r-9f2c...:read,runner:u-41ab...:run,ops:a-77de...:admin
```

| Scope | Allows |
| --- | --- |
| `read` | GET routes: history, watchlist, reports. |
| `run` | Everything in `read`, plus any route that can call the model or change state. |
| `admin` | Everything in `run`, plus the monitor start/stop (kill switch), `/r5/budget` and `/admin/*`. |

Send the key in the `X-API-Key` header. A missing or wrong key returns `401`; a valid key without enough scope returns `403`. Only `/health` is always public. This is **deny by default**: a route you add later is protected without you remembering to list it.

A bare key with no name or scope (for example `VIGIL_API_KEYS=mykey`) still works and gets `admin` scope, which suits a single-person setup.

Keys are compared in constant time, and the rate limiter tracks the key's *name*, so the secret never appears in logs or in the `/admin/ratelimit` output. Wrong-key attempts are rate limited per IP address, so a key cannot be guessed by brute force.

> **Tip** Generate a key with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. The Streamlit UI sends the key in `VIGIL_UI_API_KEY`; give it a `run` key.

## Request limits

| Limit | Default | Setting | Result |
| --- | --- | --- | --- |
| Body size | 1,000,000 bytes | `VIGIL_MAX_BODY_BYTES` | `413` |
| Upload size (`/l4b/*`) | 15,000,000 bytes | `VIGIL_MAX_UPLOAD_BYTES` | `413` |
| Chunked body with no length | rejected | none | `411` |
| Calls per minute, per caller | 60 | `VIGIL_RATE_PER_MIN` | `429` |
| Simultaneous model-calling requests | 8 | `VIGIL_MAX_CONCURRENCY` | `503` with `Retry-After` |
| CVE identifiers | `CVE-YYYY-NNNN…` only | none | `422` |

The CVE check matters because the id flows into prompts, URLs and database queries. Validating the shape at the door means a malformed or hostile string never gets that far.

## CORS

CORS controls which *browser* origins may call the API. Set `VIGIL_CORS_ORIGINS` to a comma-separated list of exact origins. A wildcard (`*`) is refused at startup. In `dev` the default is the local Streamlit UI; in `prod` the default is none.

## What this does not do

- It is **API-key** security, suitable for service-to-service calls and small teams. It has no user accounts, expiry or revocation beyond editing the setting.
- For real users, put an identity provider (OAuth2 / OpenID Connect) at a gateway in front of Vigil and treat these keys as internal credentials.
- State is in memory in one process. Rate limits and the concurrency cap are per process, not shared across replicas.
- The concurrency slot is released when the response *starts*, so a long stream counts only briefly.
- Run it behind TLS. Keys sent over plain HTTP can be read on the network.

## Check yourself

??? Why does `prod` refuse to start without keys instead of just warning?
    A warning can be missed, and a missing setting is the most common way an API ends up open. Failing at startup turns a silent misconfiguration into an error someone must fix before anything is exposed.

??? A `run` key calls `POST /l6/monitor/stop`. What status comes back, and why that one?
    `403`. The key is valid, so it is not `401`, but the kill switch needs `admin` scope.

??? Why is CORS not a substitute for an API key?
    CORS is enforced by browsers only. A script or `curl` ignores it completely, so it cannot protect the API from non-browser callers.

Continue with the [Foundations](foundations.md) overview.
