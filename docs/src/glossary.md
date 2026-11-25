---
title: Glossary
summary: Plain-English definitions of the words used in this project.
section: Reference
order: 1
---

# Glossary

Short definitions, in alphabetical order. Where a word is used in the code, the level that introduces it is shown in brackets.

| Term | Meaning |
| --- | --- |
| **Agent** | A system where the model chooses what to do next, often using tools, until a goal is met. At L2 an "agent" is only a prompt plus a schema; real autonomy arrives in L4 to L6. |
| **API** | The way your code talks to a service. Here, mainly the model provider's API, and also the FastAPI service Vigil exposes. |
| **API key** | A secret string that identifies and bills your account. Keep it in `.env`, never in code. |
| **async / await** | Python syntax that lets a program wait on slow work, such as a network call, without freezing. Used from L2. |
| **Chain** | Several model calls in sequence where each feeds the next (L1). |
| **Context window** | The maximum number of tokens a model can handle in one call, counting your input and its reply. |
| **Context accumulation** | Passing earlier results into later steps so they build on what is known (L1). |
| **CVE** | Common Vulnerabilities and Exposures: a public identifier for a security flaw, such as CVE-2021-44228. |
| **CVSS** | A 0 to 10 severity score for a vulnerability. |
| **EPSS** | A score estimating how likely a vulnerability is to be exploited soon (used at L4). |
| **Embedding** | A list of numbers that represents the meaning of a text, so similar texts are close together. Used for memory and retrieval. |
| **Evaluation** | Measuring how good an AI system's answers are against a known set of examples. |
| **Fan-out / fan-in** | Sending one input to many workers at once, then combining their outputs (L2). |
| **Guardrail** | A check that blocks or fixes unsafe or invalid input and output (R1). |
| **Hallucination** | A fluent answer that is not true. A model can invent details. |
| **LLM** | Large language model: a model trained on lots of text to predict the next token. |
| **MCP** | Model Context Protocol: a standard way for a model to discover and use outside tools. |
| **Memory** | Information kept between runs so the system can recall earlier work (L5). A model itself has none. |
| **Moderator** | An extra step that reads other agents' outputs and produces one verdict (L2). |
| **NVD** | The US National Vulnerability Database, a public source of CVE data (used at L4). |
| **Orchestration** | The code that decides which calls happen, in what order. |
| **Prompt** | The text and messages you send to the model. |
| **Pydantic** | A Python library for describing and validating data shapes. Used for structured output. |
| **RAG** | Retrieval-augmented generation: look up relevant documents first, then give them to the model so it answers from real sources. |
| **Routing** | Choosing which path or specialist handles an input (L3). |
| **Schema** | A description of the exact fields and types you expect back. |
| **Structured output** | Making the model return data that matches a schema instead of free text (L1). |
| **System prompt** | The instruction that sets the model's role and rules (L0). |
| **Temperature** | A setting for how varied the model's wording is. Low is steady, high is varied (L0). |
| **Token** | A chunk of text, roughly three quarters of an English word. Billing and limits are counted in tokens. |
| **Tool use** | Letting the model ask your code to run a function, such as looking up a CVE, and then using the result (L4). |
| **User prompt** | The message carrying the actual task (L0). |
| **Vector** | See embedding. |
