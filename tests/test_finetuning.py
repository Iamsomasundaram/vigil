from __future__ import annotations

from levels.foundations.finetuning import recommend_approach, validate_finetune_dataset


def test_recommend_prefers_rag_for_fresh_knowledge():
    out = recommend_approach(needs_fresh_knowledge=True, data_volume=50)
    assert out["recommended"] == "rag"
    assert any("RAG" in r for r in out["reasons"])


def test_recommend_prefers_lora_for_stable_strict_high_data():
    out = recommend_approach(
        task_stability="stable",
        data_volume=2000,
        needs_fresh_knowledge=False,
        strict_format=True,
    )
    assert out["recommended"] == "fine_tune_lora"


def test_recommend_prefers_prompt_only_for_tiny_data():
    out = recommend_approach(data_volume=0, strict_format=False, needs_fresh_knowledge=False)
    assert out["recommended"] == "prompt_only"


def test_validate_dataset_flags_issues():
    records = [
        {"messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]},
        {"messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]},  # dup
        {"messages": [{"role": "user", "content": "q"}, {"role": "assistant", "content": ""}]},  # empty
        {"messages": [{"role": "user", "content": "only user"}]},  # role error
    ]
    out = validate_finetune_dataset(records)
    assert out["total"] == 4
    assert out["duplicates"] == 1
    assert out["empty_completions"] == 1
    assert out["role_errors"] == 1
    assert out["ready_to_train"] is False


def test_validate_dataset_ready_when_clean():
    records = [
        {"messages": [{"role": "user", "content": f"q{i}"}, {"role": "assistant", "content": f"a{i}"}]}
        for i in range(12)
    ]
    out = validate_finetune_dataset(records)
    assert out["valid"] == 12
    assert out["ready_to_train"] is True
