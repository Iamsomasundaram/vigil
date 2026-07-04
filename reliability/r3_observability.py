"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  VIGIL — Reliability R3: Observability & Tracing                            ║
║                                                                              ║
║  Provides lightweight in-process tracing with nested spans, token           ║
║  attribution, and retrieval by trace_id for debugging and auditability.     ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import argparse
import inspect
import json
import threading
import time
import uuid
from collections import OrderedDict
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Callable

from rich.console import Console
from rich.tree import Tree

from vigil.models import Span, Trace

console = Console()


class _TraceStore:
    def __init__(self, max_traces: int = 100):
        self.max_traces = max_traces
        self._lock = threading.Lock()
        self._traces: OrderedDict[str, Trace] = OrderedDict()

    def put(self, trace: Trace) -> None:
        with self._lock:
            self._traces[trace.trace_id] = trace
            self._traces.move_to_end(trace.trace_id)
            while len(self._traces) > self.max_traces:
                self._traces.popitem(last=False)

    def get(self, trace_id: str) -> Trace | None:
        with self._lock:
            return self._traces.get(trace_id)


TRACE_STORE = _TraceStore(max_traces=200)


class _SpanState:
    def __init__(self, span_id: str, parent_id: str | None, name: str, attributes: dict[str, str]):
        self.span_id = span_id
        self.parent_id = parent_id
        self.name = name
        self.attributes = attributes
        self.start_ms = time.perf_counter() * 1000
        self.status = "ok"
        self.tokens: int | None = None


class SpanScope(AbstractContextManager["SpanScope"]):
    def __init__(self, tracer: "Tracer", name: str, attributes: dict[str, str]):
        self.tracer = tracer
        self.name = name
        self.attributes = attributes
        self._state: _SpanState | None = None

    def __enter__(self) -> "SpanScope":
        self._state = self.tracer._open_span(self.name, self.attributes)
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> bool:
        status = "error" if exc_type is not None else "ok"
        self.tracer._close_span(self._state, status=status)
        return False

    @property
    def span_id(self) -> str:
        if self._state is None:
            return ""
        return self._state.span_id

    def add_tokens(self, tokens: int) -> None:
        if self._state is None:
            return
        self.tracer.add_tokens(tokens, span_id=self._state.span_id)


class Tracer:
    def __init__(self, trace_id: str | None = None):
        self.trace_id = trace_id or str(uuid.uuid4())
        self._stack: list[_SpanState] = []
        self._spans: list[Span] = []
        self._root_span_id: str | None = None

    def span(self, name: str, **attributes: Any) -> SpanScope:
        attrs = {k: str(v) for k, v in attributes.items()}
        return SpanScope(self, name, attrs)

    def _open_span(self, name: str, attributes: dict[str, str]) -> _SpanState:
        parent_id = self._stack[-1].span_id if self._stack else None
        span_id = str(uuid.uuid4())
        state = _SpanState(span_id=span_id, parent_id=parent_id, name=name, attributes=attributes)
        if self._root_span_id is None:
            self._root_span_id = span_id
        self._stack.append(state)
        return state

    def _close_span(self, state: _SpanState | None, status: str) -> None:
        if state is None:
            return
        if not self._stack or self._stack[-1].span_id != state.span_id:
            self._stack = [s for s in self._stack if s.span_id != state.span_id]
        else:
            self._stack.pop()

        state.status = status
        end_ms = time.perf_counter() * 1000
        duration_ms = max(0.0, end_ms - state.start_ms)

        self._spans.append(
            Span(
                span_id=state.span_id,
                parent_id=state.parent_id,
                name=state.name,
                attributes=state.attributes,
                start_ms=state.start_ms,
                duration_ms=duration_ms,
                status="error" if status == "error" else "ok",
                tokens=state.tokens,
            )
        )

    def add_tokens(self, tokens: int, span_id: str | None = None) -> None:
        if span_id is None:
            if not self._stack:
                return
            state = self._stack[-1]
        else:
            state = next((s for s in self._stack if s.span_id == span_id), None)
            if state is None:
                return

        current = state.tokens or 0
        state.tokens = max(0, current + tokens)

    def to_trace(self) -> Trace:
        if not self._spans:
            raise ValueError("No spans recorded; open at least one span before exporting")

        root = self._root_span_id or self._spans[0].span_id
        starts = [s.start_ms for s in self._spans]
        ends = [s.start_ms + s.duration_ms for s in self._spans]
        total_duration = max(0.0, max(ends) - min(starts))
        total_tokens = sum(s.tokens or 0 for s in self._spans)
        estimated_cost = ((total_tokens * 0.150) / 1_000_000) if total_tokens else 0.0

        trace = Trace(
            trace_id=self.trace_id,
            root_span_id=root,
            spans=self._spans,
            total_duration_ms=round(total_duration, 3),
            total_tokens=total_tokens,
            estimated_cost_usd=round(estimated_cost, 6),
        )
        TRACE_STORE.put(trace)
        return trace


def export_trace_jsonl(trace: Trace, file_path: str) -> None:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(trace.model_dump(), ensure_ascii=True) + "\n")


def load_trace_jsonl(file_path: str, trace_id: str) -> Trace | None:
    path = Path(file_path)
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if payload.get("trace_id") == trace_id:
            return Trace.model_validate(payload)
    return None


def get_trace(trace_id: str, jsonl_path: str | None = None) -> Trace | None:
    trace = TRACE_STORE.get(trace_id)
    if trace is not None:
        return trace
    if jsonl_path:
        return load_trace_jsonl(jsonl_path, trace_id)
    return None


def render_trace_tree(trace: Trace) -> None:
    by_parent: dict[str | None, list[Span]] = {}
    for span in trace.spans:
        by_parent.setdefault(span.parent_id, []).append(span)

    for parent_key in by_parent:
        by_parent[parent_key].sort(key=lambda s: s.start_ms)

    root_span = next((s for s in trace.spans if s.span_id == trace.root_span_id), trace.spans[0])
    root_label = f"{root_span.name} [{root_span.duration_ms:.1f}ms] status={root_span.status}"
    tree = Tree(root_label)

    def walk(node, parent_id: str):
        for child in by_parent.get(parent_id, []):
            tok = f" tokens={child.tokens}" if child.tokens is not None else ""
            attrs = " ".join(f"{k}={v}" for k, v in child.attributes.items())
            label = f"{child.name} [{child.duration_ms:.1f}ms] status={child.status}{tok} {attrs}".strip()
            child_node = node.add(label)
            walk(child_node, child.span_id)

    walk(tree, root_span.span_id)
    console.print(tree)
    console.print(
        f"trace_id={trace.trace_id}  total={trace.total_duration_ms:.1f}ms  "
        f"tokens={trace.total_tokens}  cost=${trace.estimated_cost_usd:.6f}"
    )


def traced(
    tracer: Tracer,
    name: str | None = None,
    attr_builder: Callable[..., dict[str, Any]] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        span_name = name or fn.__name__

        if inspect.iscoroutinefunction(fn):
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                attrs = attr_builder(*args, **kwargs) if attr_builder else {}
                with tracer.span(span_name, **attrs):
                    return await fn(*args, **kwargs)

            return async_wrapper

        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            attrs = attr_builder(*args, **kwargs) if attr_builder else {}
            with tracer.span(span_name, **attrs):
                return fn(*args, **kwargs)

        return sync_wrapper

    return decorator


async def run_traced_l4(cve_id: str, export_path: str | None = None) -> tuple[dict[str, Any], Trace]:
    from levels.l4_tool_use import analyse_cve, get_usage

    tracer = Tracer()
    with tracer.span("analyse", cve_id=cve_id, target="l4"):
        with tracer.span("llm.tool_loop", model="gpt-4o-mini"):
            analysis, tool_log = await analyse_cve(cve_id)
        for tc in tool_log:
            with tracer.span("tool.call", name=tc.get("tool", "unknown")):
                pass

    usage = get_usage()
    trace = tracer.to_trace()
    token_total = int(usage.get("total_tokens", 0))
    if token_total > 0:
        for s in trace.spans:
            if s.name == "llm.tool_loop":
                s.tokens = token_total
                break
        trace.total_tokens = token_total
        trace.estimated_cost_usd = float(usage.get("estimated_cost_usd", 0.0))
        TRACE_STORE.put(trace)

    if export_path:
        export_trace_jsonl(trace, export_path)

    return {
        "cve_id": cve_id,
        "analysis": analysis.model_dump() if hasattr(analysis, "model_dump") else dict(analysis),
        "tool_calls": tool_log,
        "token_usage": usage,
        "trace_id": trace.trace_id,
    }, trace


def main() -> None:
    parser = argparse.ArgumentParser(description="R3 tracing demo over L4")
    parser.add_argument("cve_id", nargs="?", default="CVE-2021-44228")
    parser.add_argument("--trace", action="store_true", help="Print span tree")
    parser.add_argument("--export", default="", help="Optional JSONL export path")
    args = parser.parse_args()

    import asyncio

    payload, trace = asyncio.run(run_traced_l4(args.cve_id, export_path=args.export or None))
    console.print(f"R3 trace captured for {payload['cve_id']}: trace_id={payload['trace_id']}")
    if args.trace:
        render_trace_tree(trace)


if __name__ == "__main__":
    main()
