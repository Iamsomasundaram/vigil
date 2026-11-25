---
title: Welcome
summary: What Vigil is, who this guide is for, and how to use it.
section: Start here
order: 1
---

# Learn GenAI by building a security agent

Vigil is a small, real project that grows from **one call to a language model** into an **autonomous agent** that watches for security vulnerabilities (CVEs), decides which ones matter, and follows up on them.

You do not need to know any AI to start. You do need to be comfortable reading basic Python.

> **Note** The guide covers all seven levels, the four agent architectures, the reliability modules (R1 to R9) and the foundations track. Pages describe what the code does and call out where it is simplified or where its comments disagree with it.

## The idea in one picture

Every level adds exactly one new idea on top of the one before it.

{{flow: L0 ~ one call | L1 ~ a chain | L2 ~ parallel agents | L3 ~ routing | L4 ~ tools | L5 ~ memory | L6 ~ autonomy}}

By the end you will have seen, in running code, how an AI *system* turns into an AI *agent*.

## Why a security problem?

Organisations face thousands of new CVEs a year and cannot fix them all. The useful question is not "what is this CVE?" but "does it matter to *us*, and what do we do first?". That question needs facts, judgement, tools and follow-up, which is exactly what makes it a good way to learn agents.

## How to use this guide

1. Read [Getting started](getting-started.md) and get the code running (15 minutes, no API key needed for the first part).
2. Read [How LLMs work](concepts.md). It covers just enough theory to follow the code.
3. Work through the levels in order. Each page follows the same shape: the question, the idea in plain English, a diagram, the real code, a run, experiments, mistakes to avoid, and a short self-check.
4. Do the matching exercise after each level. Use the [glossary](glossary.md) whenever a word is new.

<div class="cards">
<a class="card" href="pages/getting-started.html"><em>START</em><b>Getting started</b><span>Install, run the tests, run your first level.</span></a>
<a class="card" href="pages/concepts.html"><em>THEORY</em><b>How LLMs work</b><span>Tokens, messages, temperature and cost in plain English.</span></a>
<a class="card" href="pages/l0.html"><em>LEVEL 0</em><b>A single call</b><span>The one primitive every agent is built from.</span></a>
<a class="card" href="pages/learning-path.html"><em>MAP</em><b>Learning path</b><span>Every level, notebook and exercise in order.</span></a>
</div>

## What this guide does not claim

Vigil is a **teaching** project. It shows the shape of real techniques with small, readable code. It is not a production security product, its cost figures are estimates, and the model's answers about a CVE can be wrong. Always check a model's claims against the official advisory before acting on them.
