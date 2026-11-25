---
title: "Semantic caching"
summary: Reuse answers to similar questions to save cost and time, and understand how a loose threshold returns wrong answers.
section: Foundations
order: 11
---

# Semantic caching

**The question this page answers:** if many people ask almost the same question, can I answer once and reuse it?

Every model call costs money and takes time. If someone already asked "What is CVE-2021-44228?" a minute ago, calling the model again for "Tell me about CVE-2021-44228" is wasteful. A **cache** remembers answers. Vigil has two kinds, and the difference between them is the lesson of this page.

| | Exact cache | Semantic cache |
| --- | --- | --- |
| Reuses an answer when | the request is **identical** | the request is **similar enough** |
| Code | `vigil/cache.py` | `levels/foundations/semantic_cache.py` |
| Risk of a wrong answer | none from matching | real, depends on the threshold |
| Where it is used | the API, for the L0 and L4 endpoints | a standalone teaching module (spec F24) |

> **Note** The semantic cache is a **teaching module**. It is exercised by its tests and by the endpoint `POST /foundations/semantic-cache`, but the cached API calls (the L0 and L4 analyse endpoints) use the exact cache.

## The exact cache

The API caches whole responses for its L0 and L4 analyse endpoints. The key is a hash of the request, the model name and a namespace, so only an identical request gets a hit. Here is the storage backend:

{{include vigil/cache.py#CacheBackend}}

Points to notice:

- **A time to live (TTL).** An entry expires after `default_ttl` seconds (the API reads `VIGIL_CACHE_TTL`, default 300). Old answers go stale, so they must not live forever.
- **Redis if available, memory if not.** If the `REDIS_URL` setting is present and the connection works, it uses Redis. Otherwise, or if Redis fails, it quietly falls back to a plain in-memory dictionary. The cache is an optimisation, so a failure never breaks the request.
- **Values are stored as JSON.** Anything you cache must be JSON-serialisable.

A hit costs no model call, so the API returns `cache.from_cache` set to true with zero tokens and zero cost.

## The semantic cache

An exact cache misses on any change of wording. A **semantic** cache asks "is this question close enough to one I already answered?" and, if so, returns the stored answer.

{{flow: New query | Compare with stored queries ~ similarity score | Best match above the threshold? | Hit: return stored answer | Miss: call the model and store}}

Here is the whole class:

{{include levels/foundations/semantic_cache.py#SemanticCache}}

How it decides:

1. `_terms` lowercases the query and drops filler words, leaving a **set of terms**.
2. `_cosine` measures overlap between two sets as shared terms divided by the square root of the product of the set sizes. That gives a number from 0 (nothing shared) to 1 (identical sets).
3. If the best stored match scores at or above `threshold` (default `0.8`), it is a **hit**.
4. Entries older than `ttl_seconds` (default 300) are pruned before every lookup.

Because it compares sets of words, it is a **lexical** similarity, not a deep semantic one. A real semantic cache would compare embeddings from a trained model (see [Retrieval and RAG](retrieval.md)).

## The threshold is the whole game

I ran the module's own two example queries offline:

- `What is CVE-2021-44228?` becomes the terms `cve`, `2021`, `44228`.
- `Tell me about CVE-2021-44228` becomes `me`, `about`, `cve`, `44228`, `tell`, `2021`.

Their similarity is `0.7071`. With the **default threshold of 0.8, that is a miss**: the second question would call the model again. The tests use a threshold of `0.5`, where it is a hit.

So choosing the threshold trades cost against correctness:

| Threshold | Effect |
| --- | --- |
| Too high | Few hits, little saving, behaves like an exact cache |
| Too low | Many hits, but some are **wrong answers** |

Here is a wrong answer, from running the code at threshold `0.5`. After storing the answer "Yes, in 2.17.1" for `Is CVE-2021-44228 patched?`, the question `Is CVE-2021-44228 exploited?` scored `0.75` and **hit the cache**, returning an answer to a different question. At the default `0.8` it correctly missed.

> **Warning** A cache that returns a confident answer to the wrong question is worse than no cache. In a security setting, keep the threshold high, keep TTLs short, and never cache answers that depend on fresh data such as live exploit status.

## Measuring it

`simulate` replays a list of query and response pairs and reports each lookup's hit or miss with its similarity, plus the totals:

{{include levels/foundations/semantic_cache.py#simulate}}

`stats()` gives entries, hits, misses, hit rate, threshold and TTL. The hit rate is what tells you whether the cache is earning its keep, and you should always read it alongside a sample of the actual hits to see whether they were correct.

## Run it

```bash
python levels/foundations/semantic_cache.py
python levels/foundations/semantic_cache.py --threshold 0.5
```

You should see a JSON trace for three queries, with a hit flag and similarity for each, and the final stats. Compare the output at the two thresholds.

## Try it

> **Try it** 1) Run with `--threshold 0.5` and then `0.8` and note which query pairs change from hit to miss. 2) Add two queries that differ by one important word, such as `patched` and `exploited`, and check whether they wrongly hit. 3) Set a very small `ttl_seconds` and show an entry expiring.

## Common mistakes

- **Choosing the threshold by feel.** Test it on real near-duplicate and near-miss pairs.
- **Caching answers that go stale.** Always use a TTL.
- **Caching personalised or sensitive answers** for everyone to share.
- **Reading hit rate alone.** A high hit rate with wrong hits is a bug, not a win.
- **Forgetting the model and settings.** Different models or temperatures should not share cache entries; the API's key includes the model for this reason.

## Check yourself

??? What is the difference between an exact cache and a semantic cache?
    An exact cache hits only on an identical request. A semantic cache also hits when a new request is similar enough to a stored one.

??? Why does the default demo not get a hit at threshold 0.8?
    The two example queries have a similarity of about 0.71, below 0.8, so the second is a miss.

??? What is the main risk of lowering the threshold?
    More hits, but some return the answer to a different question.

Next: [Theme: Incident response](incident-ops.md) applies these ideas to a different domain.
