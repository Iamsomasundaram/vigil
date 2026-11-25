---
title: Architectures overview
summary: Four named ways to design an agent, compared on one job, plus the LangGraph bridge.
section: Architectures
order: 1
---

# Architectures: four ways to build the same agent

**The question this track answers:** once a model can call tools, how should you *organise* it?

The [levels](l0.md) teach capabilities in order: one call, a chain, parallel agents, routing, tools, memory, autonomy. The **architectures** are different. Each one is a named **design pattern**, and Vigil gives all four the **same job** so you can compare them fairly:

> Investigate a CVE using live data from NVD, EPSS and the CISA Known Exploited Vulnerabilities (KEV) catalog, then produce a structured risk report.

Same tools, same kind of report, four different designs. The differences you see are the differences in the pattern, not in the task.

{{flow: A1 ReAct ~ think, act, observe, repeat | A2 Plan-and-Execute ~ plan first, then run | A3 Reflection ~ draft, critique, revise | A4 Multi-agent ~ specialists plus orchestrator}}

## The three tools they share

| Tool | Source | What it tells you |
| --- | --- | --- |
| `fetch_nvd_data` | NVD | Description, CVSS score, severity |
| `fetch_epss_score` | EPSS | Probability the CVE is exploited soon (0 to 1) |
| `check_cisa_kev` | CISA KEV | Whether the CVE is confirmed as actively exploited |

KEV is the new one compared with [L4](l4.md). A CVE in the KEV catalog is being exploited in the wild, which is the strongest urgency signal the project uses.

## Which one should I use?

This comparison comes from reading how each file is built. It is qualitative on purpose: real cost and speed depend on the model, the CVE and your network, and Vigil does not measure them here.

| | A1 ReAct | A2 Plan-and-Execute | A3 Reflection | A4 Multi-agent |
| --- | --- | --- | --- | --- |
| **Who decides the next step** | The model, after seeing each result | The model, once, up front | Fixed code (research, critique, revise) | Fixed code dispatches; each specialist chooses its own tool calls |
| **Model calls** | As many as the loop needs, plus one to structure the report | Two: one plan, one synthesis. Tool steps call your code directly | Three, always | Several per specialist, three specialists, plus one orchestrator call |
| **Parallelism** | Tool calls within one model turn run together | Steps run one by one | The three data fetches run together; the three model calls are sequential | The three specialists run together |
| **Main strength** | Adapts to what it finds; shows its reasoning | Predictable; you can review or edit the plan before anything runs | Improves report quality by checking it | Focused roles; independent work finishes sooner |
| **Main weakness** | Less predictable; can wander | Cannot change course after the plan is made | Does not gather more data; only rewrites | Most moving parts; specialists cannot see each other |
| **Reach for it when** | The path depends on what you discover, or you need an audit trail of reasoning | You need approval before acting, or want a fixed, inspectable procedure | The wording and calibration of the answer matters | The work splits into independent, specialised jobs |

> **Tip** They combine. The Reflection file says so itself: gather data with ReAct, then critique the resulting report. Real systems often layer two patterns.

## Pages in this track

- [A1: ReAct](a1.md) writes down a *Thought* before every action.
- [A2: Plan-and-Execute](a2.md) separates planning from doing, and adds human approval gates.
- [A3: Reflection](a3.md) has the model critique its own draft.
- [A4: Multi-agent](a4.md) uses specialist agents and an orchestrator.

## Running them

Each file is a script. They call the OpenAI API and the three live public data sources, so you need a key in `.env` and an internet connection.

```bash
python architectures/a1_react.py CVE-2021-44228
python architectures/a2_plan_execute.py CVE-2021-44228
python architectures/a3_reflection.py CVE-2021-44228
python architectures/a4_multi_agent.py CVE-2021-44228
```

> **Note** The tests in `tests/test_architectures.py` replace the model and the data fetchers with stand-ins, so they run offline and cost nothing. They check the control flow: the order of calls, the safety limits, and how errors are handled. They do not check how good a real model's answers are.

## The LangGraph bridge

Frameworks such as LangGraph give you ready-made building blocks for this kind of orchestration. Vigil writes its patterns by hand so you can see how they work, then shows how they map onto a framework in `architectures/frameworks/`.

[`MAPPING.md`](repo:architectures/frameworks/MAPPING.md) lists the correspondence:

| Vigil concept | LangGraph concept |
| --- | --- |
| A Python function that updates state | A graph **node** |
| `if`/`else` routing inside the loop | A **conditional edge** |
| The `messages` list | A field in the graph **state** |
| The `max_iterations` guard | `recursion_limit` |
| The tool dispatch function | A tool node or callable |

The same file notes that CrewAI maps to A4, LlamaIndex to the L5 memory work, and the OpenAI Agents SDK to the L4 tool loop.

The code is a deliberately small port, `a1_react_langgraph.py`:

{{include architectures/frameworks/a1_react_langgraph.py#build_graph}}

Read it honestly: it builds a graph with **one node** (`reason`) that makes a single model call and returns a one-line verdict. It does **not** reproduce A1's tool loop. It exists to show the vocabulary of nodes, edges and state, not to be a full port.

If LangGraph is not installed, `analyse_cve` catches the `ImportError` and returns a canned fallback sentence with `"framework": "fallback"`, so nothing crashes. That fallback does not call a model. Install the real thing with `pip install -e ".[frameworks]"`. The API exposes the port at `/frameworks/a1`.

## Try it

> **Try it** Run all four on the same CVE and compare, in a notebook or a text file: how many tool calls each made, how long each took (each script prints it), and how the final risk verdicts differ in wording and caution. Then run a CVE that is *not* in the KEV catalog and see which pattern copes best with the "not found" answer.

## Common mistakes

- **Treating the patterns as rivals.** They solve different problems. Pick by what you need, not by which sounds most advanced.
- **Reaching for multi-agent first.** More agents means more calls, more cost and more places to fail. Use one only when the job really splits.
- **Assuming reasoning text is the real reason.** In ReAct the written *Thought* is useful evidence, but it is text the model produced, not a guaranteed view into its process.
- **Skipping limits.** Every loop here has a cap. Keep that habit in your own agents.

## Check yourself

??? What is held constant across A1 to A4, and why?
    The job and the tools (NVD, EPSS, CISA KEV) and the shape of the report. Holding them constant means any difference in behaviour comes from the pattern.

??? Which pattern lets a human approve a step before anything runs, and why?
    Plan-and-Execute (A2). Because the plan exists as data before execution starts, a person can review, edit or reject it.

??? Why is the LangGraph port in Vigil only one node?
    It is a minimal illustration of the framework's vocabulary. It makes one model call and returns a verdict, and it does not include A1's tool loop.

Start with [A1: ReAct](a1.md).
