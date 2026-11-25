"""
vigil/routers/foundations.py — Foundations (F-series), Claude bridge, MCP loop and theme endpoints.
"""

from __future__ import annotations

import os
import time
from fastapi import APIRouter, HTTPException
from vigil.models import (
    AdaptationRecommendation,
    ClaudeMappedMessages,
    FactualityReport,
    FinetuneDatasetReport,
    HybridRetrievalReport,
    McpLoopReport,
    ModelRecommendation,
    PrivacyReport,
    PromptComparison,
    PromptExperimentReport,
    PromptVersion,
    ResponsibleAIReport,
    RetrievalEvalReport,
    RetrievalLabReport,
    SemanticCacheReport,
    TokenReport,
)
from vigil.schemas import (
    AdaptationRequest,
    ClaudeMapRequest,
    FactualityCheckRequest,
    FinetuneDatasetRequest,
    HybridRetrievalRequest,
    IncidentThemeRequest,
    IncidentThemeResponse,
    McpLoopRequest,
    ModelSelectRequest,
    PrivacyRedactRequest,
    PromptCompareRequest,
    PromptCompareVersionsRequest,
    ResponsibleAIRequest,
    RetrievalEvalRequest,
    RetrievalLabRequest,
    SemanticCacheRequest,
    TokenizeRequest,
)

router = APIRouter()


@router.post("/foundations/tokenize", response_model=TokenReport, tags=["foundations"])
def tokenize_foundations(req: TokenizeRequest):
    """F4: tokenize text, report token count vs context limit and projected cost."""
    try:
        from levels.foundations.tokenization import tokenize_report

        model = req.model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        return TokenReport.model_validate(tokenize_report(req.text, model=model))
    except ModuleNotFoundError as e:
        raise HTTPException(status_code=503, detail=f"Tokenizer dependency missing ({e}). Install with: pip install -e .[foundations]")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/foundations/prompt-compare", response_model=PromptComparison, tags=["foundations"])
async def prompt_compare_foundations(req: PromptCompareRequest):
    """F6: compare prompt techniques on the same CVE task."""
    try:
        from levels.foundations.prompting import prompt_compare

        return PromptComparison.model_validate(await prompt_compare(req.cve_id, req.advisory_text))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/foundations/retrieval-lab", response_model=RetrievalLabReport, tags=["foundations"])
def retrieval_lab_foundations(req: RetrievalLabRequest):
    """F11: tune chunking/indexing settings and inspect ranked retrieval hits."""
    try:
        from levels.foundations.retrieval_quality import retrieval_lab

        return RetrievalLabReport.model_validate(
            retrieval_lab(
                query=req.query,
                chunk_size_words=req.chunk_size_words,
                overlap_words=req.overlap_words,
                top_k=req.top_k,
            )
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/foundations/retrieval-eval", response_model=RetrievalEvalReport, tags=["foundations"])
def retrieval_eval_foundations(req: RetrievalEvalRequest):
    """F12: evaluate retrieval quality using Recall@k, MRR, and nDCG."""
    try:
        from levels.foundations.retrieval_quality import evaluate_retrieval_settings

        out = evaluate_retrieval_settings(
            dataset_path=req.dataset_path,
            chunk_size_a=req.chunk_size_a,
            overlap_a=req.overlap_a,
            chunk_size_b=req.chunk_size_b,
            overlap_b=req.overlap_b,
            k=req.k,
        )
        return RetrievalEvalReport.model_validate(out)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/foundations/factuality-check", response_model=FactualityReport, tags=["foundations"])
def factuality_check_foundations(req: FactualityCheckRequest):
    """F13: verify answer claims against provided evidence snippets."""
    try:
        from levels.foundations.factuality import factuality_check

        out = factuality_check(
            answer_text=req.answer_text,
            evidence_snippets=req.evidence_snippets,
            support_threshold=req.support_threshold,
        )
        return FactualityReport.model_validate(out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/foundations/prompt-versions", response_model=list[PromptVersion], tags=["foundations"])
def prompt_versions_foundations(path: str = "data/prompts/f14_prompt_versions.json"):
    """F14: list available prompt versions for replay/experimentation."""
    try:
        from levels.foundations.prompt_lifecycle import list_versions

        return [PromptVersion.model_validate(v) for v in list_versions(path)]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/foundations/prompt-versions/compare", response_model=PromptExperimentReport, tags=["foundations"])
def prompt_versions_compare_foundations(req: PromptCompareVersionsRequest):
    """F14: compare prompt versions on fixed items and return a winner."""
    try:
        from levels.foundations.prompt_lifecycle import compare_versions

        out = compare_versions(
            version_a=req.version_a,
            version_b=req.version_b,
            items=req.items,
            path=req.path,
        )
        return PromptExperimentReport.model_validate(out)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/foundations/privacy/redact", response_model=PrivacyReport, tags=["foundations"])
def privacy_redact_foundations(req: PrivacyRedactRequest):
    """F15: redact sensitive patterns and produce a safe log snapshot."""
    try:
        from levels.foundations.privacy import privacy_report

        out = privacy_report(req.text, sample_payload=req.sample_payload)
        return PrivacyReport.model_validate(out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/foundations/hybrid-retrieval", response_model=HybridRetrievalReport, tags=["foundations"])
def hybrid_retrieval_foundations(req: HybridRetrievalRequest):
    """F16: compare lexical, vector, and hybrid retrieval with optional reranking."""
    try:
        from levels.foundations.retrieval_quality import hybrid_lab

        out = hybrid_lab(
            query=req.query,
            chunk_size_words=req.chunk_size_words,
            overlap_words=req.overlap_words,
            alpha=req.alpha,
            rerank=req.rerank,
            top_k=req.top_k,
        )
        return HybridRetrievalReport.model_validate(out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/foundations/adaptation/recommend", response_model=AdaptationRecommendation, tags=["foundations"])
def adaptation_recommend(req: AdaptationRequest):
    """F21: recommend prompt/few-shot/RAG/fine-tune approach from task traits."""
    try:
        from levels.foundations.finetuning import recommend_approach

        out = recommend_approach(
            task_stability=req.task_stability,
            data_volume=req.data_volume,
            needs_fresh_knowledge=req.needs_fresh_knowledge,
            strict_format=req.strict_format,
            latency_sensitive=req.latency_sensitive,
            domain_shift=req.domain_shift,
        )
        return AdaptationRecommendation.model_validate(out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/foundations/finetune/validate", response_model=FinetuneDatasetReport, tags=["foundations"])
def finetune_validate(req: FinetuneDatasetRequest):
    """F21: validate a chat-style fine-tuning dataset for common quality issues."""
    try:
        from levels.foundations.finetuning import validate_finetune_dataset

        return FinetuneDatasetReport.model_validate(validate_finetune_dataset(req.records))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/foundations/model-select", response_model=ModelRecommendation, tags=["foundations"])
def model_select_foundations(req: ModelSelectRequest):
    """F22: recommend a Claude model tier (Haiku/Sonnet/Opus) from constraints."""
    try:
        from levels.foundations.model_selection import recommend_model

        out = recommend_model(
            task_complexity=req.task_complexity,
            latency_sensitive=req.latency_sensitive,
            cost_sensitive=req.cost_sensitive,
            high_volume=req.high_volume,
            high_stakes=req.high_stakes,
        )
        return ModelRecommendation.model_validate(out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/claude/map-messages", response_model=ClaudeMappedMessages, tags=["claude"])
def claude_map_messages(req: ClaudeMapRequest):
    """Claude bridge: map OpenAI-style messages to Claude Messages API shape."""
    try:
        from vigil.claude_provider import map_messages_to_claude

        return ClaudeMappedMessages.model_validate(map_messages_to_claude(req.messages))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mcp/tool-loop", response_model=McpLoopReport, tags=["claude"])
async def mcp_tool_loop(req: McpLoopRequest):
    """MCP client path: run a deterministic tool loop over the MCP server tools."""
    try:
        from vigil_mcp.vigil_client import run_tool_loop

        return McpLoopReport.model_validate(await run_tool_loop(cve_id=req.cve_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/foundations/responsible-ai", response_model=ResponsibleAIReport, tags=["foundations"])
def responsible_ai_foundations(req: ResponsibleAIRequest):
    """F23: content moderation + fairness (demographic parity) evaluation."""
    try:
        from levels.foundations.responsible_ai import responsible_ai_report

        out = responsible_ai_report(texts=req.texts, outcomes=req.outcomes)
        return ResponsibleAIReport.model_validate(out)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/foundations/semantic-cache", response_model=SemanticCacheReport, tags=["foundations"])
def semantic_cache_foundations(req: SemanticCacheRequest):
    """F24: replay queries through a similarity-based semantic cache."""
    try:
        from levels.foundations.semantic_cache import simulate

        return SemanticCacheReport.model_validate(simulate(req.pairs, threshold=req.threshold))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/themes/incident/analyse", response_model=IncidentThemeResponse, tags=["themes"])
def analyse_theme_incident(req: IncidentThemeRequest):
    """T1: domain transfer demo from CVE workflows to incident-response operations."""
    try:
        from levels.themes.incident_ops import analyse_incident

        start = time.perf_counter()
        report = analyse_incident(
            alert_text=req.alert_text,
            service_name=req.service_name,
            customer_impact=req.customer_impact,
            signals=req.signals,
        )
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {
            "theme": "T1",
            "scenario": "Incident Response Ops",
            "elapsed_ms": elapsed_ms,
            "report": report,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
