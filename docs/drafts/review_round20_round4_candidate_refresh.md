# Round 20 Candidate Refresh: Round4 RAG Follow-Up

## Scope

This pass consolidates four inputs into one narrower decision memo:

- the current high-value round4 candidate pool
- Boyle's targeted candidate mining
- Einstein's strict challenge pass
- Nietzsche's Type D / namespace-confusion mining

This memo does **not** promote anything directly into the formal eval pool.
Its purpose is to decide what is worth rewriting next and what should be parked or dropped.

## Retrieval Signal That Motivates This Pass

- On the current `32`-case round4 draft, fused honest retrieval (`chunk_symbols`) is still the main metric.
- `question_only` remains the correct default headline: `Recall@5 = 0.2962`, `MRR = 0.5120`.
- `question_plus_entry` is not helping yet: fused `chunk_symbols` falls to `Recall@5 = 0.2147`, `MRR = 0.4969`.
- Type D remains the weakest slice; fused `chunk_symbols` Type D Recall@5 is still `0.0000` in both query modes.

Working implication:

- do **not** try to hide Type D weakness by adding entry metadata
- keep pushing genuine namespace-confusion and resolution-path cases

## Executive Decision

Verdict for this batch: `rewrite_two / park_or_reject_three / accept_two_new_type_d / reject_two_new_type_d`

The current best next drafting direction is:

1. keep the `lpmerge` merge-semantics material, but rewrite it into a smaller and cleaner single-target question
2. keep the quorum delayed-route rewrite material, but rewrite all runtime gates and tighten gold closure
3. move only the two strict-review survivors from the new Type D batch into the next manual drafting queue

## Boyle Batch After Strict Challenge

### Keep But Rewrite

1. `lpmerge` preserving route values against explicit `None`
   - Status: `revise`
   - Why it survives:
     - single mechanism
     - real namespace-confusion behavior
     - useful for the weakest retrieval slice
   - Required rewrite:
     - ask only about the merge semantic
     - avoid helper-name giveaway wording
     - keep gold centered on the true helper implementation, not on route-side noise
   - Safe closure target:
     - direct: `celery.utils.collections.lpmerge`
     - indirect: `celery.app.routes.Router.route`

2. quorum delayed-route rewrite in `Celery.send_task`
   - Status: `revise`
   - Why it survives:
     - broker-specific and high-value
     - real behavior gate that models often flatten incorrectly
   - Required rewrite:
     - spell out the full runtime gates
     - do not paraphrase runtime checks as product-language claims
     - anchor the answer to the actual rewrite point inside `Celery.send_task`
   - Safe closure target:
     - direct: `celery.app.base.Celery.send_task`
     - indirect: delayed-delivery gate helpers only if the final schema draft truly needs them

### Reject Or Park

1. `worker_acks_late_failure_branch`
   - Status: `reject`
   - Reason:
     - too close to the already parked `celery_hard_021`
     - mixes decision point and execution point
     - closure gets dirty very quickly

2. `retry=True` / original function `disconnect`
   - Status: `reject`
   - Reason:
     - overlaps too heavily with existing few-shot `D04`
     - gold is not cleanly unique once `Signal.connect` and lookup-key generation are both involved

3. `PersistentScheduler.merge_inplace` startup merge point
   - Status: `reject`
   - Reason:
     - too close to `celery_hard_024`
     - easy to drift into a misleading "merge name means behavior" question

## New Type D Batch From Nietzsche After Strict Challenge

### Accepted

1. `expand_router_string` old-style router materialization
   - Status: `accept`
   - Why it survives:
     - gold `celery.app.routes.expand_router_string` is stable and unique
     - the string-path namespace ambiguity is real, not synthetic
     - overlap risk with existing eval / few-shot material looks low
   - Safe closure target:
     - direct: `celery.app.routes.expand_router_string`
     - indirect: `celery.app.routes.prepare`, `celery.app.routes.Router.query_router`

2. `MapRoute.__call__` exact key beating glob / regex
   - Status: `accept`
   - Why it survives:
     - single decision point
     - gold `celery.app.routes.MapRoute.__call__` is stable
     - exact-key versus pattern namespace priority is a real Type D behavior boundary
   - Safe closure target:
     - direct: `celery.app.routes.MapRoute.__call__`
     - indirect: `celery.app.routes.MapRoute.__init__`

### Keep But Rewrite

1. `lpmerge` route merge semantics
   - Status: `revise`
   - Updated rewrite rule after the second strict challenge:
     - drop `Router.expand_destination` from closure
     - keep the question focused on left-precedent merge semantics
     - ask the behavior question first, not the helper name directly

### Rejected

1. `Signature.from_dict` subtype dispatch
   - Status: `reject`
   - Reason:
     - dispatch point and final returned subtype are too easy to conflate
     - `subtask_type` dominates the behavior, so the `task` part of the prompt becomes misleading noise
     - overlap risk with existing `Signature.from_dict`-based materials is too high

2. `_unpickle_task_v2` import-vs-registry resolution
   - Status: `reject`
   - Reason:
     - the gold is unique but too shallow
     - the function body already exposes the answer too directly, so the item is too guessable to spend a scarce Type D slot on

## Next Drafting Queue

Use this order for the next manual drafting pass:

1. rewrite the `lpmerge` candidate into a strict single-target Type D item
2. rewrite the quorum delayed-route candidate with complete gates
3. draft a formal `expand_router_string` Type D item
4. draft a formal `MapRoute.__call__` Type D item
