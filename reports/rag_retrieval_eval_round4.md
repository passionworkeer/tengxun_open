# RAG Retrieval Eval Round 4

## Scope

- Dataset: `data/eval_cases_migrated_draft_round4.json`
- Cases: `32`
- Schema: `schema_v2`
- Repo snapshot: `external/celery@b8f85213f45c937670a6a6806ce55326a0eb537f`
- Primary query mode: `question_only`
- Comparison query mode: `question_plus_entry`
- Top-k: `5`
- Per-source depth: `12`
- Raw JSON artifacts:
  - `artifacts/rag/rag_eval_round4_question_only.json`
  - `artifacts/rag/rag_eval_round4_question_plus_entry.json`

## Metric Contract

This report uses two ranking views and keeps them separate on purpose:

1. `chunk_symbols`
   - Only uses retrieved chunk symbols.
   - This is the primary retrieval metric and the headline number for the current prototype.
2. `expanded_fqns`
   - Uses retrieved chunks plus heuristic expansion over imports, string targets, and references.
   - This is useful for diagnostics, but it is **not** a pure retrieval metric.

## Headline Numbers

| View | Recall@5 | MRR | Notes |
| :--- | :--- | :--- | :--- |
| Fused `chunk_symbols` | `0.2962` | `0.5120` | Current honest retrieval headline |
| Fused `expanded_fqns` | `0.2140` | `0.4521` | Retrieval + heuristic expansion, not for headline |

## Query-Mode Comparison

### Fused Retrieval Views

| View | `question_only` | `question_plus_entry` | Delta | Interpretation |
| :--- | :--- | :--- | :--- | :--- |
| `chunk_symbols` Recall@5 | `0.2962` | `0.2147` | `-0.0815` | Adding entry metadata currently hurts the honest fused retrieval headline |
| `chunk_symbols` MRR | `0.5120` | `0.4969` | `-0.0151` | Top-ranked hits also get slightly worse |
| `expanded_fqns` Recall@5 | `0.2140` | `0.2128` | `-0.0012` | Heuristic-expanded view is effectively flat |
| `expanded_fqns` MRR | `0.4521` | `0.4334` | `-0.0187` | No diagnostic upside yet |

### `chunk_symbols` Source-Level Delta

| Source | `question_only` Recall@5 / MRR | `question_plus_entry` Recall@5 / MRR | Delta | Takeaway |
| :--- | :--- | :--- | :--- | :--- |
| BM25 | `0.1910 / 0.4143` | `0.1955 / 0.3675` | `+0.0045 / -0.0468` | Recall is flat; ranking quality drops |
| Semantic | `0.1506 / 0.3131` | `0.1402 / 0.2942` | `-0.0104 / -0.0189` | Entry metadata makes semantic retrieval slightly worse |
| Graph | `0.2823 / 0.5100` | `0.3272 / 0.5714` | `+0.0449 / +0.0614` | Graph-only improves when `entry_file` is available |
| Fused | `0.2962 / 0.5120` | `0.2147 / 0.4969` | `-0.0815 / -0.0151` | Fusion currently amplifies the noisy part of entry metadata |

### Type D Check

- Fused `chunk_symbols` Type D Recall@5 stays at `0.0000` in both query modes.
- Type D fused `chunk_symbols` MRR moves from `0.0000` to `0.0635`, which is still far too weak to count as a real fix.
- In this draft, `question_plus_entry` is effectively `question + entry_file` because entry-symbol coverage is still `0 / 32`.

## Single-Source Breakdown

### `chunk_symbols`

| Source | Recall@5 | MRR |
| :--- | :--- | :--- |
| BM25 | `0.1910` | `0.4143` |
| Semantic | `0.1506` | `0.3131` |
| Graph | `0.2823` | `0.5100` |
| Fused | `0.2962` | `0.5120` |

### `expanded_fqns`

| Source | Recall@5 | MRR |
| :--- | :--- | :--- |
| BM25 | `0.2373` | `0.4668` |
| Semantic | `0.1694` | `0.4108` |
| Graph | `0.2089` | `0.4293` |
| Fused | `0.2140` | `0.4521` |

## Failure-Type Snapshot

### Fused `chunk_symbols`

| Failure Type | Recall@5 | MRR | Cases |
| :--- | :--- | :--- | :--- |
| Type A | `0.5938` | `0.7581` | `4` |
| Type B | `0.1542` | `0.3542` | `8` |
| Type C | `0.6000` | `0.3204` | `5` |
| Type D | `0.0000` | `0.0000` | `2` |
| Type E | `0.2208` | `0.6859` | `13` |

### Fused `expanded_fqns`

| Failure Type | Recall@5 | MRR | Cases |
| :--- | :--- | :--- | :--- |
| Type A | `0.2875` | `0.4629` | `4` |
| Type B | `0.1792` | `0.3591` | `8` |
| Type C | `0.1000` | `0.2268` | `5` |
| Type D | `0.1667` | `0.1714` | `2` |
| Type E | `0.2639` | `0.6359` | `13` |

## What This Round Actually Shows

- The current prototype can now run a real retrieval-only evaluation on the `32`-case round4 draft instead of being blocked on the old `12`-case legacy file.
- Graph retrieval is the strongest single source on the honest `chunk_symbols` metric.
- Three-way fusion does improve on graph-only, but the margin is still small. This means the current fusion stack is helping, but not yet decisively.
- Adding `entry_file` through `question_plus_entry` currently makes fused retrieval worse instead of better. That means entry metadata is not a free boost; right now it behaves more like a noisy feature than a stable gain.
- Type D remains the weakest area on the honest retrieval view. The current prototype is still not good at namespace-confusion cases.
- Type A and Type C are currently the easiest failure types for the retrieval stack to support.

## Current Limits

- This is still a `draft eval` report, not a formal benchmark.
- The dataset is `32`, not `50`, so the result is directional rather than final.
- `schema_v2` gold uses the union of `direct_deps / indirect_deps / implicit_deps`; this is broader than a single-target answer metric.
- `question_plus_entry` is currently dominated by `entry_file` because the draft has `0 / 32` entry-symbol coverage.
- `question_only` is intentionally stricter than `question_plus_entry`, but both runs are still retrieval-only and do not yet include generation-side evaluation.
- `expanded_fqns` should not be quoted as the main retrieval number in external summaries.

## Next Recommended Moves

1. Keep `question_only` as the default retrieval headline and regression target until a richer entry-metadata scheme proves it helps.
2. Treat `question_plus_entry` as a diagnostic mode only; do not silently switch the prototype default to it.
3. Keep `chunk_symbols` as the primary metric and treat `expanded_fqns` as a secondary diagnostic view only.
4. Use the weakest slices, especially `Type D`, to drive the next batch of eval candidate design and bad-case analysis.
5. Once the draft pool is closer to `50`, freeze a cleaner retrieval report for the formal benchmark track.
