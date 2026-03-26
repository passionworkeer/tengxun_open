# RAG Retrieval Eval — v2 Hybrid Index

## Scope

- Dataset: `data/eval_cases_migrated_draft_round4.json`
- Cases: **50** (full eval)
- Schema: `schema_v2`
- Repo snapshot: `external/celery@b8f85213f45c937670a6a6806ce55326a0eb537f`
- Index: `8086` chunks, dict-based adjacency graph
- Query mode: `question_plus_entry` (question + entry_file)
- RRF k: `60`
- Raw artifact: `artifacts/rag/eval_v2_full_50cases.json`

## Metric Contract

1. `chunk_symbols` — retrieved chunk symbol names only; primary headline metric
2. `expanded_fqns` — chunk symbols + heuristic expansion over imports/string_targets/references; diagnostic only

## v2 Index Architecture

| Component | Implementation |
|-----------|---------------|
| **BM25** | Classic TF-IDF with k1=1.5, b=0.75, per-source kind bonus |
| **Semantic** | Hybrid: word-level TF-IDF (identifier tokenization) + char 3-5 n-gram TF-IDF; fusion 0.6/0.4 |
| **Graph** | Dict adjacency BFS; edges from imports, string_targets, references, module siblings; edge-type bonuses (import +0.3, string_target +0.25, reference +0.15) |
| **Fusion** | RRF(k=60) over all three sources |

> **Optimization note**: NetworkX was initially used for graph construction but caused a ~2.7s/batch bottleneck
> (89% of total retrieval time) due to `nx.ego_graph` + `nx.shortest_path_length` calls on a 524,844-edge graph.
> Replaced with a pure Python dict adjacency BFS — retrieval now runs ~225ms per query.

> **Embedding note**: Real embeddings via Qwen3-Embedding-8B (ModelScope API) integrated.
> Bulk pre-computation is rate-limited by ModelScope (~40min for 8086 chunks).
> Pre-compute script: `scripts/precompute_embeddings.py`. Falls back to TF-IDF when cache unavailable.

## Headline Numbers (50-case, question_plus_entry)

| Source | Recall@5 | MRR | Notes |
|:-------|:---------:|:----:|:------|
| BM25 | 0.1451 | 0.2622 | Keyword match baseline |
| Semantic | 0.0533 | 0.0522 | Hybrid TF-IDF + char n-gram; weakest source |
| **Graph** | **0.3234** | **0.4650** | **Strongest single source** |
| **Fused (RRF)** | **0.2252** | **0.3999** | BM25+Semantic+Graph fusion (chunk_symbols) |
| **Fused (RRF)** | **0.2741** | **0.4288** | BM25+Semantic+Graph fusion (expanded_fqns) |

> Graph alone outperforms every individual source — confirming that the import/reference graph structure
> captures code dependency patterns that keyword or bag-of-terms methods miss.

## By Difficulty (Fused, expanded_fqns)

| Difficulty | Recall@5 | MRR | Cases |
|:-----------|:---------:|:----:|:-----:|
| Easy | 0.4444 | 0.4727 | 15 |
| Medium | 0.1958 | 0.4153 | 20 |
| Hard | 0.2080 | 0.4028 | 15 |

## By Failure Type (Fused RRF)

| Type | Recall@5 | MRR | Cases | Interpretation |
|:-----|:---------:|:----:|:-----:|:--------------|
| **Type A (长上下文截断)** | **0.4375** | **0.5250** | 4 | Moderate; some signals in context |
| **Type C (再导出链断裂)** | **0.3750** | **0.3949** | 12 | Graph naturally handles `__init__.py` forwarding |
| Type B (隐式依赖幻觉) | 0.1161 | 0.1920 | 12 | RAG can't fix hallucination; needs FT |
| **Type D (命名空间混淆)** | **0.2000** | **0.1811** | 5 | Retrieval helps with disambiguation in some cases |
| **Type E (动态加载失配)** | **0.2977** | **0.6700** | 17 | String targets in graph help significantly |

> Note: Type D improved from R@5=0.0 (20-case sample) to R@5=0.20 (50-case full eval),
> suggesting some Type D cases are retrievable but the 20-case sample was unlucky.

## Source Breakdown (50-case)

### Graph alone is the dominant signal

| View | Graph R@5 | Graph MRR | BM25 R@5 | Semantic R@5 |
|:-----|:---------:|:--------:|:--------:|:-----------:|
| chunk_symbols | 0.3234 | 0.4650 | 0.1451 | 0.0533 |
| expanded_fqns | 0.3312 | 0.4807 | 0.1831 | 0.0634 |

Graph R@5 is 2.2x BM25 and 6x Semantic on chunk_symbols.

## Diagnosis

- **Graph is the workhorse**: Structural connectivity (imports + references) is more predictive than
  text similarity for code dependency queries.
- **Type D (namespace confusion) is partially retrievable**: The 20-case sample gave R@5=0.0 but the
  full 50-case shows R@5=0.20. Still, 80% of Type D cases are not solved by retrieval — likely needs FT.
- **Type C (re-export chains) is well-supported by graph**: `__init__.py` forwarding chains are naturally
  captured by the import graph structure.
- **Type B (hallucination) is not a retrieval problem**: No amount of retrieved context prevents
  the model from hallucinating implicit dependencies; this is the core motivation for FT.
- **Semantic index is the weakest link**: Pure TF-IDF on code lacks semantic understanding. A real
  embedding model (GPU-backed) would likely make semantic competitive with graph.
- **Fusion hurts vs graph alone**: R@5=0.2741 (fused, expanded_fqns) vs R@5=0.3312 (graph alone).
  The BM25 and semantic sources add noise to the strong graph signal. Consider graph-only or
  graph-weighted fusion.

## What Changed from v1

| | v1 (TF-IDF only) | v2 (Hybrid + Graph) |
|:--|:--|:--|
| Semantic | `_TfIdfIndex` (weak) | `_SemanticIndex` (word TF-IDF + char n-gram, 0.6/0.4) |
| Graph | none | Dict adjacency BFS with edge-type bonuses (import +0.3, string_target +0.25, reference +0.15) |
| Context | Flat all-k retrieval | Tiered: Top-1 full content, Top-2~5 compressed sig+docstring, >5 summary |
| RRF k | hardcoded 60 | configurable via `--rrf-k` |
| Graph construction | N/A | Dict adjacency; replaced NetworkX (was 89% of retrieval time) |

## RRF k Ablation (50-case, expanded_fqns)

| k | Recall@5 | MRR | Notes |
|:--|:---------:|:----:|:------|
| **30** | **0.2941** | **0.4487** | Best — smaller k = more weight to top ranks |
| 60 | 0.2741 | 0.4288 | Default |
| 120 | 0.2841 | 0.4363 | Marginal improvement over k=60 |

k=30 is recommended as the default. Smaller k gives more weight to top-ranked items,
which matters when graph (the strongest source) is much better than BM25/Semantic.

## Next Recommended Moves

1. **Graph-weighted fusion**: Since graph alone (R@5=0.3312) beats fused (R@5=0.2741), try RRF
   with graph source weighted 2-3x, or use graph as primary + BM25/Semantic as tiebreakers.
2. **GPU embedding**: Pre-compute CodeBERT/UniXcoder embeddings for all 8086 chunks (offline),
   store in FAISS index — should dramatically boost the semantic source.
3. **Type D专项**: Mine more Type D candidates; graph structural features (same-symbol different-module)
   may help with disambiguation.
4. **GLM-5 integration**: Verified API works via ModelScope; wire into `evaluation/baseline.py`
   for actual baseline evaluation against the 50-case dataset.
