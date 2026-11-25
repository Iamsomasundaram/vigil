"""
vigil/routers/extensions.py — Axis-extension endpoints (E4 inference layer).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from vigil.models import InferenceComparison, ProviderInfo, RoutePolicy
from vigil.schemas import InferenceCompareRequest

router = APIRouter()


@router.get("/inference/policy", response_model=list[RoutePolicy], tags=["extensions"])
def inference_policy():
    """Return configured inference routing/fallback policies."""
    try:
        from vigil.inference import get_all_policies

        return get_all_policies()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/inference/providers", response_model=list[ProviderInfo], tags=["extensions"])
def inference_providers():
    """List configured inference providers and their capability flags (F3)."""
    try:
        from vigil.inference import get_providers

        return get_providers()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/inference/compare", response_model=InferenceComparison, tags=["extensions"])
async def inference_compare(req: InferenceCompareRequest):
    """Run the same prompt across providers and compare latency/cost/output (F3)."""
    try:
        from vigil.inference import compare_inference

        messages = [
            {
                "role": "user",
                "content": f"In two sentences, summarise the risk of {req.cve_id}.",
            }
        ]
        return await compare_inference(
            messages=messages,
            task=req.task,
            providers=req.providers,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
