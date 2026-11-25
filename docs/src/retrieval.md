---
title: "Retrieval and RAG"
summary: Find the right passages before the model answers: chunking, scoring, retrieval metrics, hybrid search and reranking.
section: Foundations
order: 7
---

# Retrieval and RAG

**The question this page answers:** how do I give a model the *right* facts to answer from, instead of trusting its memory?

In [Level 0](l0.md) the model answered from what it learned in training, which can be out of date or wrong. **Retrieval-augmented generation (RAG)** fixes that in two moves: first **retrieve** the most relevant passages from your own documents, then hand them to the model along with the question so it answers from them.

{{flow: Question | Retrieve ~ find the best passages | Prompt ~ question + passages | Model | Answer}}

Most RAG failures are not model failures. They are **retrieval** failures: the right passage was never found, so the model never saw it. This page is about making retrieval good and *measuring* whether it is.

> **Note** The code in `levels/foundations/retrieval_quality.py` is deliberately small and runs **offline with no API key**. Its scoring is word matching, not real semantic search. Read the sections below to see exactly what is simplified.

## Step 1: Chunking

Documents are too long to search or send whole, so they are cut into **chunks**. Chunk size is a real trade-off:

- **Small chunks** are precise but may lose surrounding context.
- **Large chunks** keep context but dilute the match and cost more tokens when sent to the model.

Vigil cuts by words, with an **overlap** so a sentence on a boundary appears in two chunks:

{{include levels/foundations/retrieval_quality.py#chunk_text}}

Two details worth noticing: the chunk size is never allowed below 20 words, and the overlap is forced to be smaller than the chunk so the window always moves forward.

## Step 2: Scoring (lexical retrieval)

Each chunk is reduced to the set of its non-trivial words. A query is scored against a chunk by how many query words it contains:

{{include levels/foundations/retrieval_quality.py#_score}}

- **Coverage** is the share of query words found in the chunk. It carries 75% of the score.
- **Density** is the share of the chunk's words that matched. It carries 25%, and slightly favours tighter chunks.

`retrieve` scores every chunk and returns the best `top_k`:

{{include levels/foundations/retrieval_quality.py#retrieve}}

### What this simple scorer cannot do

It matches **exact words only**. There is no stemming and no synonyms. Try the default query `log4j remote code execution patch` against the built-in Log4j advisory: the advisory says "patched", not "patch", so the word `patch` does **not** match, and the chunk scores on the other four words.

This is the same weakness real keyword search has, and it is why the next two steps exist.

## Step 3: Measuring retrieval

"It looks right" is not a measurement. To compare two settings you need a labelled set: queries, plus the documents that *should* be found. Vigil ships one in `data/eval/retrieval_golden.json`, where each row looks like this:

```text
{"query": "log4j remote code execution patch", "relevant_doc_ids": ["doc1"]}
```

Three standard metrics score a ranked list against those labels. Each takes the retrieved document ids and the relevant ones:

{{include levels/foundations/retrieval_quality.py#recall_at_k}}

{{include levels/foundations/retrieval_quality.py#reciprocal_rank}}

{{include levels/foundations/retrieval_quality.py#ndcg_at_k}}

| Metric | Question it answers | Range |
| --- | --- | --- |
| **Recall@k** | Of the documents I needed, how many appeared in the top k? | 0 to 1 |
| **MRR** (mean reciprocal rank) | How near the top was the *first* relevant result? 1st gives 1.0, 2nd gives 0.5, 3rd about 0.33 | 0 to 1 |
| **nDCG@k** | Are the relevant results ranked *above* the irrelevant ones? | 0 to 1 |

`evaluate_retrieval_settings` runs two chunking configurations over the whole labelled set and reports the averages for each, a winner and the differences.

> **Warning** On the built-in sample, all three documents are only about 23 words long, so each becomes a single chunk whatever size you choose. Comparing chunk sizes there gives a **tie**, and that is correct, not a bug. Chunk-size experiments only mean something on longer documents. Add your own longer texts through the `documents` argument.

## Step 4: Hybrid retrieval and reranking

Real systems rarely rely on one signal. Vigil's hybrid lab blends two:

- a **lexical** score (word overlap, as above), and
- a **vector** score, from turning text into a list of numbers and comparing them with cosine similarity.

The two are normalised to the same scale and mixed with a weight `alpha`, where `1.0` means pure lexical:

{{include levels/foundations/retrieval_quality.py#hybrid_retrieve}}

An optional **rerank** step then re-scores the shortlist with a stricter check, rewarding chunks that contain the query words and have them early:

{{include levels/foundations/retrieval_quality.py#_rerank}}

### The honest caveat about the "vector" score

The vector here comes from `_hash_embed`:

{{include levels/foundations/retrieval_quality.py#_hash_embed}}

It hashes each *word* into one of 64 buckets and counts. That is a **teaching stand-in**, not a real embedding. It has no idea that "arbitrary code execution" and "remote code execution" mean nearly the same thing. It also lets unrelated text score above zero when words happen to land in the same bucket: for the query `arbitrary code execution in log4j`, the unrelated HTTP/2 note gets a non-zero vector score while its lexical score is zero.

A **real embedding model** maps meaning to nearby points, so paraphrases score high even with no shared words. Vigil supports that in L5 memory by setting `VIGIL_EMBED_MODE=openai`, which uses `text-embedding-3-small`. The notebook `notebooks/03_embeddings_rag.ipynb` walks through local versus real embeddings. Rerunning the lab with real embeddings would give different, better semantic results; the code here does not do that.

## Run it

```bash
python levels/foundations/retrieval_quality.py "log4j remote code execution patch"
```

This prints the index size, the average chunk length and a table of the top hits with the matching words. For the built-in data you should see the Log4j advisory ranked first. The notebook runs the embedding comparison offline:

```bash
jupyter lab notebooks/
```

## Try it

> **Try it** 1) Run the default query, then change `patch` to `patched` and compare the score. This shows why exact word matching is fragile. 2) Call `hybrid_lab` with `alpha=1.0` and then `alpha=0.0` and watch the ranking change. 3) Add two long documents of your own and compare chunk sizes 40 and 120 with `evaluate_retrieval_settings`.

## Common mistakes

- **Judging by eye.** Build a small labelled set and use Recall, MRR and nDCG.
- **Tuning on three examples.** A tiny benchmark tells you almost nothing; it only proves the mechanics.
- **Chunks too large.** The relevant sentence is buried and you pay for the extra tokens.
- **Chunks too small.** The passage loses the context that made it meaningful.
- **Assuming the vector score means semantic.** Here it does not; it is a hash.
- **Blaming the model.** If the right passage was not retrieved, no prompt can fix the answer.

## Check yourself

??? Why does overlap between chunks help?
    A fact that sits on a chunk boundary would otherwise be cut in half. Overlap keeps it whole in at least one chunk.

??? A query uses the word "patch" but the document says "patched". What happens in Vigil's lexical search, and why?
    That word does not match, because matching is on exact words with no stemming. The chunk can still match on other words, but its score is lower.

??? What does MRR reward that Recall@k does not?
    Where the first relevant result appears. Recall@k only checks whether it is in the top k; MRR rewards ranking it first.

??? Why is Vigil's built-in vector score not real semantic search?
    It hashes words into buckets instead of using a trained embedding model, so it cannot see that different words mean the same thing.

Next: [Factuality and citations](factuality.md) checks that an answer is actually supported by what was retrieved.
