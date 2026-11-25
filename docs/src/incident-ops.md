---
title: "Theme: Incident response"
summary: The same classify, route and plan pattern from the CVE levels, applied to a different job: handling a production incident.
section: Foundations
order: 12
---

# Theme: Incident response

**The question this page answers:** does what I learned on CVEs transfer to a different problem?

Vigil teaches its ideas on vulnerability management, but none of them are about CVEs. They are about a *shape*: take messy input, classify how serious it is, route it to the right response, and return a structured plan. Theme track T1 (`levels/themes/incident_ops.py`) proves that by applying the same shape to **production incidents**: an alert fires, and someone must decide how urgent it is and what to do first.

{{flow: Alert text + signals | Classify severity | Pick a track ~ containment, mitigation or monitor | Structured response plan}}

If that looks like [routing](l3.md) and the structured output from [Level 1](l1.md), it is. The domain changed; the architecture did not.

> **Note** Unlike the CVE levels, this module makes **no model calls**. It is a plain rule-based classifier that runs offline with no API key. That makes the routing logic easy to read and test. In a real system you could place a model where the rules are, but this module does not do that.

## The output: a typed plan

Just as L1 returns typed objects rather than text, the incident analysis returns a typed report:

{{include vigil/models.py#IncidentOpsReport}}

Notice the `Literal` types. The track can only be `containment`, `mitigation` or `monitor`, so the code that acts on a report never has to guess at a spelling.

## The rules

Severity comes from keyword lists. Two sets of terms mark an incident as critical or high:

{{include levels/themes/incident_ops.py#_CRITICAL_TERMS}}

{{include levels/themes/incident_ops.py#_HIGH_TERMS}}

A third table guesses which area of the system is involved, by looking for a word and naming the domain:

{{include levels/themes/incident_ops.py#_DOMAIN_RULES}}

## The decision

Here is the whole function:

{{include levels/themes/incident_ops.py#analyse_incident}}

Read it as a decision ladder:

| Condition | Severity | Track | Respond within |
| --- | --- | --- | --- |
| Customer impact **and** a critical term | Critical | containment | 15 minutes |
| A high term, **or** customer impact | High | mitigation | 60 minutes |
| Anything else | Medium | monitor | 240 minutes |

Each branch also fills in the immediate actions, who to escalate to, and a one-line reasoning that explains the choice. The reasoning field matters: a plan people are asked to trust should say why.

Running three cases offline gives results that match the table:

- `Payment API error rate surged and customer checkouts are failing`, with no customer-impact flag, gives **High**, the **mitigation** track and the **payments** domain. The words "error rate" are on the high list.
- `Possible data breach with exfiltration of customer records`, with customer impact set, gives **Critical**, **containment**, 15 minutes.
- `Minor config drift noticed` gives **Medium**, **monitor**, 240 minutes.

## What these rules get wrong

This is the most useful part of the page, because it shows why real systems need more than keyword rules. All of the following I confirmed by running the code offline.

- **Critical needs the customer-impact flag.** The alert `Payment outage, remote code execution suspected` with customer impact **false** comes out as **Medium**. A suspected remote code execution is rated lower than a routine slowdown, purely because a flag was not set.
- **Matching is whole-word, but still keyword-based.** Terms are matched as whole words, so the term `rce` no longer fires inside `resource`. `Disk resource usage slightly elevated` with customer impact set is **High**, sent to **mitigation** with 60 minutes. (An earlier version matched plain substrings and rated this alert Critical.) A real RCE described as "code execution" would still be missed, since only the listed phrases count.
- **Severity never goes below Medium.** The report type allows `Low`, but this code never produces it.
- **Keywords are not understanding.** A rare but serious problem described in different words will be missed.

Notice these are the same failure modes as in [Factuality](factuality.md) and the [moderation filter](responsible-ai.md): word lists are fast and transparent, but brittle. Fixing them means word-boundary matching, a model that reads the alert, and tests built from real incidents.

> **Warning** Do not use this classifier to run real incidents. It exists to teach the pattern. A human decides severity.

## How it relates to the rest of Vigil

| In the CVE levels | In incident response |
| --- | --- |
| Classify the CVE type (L3 routing) | Classify the incident severity |
| Choose a specialist track | Choose containment, mitigation or monitor |
| Structured remediation plan (L1) | Structured response plan with escalation targets |
| Human review for uncertain cases | The need for an incident commander |

The module is also exposed through the API as `POST /themes/incident/analyse`.

## Run it

```bash
python levels/themes/incident_ops.py "Payment API error rate surged and customer checkouts are failing" --service payments-api
python levels/themes/incident_ops.py "Possible data breach" --customer-impact --signal latency
```

You should see a table with the service, severity, track, urgency and likely domains, then the summary and numbered actions, followed by the full JSON report.

## Try it

> **Try it** 1) Run the same alert with and without `--customer-impact` and compare the severity. 2) Run `Disk resource usage slightly elevated` and confirm it is not Critical, then temporarily change `_contains_any` back to a plain `term in lowered` test and see the false alarm return. 3) Add a new domain rule, such as `kafka` mapping to `messaging`, and confirm the domain shows up.

## Common mistakes

- **Letting one flag decide everything.** A missing input silently lowers the severity.
- **Naive keyword matching.** Whole-word matching fixed the `rce` inside `resource` case, but a keyword list is still not understanding. Use a better classifier for real work.
- **No reasoning field.** People will not trust a verdict with no explanation.
- **Skipping tests with awkward inputs.** The `resource` false alarm appeared only when someone tried a word that contains a keyword, which is why there is now a test for it.
- **Believing the domain transfer is automatic.** The pattern transfers; the rules and the data do not.

## Check yourself

??? What stays the same between the CVE levels and this theme?
    The architecture: classify the input, route it to a track, and return a structured plan.

??? Why did an alert about "resource usage" used to be rated Critical, and why does it not now?
    Keywords were matched as substrings, and `rce` is a critical term that appears inside the word "resource". Matching is now whole-word, so it no longer fires.

??? Why does the report use `Literal` types for severity and track?
    So downstream code receives only a fixed set of exact values and can act on them safely.

You have reached the end of the Foundations pages. Next: the [learning path](learning-path.md) shows how everything fits together and what to try next.
