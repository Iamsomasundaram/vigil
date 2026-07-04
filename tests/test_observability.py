from __future__ import annotations

from pathlib import Path

import pytest

from reliability import r3_observability as r3


def test_nested_spans_have_parent_child_and_single_trace_id():
    tracer = r3.Tracer()
    with tracer.span("root", cve_id="CVE-2021-44228"):
        with tracer.span("child", step="one"):
            pass

    trace = tracer.to_trace()
    assert len(trace.spans) == 2
    root = next(s for s in trace.spans if s.parent_id is None)
    child = next(s for s in trace.spans if s.parent_id is not None)
    assert child.parent_id == root.span_id
    assert trace.trace_id
    assert trace.root_span_id == root.span_id


def test_error_status_is_recorded_and_span_closes():
    tracer = r3.Tracer()
    with pytest.raises(RuntimeError):
        with tracer.span("root"):
            raise RuntimeError("boom")

    trace = tracer.to_trace()
    assert len(trace.spans) == 1
    assert trace.spans[0].status == "error"
    assert trace.spans[0].duration_ms >= 0.0


def test_jsonl_export_round_trip(tmp_path: Path):
    tracer = r3.Tracer(trace_id="trace-jsonl-1")
    with tracer.span("root"):
        pass
    trace = tracer.to_trace()

    out = tmp_path / "traces.jsonl"
    r3.export_trace_jsonl(trace, str(out))

    loaded = r3.load_trace_jsonl(str(out), "trace-jsonl-1")
    assert loaded is not None
    assert loaded.trace_id == "trace-jsonl-1"
    assert len(loaded.spans) == 1


@pytest.mark.asyncio
async def test_traced_decorator_preserves_return_value_async():
    tracer = r3.Tracer()

    @r3.traced(tracer, name="wrapped.add")
    async def add(x: int, y: int) -> int:
        return x + y

    result = await add(2, 3)
    assert result == 5

    trace = tracer.to_trace()
    assert any(span.name == "wrapped.add" for span in trace.spans)


def test_token_attribution_to_active_span():
    tracer = r3.Tracer()
    with tracer.span("root"):
        tracer.add_tokens(120)

    trace = tracer.to_trace()
    root = trace.spans[0]
    assert root.tokens == 120
    assert trace.total_tokens == 120
