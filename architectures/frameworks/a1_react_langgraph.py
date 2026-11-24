"""F7: A minimal A1-style ReAct port using LangGraph when installed."""

from __future__ import annotations

import asyncio
import json
import os
from typing import TypedDict

from openai import AsyncOpenAI

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


class GraphState(TypedDict):
    cve_id: str
    verdict: str


def _fallback_verdict(cve_id: str) -> str:
    return f"Fallback verdict for {cve_id}: patch quickly and monitor exploitation telemetry."


def build_graph():
    """Build the LangGraph graph. Raises ImportError if langgraph is absent."""
    from langgraph.graph import END, START, StateGraph

    async def reason(state: GraphState) -> GraphState:
        cve_id = state["cve_id"]
        client = AsyncOpenAI(timeout=45.0)
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a concise vulnerability analyst."},
                {"role": "user", "content": f"Give a one-line remediation verdict for {cve_id}."},
            ],
            temperature=0.1,
            max_tokens=120,
        )
        verdict = (response.choices[0].message.content or "").strip()
        return {**state, "verdict": verdict}

    graph = StateGraph(GraphState)
    graph.add_node("reason", reason)
    graph.add_edge(START, "reason")
    graph.add_edge("reason", END)
    return graph.compile()


async def analyse_cve(cve_id: str) -> dict:
    """Run the LangGraph port if available, otherwise degrade clearly."""
    try:
        app = build_graph()
        out = await app.ainvoke({"cve_id": cve_id, "verdict": ""})
        return {"cve_id": cve_id, "framework": "langgraph", "verdict": out.get("verdict", "")}
    except ImportError:
        return {"cve_id": cve_id, "framework": "fallback", "verdict": _fallback_verdict(cve_id)}


def main() -> None:
    import sys

    cve_id = sys.argv[1] if len(sys.argv) > 1 else "CVE-2021-44228"
    print(json.dumps(asyncio.run(analyse_cve(cve_id)), indent=2))


if __name__ == "__main__":
    main()
