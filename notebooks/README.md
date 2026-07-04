# Vigil Notebooks — Experiment Live

Runnable notebooks that let you **poke** at GenAI concepts and see the effect
immediately. All four are **offline-friendly**: with no `OPENAI_API_KEY`, live calls
are skipped but every concept cell still runs.

## Run them

```bash
pip install -e ".[notebooks]"
jupyter lab notebooks/
```

## The path

| Notebook                                           | You'll learn                                                         |
| -------------------------------------------------- | -------------------------------------------------------------------- |
| [00_setup.ipynb](00_setup.ipynb)                   | Environment check + the message list, the atomic unit of every level |
| [01_tokenization.ipynb](01_tokenization.ipynb)     | How text becomes tokens, and why budgets matter                      |
| [02_prompting.ipynb](02_prompting.ipynb)           | How the system role steers the model — the cheapest lever you have   |
| [03_embeddings_rag.ipynb](03_embeddings_rag.ipynb) | Embeddings, cosine similarity, and semantic recall (local vs real)   |

Each notebook links back to the production code in `levels/` and `vigil/` so you can
trace a concept from the sandbox into the real pipeline.

Prefer graded practice? See [../exercises/README.md](../exercises/README.md).
