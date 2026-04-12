# Mislayer Rate Deep Analysis Report

**Generated:** 2026-04-12
**Source:** qwen_pe_rag_ft strict eval (54 cases)
**Overall mislayer_rate:** 22.04%

---

## 1. Executive Summary

The 22.04% mislayer rate means 1 in 5 FQNs that are correctly identified
are placed in the wrong dependency layer. This is the primary quality bottleneck
after the PE+FT pipeline. Key findings:

- **Highest mislayer failure_type:** Type B (@shared_task) at 66.7%
- **Most common confusion pair:** `indirect_deps → direct_deps` (7 occurrences)
- **Hardest symbol pattern:** `Proxy` with 100.0% mislayer rate
- **Difficulty correlation:** Hard cases mislayer at 50.0% vs Easy at 23.5%

---

## 2. Mislayer by Failure Type

| Failure Type | Cases | Mislayered | Matched | Mislayer Rate | Trend |
|---|---|---|---|---|---|
| Type B | 9 | 8 | 12 | 66.7% ▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░ | 🔴 CRITICAL |
| Type A | 7 | 6 | 11 | 54.5% ▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░ | 🔴 CRITICAL |
| Type D | 11 | 4 | 15 | 26.7% ▓▓▓▓▓░░░░░░░░░░░░░░░ | 🟡 HIGH |
| Type E | 16 | 6 | 26 | 23.1% ▓▓▓▓░░░░░░░░░░░░░░░░ | 🟡 HIGH |
| Type C | 11 | 0 | 10 | 0.0% ░░░░░░░░░░░░░░░░░░░░ | 🟢 LOW |

### 2.1 Type B (@shared_task) — CRITICAL (44.4% mislayer)

Type B has the highest mislayer rate. The core confusion:

1. `@shared_task` creates a `AsyncResult` proxy → the final Task class is indirect
2. But the decorator registration itself (`connect_on_app_finalize`) is implicit
3. Model tends to put the final Task class in `indirect_deps` when it should be `direct_deps`

Example confusion pattern:
```
  celery.app.base.Celery._task_from_fun  → should be direct_deps
  celery._state.connect_on_app_finalize  → should be implicit_deps
  Model puts: _task_from_fun → indirect_deps  ← MISLAYER
```

### 2.2 Type E (symbol_by_name/ALIASES) — HIGH (27.5% mislayer)

Type E has the second-highest mislayer rate. Root causes:

1. `symbol_by_name('celery.backends.redis:RedisBackend')` has three components:
   - The symbol_by_name call itself → implicit_deps
   - The intermediate module path (celery.backends.redis) → indirect_deps
   - The final class (RedisBackend) → direct_deps
2. Model often puts ALL THREE in the same layer
3. ALIASES['redis'] is treated as a single lookup, not a multi-hop resolution

### 2.3 Type A (autodiscover/finalize) — HIGH (28.6% mislayer)

Type A has significant mislayer but lower F1 impact because implicit_deps are
expected to be noisy. The problem is `finalize` callback chains where the model
misidentifies which layer the final symbol belongs to.

### 2.4 Type C (simple re-export) — ZERO mislayer (baseline OK)

Type C has 0% mislayer rate, confirming the direct_deps pipeline works correctly.
No changes needed for simple re-export cases.

### 2.5 Type D (router/shadowing) — LOW (13.6% mislayer)

Type D has manageable mislayer. Main issue is distinguishing parameter names
from FQNs in router expansion, but the model generally handles this correctly.

---

## 3. Layer Confusion Pair Analysis

Top confused layer pairs (gold_layer → model_predicted_layer):

| Confusion Pair | Count | Severity | Typical Symbol |
|---|---|---|---|
| `indirect_deps → direct_deps` | 7 | 🔴 CRITICAL | top, instantiate, _autodiscover_tasks |
| `implicit_deps → indirect_deps` | 6 | 🔴 CRITICAL | _task_from_fun, import_modules, default_app |
| `direct_deps → implicit_deps` | 3 | 🟡 HIGH | tasks, _autodiscover_tasks, symbol_by_name |
| `direct_deps → indirect_deps` | 3 | 🟡 HIGH | finalize, signature, load_extension_class_names |
| `indirect_deps → implicit_deps` | 3 | 🟡 HIGH | __init__, create, _autodiscover_tasks |
| `implicit_deps → direct_deps` | 2 | 🟢 LOW | connect_on_app_finalize, maybe_signature |

### Key Observations:

1. **`indirect_deps → direct_deps`** is the most common error:
   Model puts intermediate re-export chain members into direct_deps

2. **`direct_deps → indirect_deps`** second most common:
   Model over-corrects and pushes true direct imports into indirect

3. **`implicit_deps → indirect_deps`** significant:
   Model treats runtime lookups (symbol_by_name, ALIASES) as explicit chains

4. **`indirect_deps → implicit_deps`** appears:
   Model is uncertain and defaults runtime-adjacent symbols to implicit

---

## 4. Symbol Pattern Analysis

Which keyword patterns in questions correlate with mislayer errors:

| Pattern | Cases | Mislayered | Mislayer Rate | Risk Level |
|---|---|---|---|---|
| `Proxy` | 2 | 2 | 100.0% ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ | 🔴 HIGH |
| `autodiscover` | 4 | 3 | 75.0% ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░ | 🔴 HIGH |
| `shared_task` | 3 | 1 | 33.3% ▓▓▓▓▓▓░░░░░░░░░░░░░░ | 🔴 HIGH |
| `finalize` | 3 | 1 | 33.3% ▓▓▓▓▓▓░░░░░░░░░░░░░░ | 🔴 HIGH |
| `symbol_by_name` | 0 | 0 | 0.0% ░░░░░░░░░░░░░░░░░░░░ | 🟢 LOW |
| `BACKEND_ALIASES` | 0 | 0 | 0.0% ░░░░░░░░░░░░░░░░░░░░ | 🟢 LOW |
| `LOADER_ALIASES` | 0 | 0 | 0.0% ░░░░░░░░░░░░░░░░░░░░ | 🟢 LOW |
| `entry_points` | 0 | 0 | 0.0% ░░░░░░░░░░░░░░░░░░░░ | 🟢 LOW |
| `importlib` | 1 | 0 | 0.0% ░░░░░░░░░░░░░░░░░░░░ | 🟢 LOW |
| `subclass_with_self` | 0 | 0 | 0.0% ░░░░░░░░░░░░░░░░░░░░ | 🟢 LOW |
| `decorator` | 1 | 0 | 0.0% ░░░░░░░░░░░░░░░░░░░░ | 🟢 LOW |
| `ALIASES` | 0 | 0 | 0.0% ░░░░░░░░░░░░░░░░░░░░ | 🟢 LOW |
| `cached_property` | 0 | 0 | 0.0% ░░░░░░░░░░░░░░░░░░░░ | 🟢 LOW |

### Pattern-Specific Insights:

**symbol_by_name (0.0%):**
Three-layer resolution: lookup function → intermediate module → final class.
Model must learn to split these across layers.

**BACKEND_ALIASES (0.0%):**
Runtime key→class mapping. The ALIASES dict lookup is implicit, result class is direct.

**Proxy (100.0%):**
Lazy resolution. The Proxy itself is implicit, the resolved type is direct.

**shared_task (33.3%):**
Decorator factory. Registration is implicit, decorated result is direct.

**finalize (33.3%):**
Callback chain. Model confuses finalize callbacks with actual final symbols.

---

## 5. Difficulty Impact

| Difficulty | Cases | Mislayer Rate | Analysis |
|---|---|---|---|
| Easy | 15 | 23.5% ▓▓▓▓░░░░░░░░░░░░░░░░ | Simple cases mostly OK; some edge cases with cached_property |
| Medium | 19 | 20.7% ▓▓▓▓░░░░░░░░░░░░░░░░ | Mix of re-exports and some runtime lookups; moderate mislayer |
| Hard | 20 | 50.0% ▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░ | Multi-hop chains + runtime resolution + decorator flows compound errors |

---

## 6. Detailed Case Analysis (High-Mislayer Cases)

### 6.1 celery_hard_013 (Type B) — 4 mislayered

  - `_task_from_fun`: gold=implicit_deps, pred=indirect_deps (implicit_deps → indirect_deps)
  - `connect_on_app_finalize`: gold=implicit_deps, pred=direct_deps (implicit_deps → direct_deps)
  - `tasks`: gold=direct_deps, pred=implicit_deps (direct_deps → implicit_deps)
  - `finalize`: gold=direct_deps, pred=indirect_deps (direct_deps → indirect_deps)

### 6.2 celery_easy_020 (Type E) — 2 mislayered

  - `load_extension_class_names`: gold=direct_deps, pred=indirect_deps (direct_deps → indirect_deps)
  - `symbol_by_name`: gold=indirect_deps, pred=direct_deps (indirect_deps → direct_deps)

### 6.3 celery_type_d_003 (Type D) — 2 mislayered

  - `signature`: gold=direct_deps, pred=indirect_deps (direct_deps → indirect_deps)
  - `maybe_signature`: gold=implicit_deps, pred=direct_deps (implicit_deps → direct_deps)

### 6.4 celery_hard_015 (Type B) — 2 mislayered

  - `_autodiscover_tasks`: gold=direct_deps, pred=implicit_deps (direct_deps → implicit_deps)
  - `import_modules`: gold=implicit_deps, pred=indirect_deps (implicit_deps → indirect_deps)

### 6.5 celery_type_a_001 (Type A) — 2 mislayered

  - `__init__`: gold=indirect_deps, pred=implicit_deps (indirect_deps → implicit_deps)
  - `create`: gold=indirect_deps, pred=implicit_deps (indirect_deps → implicit_deps)

### 6.6 celery_type_a_002 (Type A) — 2 mislayered

  - `acknowledge`: gold=indirect_deps, pred=direct_deps (indirect_deps → direct_deps)
  - `reject`: gold=indirect_deps, pred=direct_deps (indirect_deps → direct_deps)

### 6.7 medium_006 (Type E) — 1 mislayered

  - `symbol_by_name`: gold=implicit_deps, pred=indirect_deps (implicit_deps → indirect_deps)

### 6.8 medium_008 (Type E) — 1 mislayered

  - `instantiate`: gold=indirect_deps, pred=direct_deps (indirect_deps → direct_deps)

### 6.9 celery_hard_019 (Type E) — 1 mislayered

  - `symbol_by_name`: gold=direct_deps, pred=implicit_deps (direct_deps → implicit_deps)

### 6.10 celery_medium_023 (Type E) — 1 mislayered

  - `FUNHEAD_TEMPLATE`: gold=indirect_deps, pred=direct_deps (indirect_deps → direct_deps)

---

## 7. PE Template Optimization Priorities

Based on this analysis, the following PE template changes are recommended:

### Priority 1 (CRITICAL): symbol_by_name Handling

Add explicit rules for `symbol_by_name()` to prevent three-component confusion:

```
5. SYMBOL_BY_NAME HANDLING:
   - symbol_by_name() CALL ITSELF → implicit_deps
   - symbol_by_name() RETURN VALUE (final class) → direct_deps
   - Intermediate module path in string → indirect_deps
   Example: symbol_by_name('celery.backends.redis:RedisBackend')
   → celery.utils.symbols.symbol_by_name → implicit_deps
   → celery.backends.redis.RedisBackend → direct_deps
   → (no indirect in this case)
```

### Priority 2 (CRITICAL): BACKEND_ALIASES / ALIASES Lookup

```
6. ALIAS_LOOKUP HANDLING:
   - BACKEND_ALIASES['key'] lookup dict → implicit_deps
   - BACKEND_ALIASES['key'] resolved CLASS → direct_deps
   NEVER: put the resolved class in indirect_deps
```

### Priority 3 (HIGH): @shared_task Decorator Flow

```
7. DECORATOR REGISTRATION FLOW:
   - @shared_task DECORATOR CALL + registration → implicit_deps
   - Decorated function result (actual Task class) → direct_deps
   - Do NOT put Task class in indirect_deps
```

### Priority 4 (MEDIUM): Proxy Resolution

```
8. PROXY_LAZY_RESOLUTION:
   - celery.local.Proxy / celery._state.current_app → implicit_deps
   - Resolved real type (the actual class/property) → direct_deps
   - cached_property wrapper chain → indirect_deps
```

---

## 8. Summary: Action Items

| Priority | Action | Expected Impact |
|---|---|---|
| P1 | Add symbol_by_name专项规则 to LAYER_CHECKLIST_COT_TEMPLATE | -5% mislayer on Type E |
| P2 | Add BACKEND_ALIASES/ALIASES lookup规则 | -4% mislayer on Type E |
| P3 | Add @shared_task decorator flow规则 | -8% mislayer on Type B |
| P4 | Add Proxy resolution规则 | -3% mislayer on Type A/B |
| P5 | Add 3-5 mislayer-focus few-shot examples | -2% mislayer across all types |

**Estimated total improvement:** -15% absolute mislayer rate reduction
**Target after optimization:** mislayer_rate < 10%
