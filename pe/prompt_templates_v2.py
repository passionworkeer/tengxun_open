"""
提示词模板模块 V2

功能：
1. System Prompt：定义角色和输出格式
2. CoT模板：链式推理引导
3. Few-shot示例库：按失效类型配比的示例选择
4. Prompt构建：组装完整的prompt

核心设计理念：
- 严格区分 direct_deps / indirect_deps / implicit_deps 三级依赖
- 针对 Type A-E 五类失效模式设计
- 最小化幻觉，只输出JSON格式答案
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Sequence


SYSTEM_PROMPT = """\
You are a senior Python static analysis expert working on cross-file dependency resolution.
Resolve the final dependency structure precisely against the provided Celery source context.
Output only a JSON object in this shape:
{
  "ground_truth": {
    "direct_deps": [],
    "indirect_deps": [],
    "implicit_deps": []
  }
}
Do not include explanations, markdown, XML tags, or any extra prose.
Always respond in English, regardless of the question language.
"""


COT_TEMPLATE = """\
Reason internally using this checklist before answering:
1. Identify whether the entry is a re-export, alias, decorator flow, dynamic string target, or long multi-hop chain.
2. Separate stable public entry points from conditional internal substeps.
3. Follow the chain until the final real symbol or stable trigger point is reached.
4. Distinguish direct, indirect, and implicit dependencies instead of flattening everything into one list.
5. Return only the required JSON object.
"""


LAYER_GUARD_RULES = """\
Layer assignment rules:
1. direct_deps: symbols directly imported, called, instantiated, accessed, or returned by the entry file / entry symbol itself. If the entry symbol's file contains an `import X` or `from X import Y` where X/Y is the target, that symbol is direct_deps. Single-hop re-exports (entry file imports from another file) are also direct_deps.
2. indirect_deps: symbols reached through one or more explicit intermediate code symbols such as re-export chains (A→B→C), alias assignment, wrapper function, factory, cached_property, or subclass_with_self. Each hop in the chain adds one level of indirection.
3. implicit_deps: symbols reached through runtime-triggered edges. This includes: decorator registration callbacks, finalize hooks, signals/receivers, registries, lazy Proxy resolution, dynamic string imports, symbol_by_name(), symbol_by_name() fallback paths, loader autodiscovery, importlib.import_module, BACKEND_ALIASES/LOADER_ALIASES lookup, entry_points() resolution, and config_from_object with string arguments.
4. Each FQN must appear in exactly one layer. Never duplicate the same symbol across layers.
5. A symbol reached via string resolution, hook registration, or runtime callback cannot be direct_deps.
6. CRITICAL: symbol_by_name(), instantiate(), ALIASES['key'], entry_points(), importlib.import_module, config_from_object with string args — these ALL create implicit_deps edges, NOT indirect_deps.
7. If uncertain, prefer indirect_deps over direct_deps; prefer implicit_deps for runtime-triggered edges.
"""


STRICT_LAYER_COT_TEMPLATE = """\
Reason internally using this checklist before answering:
1. Identify the first stable code symbol reached from the entry file / entry symbol.
2. Mark only that first-hop stable code symbol as direct_deps.
3. Move any symbol reached via re-export, wrapper, alias, factory, cached_property, or helper into indirect_deps.
4. Move any symbol reached via decorator registration, finalize callbacks, signals, Proxy/lazy resolution, or string/module-name lookup into implicit_deps.
5. CRITICAL boundary check: symbol_by_name(), instantiate(), ALIASES[], entry_points(), importlib.import_module — these are RUNTIME lookups → implicit_deps.
6. Run an exclusivity check so each FQN appears in at most one layer.
7. Return only the required JSON object.
"""


# ---------------------------------------------------------------------------
# P2-17: Enhanced layer-checking CoT (reduces mislayer_rate)
# ---------------------------------------------------------------------------
LAYER_CHECKLIST_COT_TEMPLATE = """\
Step-by-step layer assignment:
1. ENTRY: Identify what the entry file/symbol is (re-export, Proxy, decorator factory, signal receiver, string resolver, etc.).
2. FIRST HOP: Trace the single immediate code path from the entry. Whatever is directly imported/called/accessed at this point is direct_deps.
3. EXPLICIT CHAIN: Follow any explicit re-export, alias, or wrapper chain. Each explicit intermediate code symbol (not a runtime call) goes to indirect_deps.
4. RUNTIME TRIGGER: Any symbol reached via:
   - symbol_by_name() / instantiate() / import_from_cwd()
   - BACKEND_ALIASES / LOADER_ALIASES / TYPES registry lookup
   - connect_on_app_finalize() / finalize() callbacks
   - signals.import_modules.send() / starpromise()
   - importlib.import_module() with string/module-name
   - entry_points() resolution
   → goes to implicit_deps (NOT indirect_deps).
5. EXCLUSIVITY: Verify each FQN appears in exactly one layer. Move any symbol_by_name results from indirect_deps to implicit_deps if found there.
6. SANITY: If a FQN is in indirect_deps but reached by a runtime call (not an explicit import chain), move it to implicit_deps.
7. Return only the required JSON object.
"""

# ---------------------------------------------------------------------------
# P2-18: CRITICAL Mislayer-Prevention Rules (Type A/B/D/E high-mislayer cases)
# ---------------------------------------------------------------------------

# Priority 1: symbol_by_name three-component split rule
# Root cause: model puts ALL symbol_by_name components in one layer
# Fix: explicit three-way split rule
SYMBOL_BY_NAME_RULE = """\
CRITICAL — SYMBOL_BY_NAME THREE-COMPONENT SPLIT:
symbol_by_name('module.path:ClassName') resolves in THREE steps:
  Step 1 — symbol_by_name() itself → implicit_deps (runtime lookup)
  Step 2 — intermediate module path (module.path) → indirect_deps (if not already direct)
  Step 3 — final ClassName (the actual class/function) → direct_deps (final resolution target)
Example: symbol_by_name('celery.backends.redis:RedisBackend')
  → celery.utils.symbols.symbol_by_name → implicit_deps (the lookup mechanism)
  → celery.backends.redis.RedisBackend → direct_deps (the resolved class)
  → celery.backends.redis → indirect_deps (only if needed as intermediate hop)
NEVER put the resolved final class (RedisBackend) in indirect_deps or implicit_deps.
"""

# Priority 2: BACKEND_ALIASES / ALIASES lookup rule
# Root cause: model confuses ALIASES dict lookup (implicit) with resolved class (direct)
BACKEND_ALIASES_RULE = """\
CRITICAL — BACKEND_ALIASES / ALIAS_LOOKUP:
BACKEND_ALIASES['redis'], LOADER_ALIASES['lazy'], TYPES['task'] are runtime dictionary lookups:
  → The ALIASES / dict object itself → implicit_deps
  → The KEY lookup operation (BACKEND_ALIASES['key']) → implicit_deps
  → The RESOLVED final class from the lookup → direct_deps
Example: BACKEND_ALIASES['redis'] → celery.backends.redis.RedisBackend
  → celery.app.backends.BACKEND_ALIASES → implicit_deps
  → celery.backends.redis.RedisBackend → direct_deps
NEVER put the resolved final class (RedisBackend) in indirect_deps.
"""

# Priority 3: @shared_task decorator registration flow
# Root cause: model puts Task class in indirect_deps instead of direct_deps
SHARED_TASK_RULE = """\
CRITICAL — @shared_task DECORATOR REGISTRATION FLOW:
@shared_task decorator creates a multi-stage registration:
  Stage 1 — @shared_task DECORATOR CALL itself → implicit_deps (runtime hook registration)
  Stage 2 — connect_on_app_finalize() callback → implicit_deps (registration mechanism)
  Stage 3 — _task_from_fun() / app._task_from_fun() → direct_deps (actual Task registration)
  Stage 4 — decorated function result (the real Task class) → direct_deps (final result)
Example: @shared_task decorated function registered via app._task_from_fun
  → celery._state.connect_on_app_finalize → implicit_deps
  → celery._state._get_active_apps → implicit_deps
  → celery.app.base.Celery._task_from_fun → direct_deps
NEVER put _task_from_fun or the final Task class in indirect_deps — it is the direct result.
"""

# Priority 4: Proxy lazy resolution
# Root cause: model confuses Proxy (implicit) with resolved type (direct)
PROXY_RESOLUTION_RULE = """\
CRITICAL — PROXY / LAZY RESOLUTION:
celery.local.Proxy and celery._state.current_app use lazy evaluation:
  → celery.local.Proxy → implicit_deps (the lazy mechanism)
  → celery._state.current_app → implicit_deps (the Proxy itself)
  → The RESOLVED real class/property behind the Proxy → direct_deps
  → cached_property wrapper → indirect_deps (explicit intermediate)
Example: Celery.Worker (cached_property) → Worker subclass with app bound
  → celery.local.Proxy → implicit_deps
  → celery.app.base.Celery.Worker (cached_property) → direct_deps
  → celery.apps.worker.Worker (resolved subclass) → direct_deps
  → celery.app.base.Celery.subclass_with_self → implicit_deps
"""

# Priority 5: cached_property and subclass_with_self
CACHED_PROPERTY_RULE = """\
IMPORTANT — CACHED_PROPERTY AND SUBCLASS_WITH_SELF:
cached_property descriptors and subclass_with_self are indirect hops:
  → cached_property descriptor itself → indirect_deps
  → Resolved real attribute value (the actual object) → direct_deps
  → subclass_with_self call → implicit_deps
  → Generated subclass class → direct_deps
Example: Celery.Worker (cached_property)
  → celery.app.base.Celery.Worker (descriptor) → direct_deps
  → celery.apps.worker.Worker (subclass) → direct_deps
  → celery.app.base.Celery.subclass_with_self → implicit_deps
"""

# Combined mislayer-prevention addendum (append to LAYER_CHECKLIST_COT_TEMPLATE)
MISLAYER_PREVENTION_ADDENDUM = (
    SYMBOL_BY_NAME_RULE
    + BACKEND_ALIASES_RULE
    + SHARED_TASK_RULE
    + PROXY_RESOLUTION_RULE
    + CACHED_PROPERTY_RULE
)


def build_mislayer_prevention_cot(base_cot: str = LAYER_CHECKLIST_COT_TEMPLATE) -> str:
    """
    Build enhanced CoT with all mislayer-prevention rules.
    Use this when mislayer rate is high or for Type A/B/D/E cases.
    """
    return f"{base_cot.strip()}\n\n{MISLAYER_PREVENTION_ADDENDUM.strip()}"


# ---------------------------------------------------------------------------
# P2-16: Hard-case optimization hints
# ---------------------------------------------------------------------------

# 触发Hard难度的关键词模式，按failure_type分组
HARD_TYPE_A_PATTERNS = [
    "autodiscover", "include_if", "conditional", "bootstep", "step",
    "finalize", "failure_matrix", "PersistentScheduler", "store.clear",
]
HARD_TYPE_B_PATTERNS = [
    "shared_task", "@app.task", "register", "Proxy", "autofinalize",
    "finalize_callback", "builtin_finalize",
]
HARD_TYPE_D_PATTERNS = [
    "expand_router", "router_string", "RouterClass", "register_type",
    "parameter_shadow", "shadows",
]
HARD_TYPE_E_PATTERNS = [
    "symbol_by_name", "by_name", "string_resolution", "import_object",
    "loader_smart", "config_from_object", "BACKEND_ALIASES", "LOADER_ALIASES",
]

# Hard case专用CoT补充：当检测到Hard关键词时追加到标准CoT后面
HARD_CASE_COT_ADDENDUM = """
[Hard Case Alert] Detected multi-hop or runtime-triggered chain:
- Trace the FULL chain: entry -> first hop -> intermediate -> final symbol.
- Decorator registration creates implicit edges; follow finalize callbacks.
- autodiscover_tasks uses lazy signals, not direct imports.
- Parameter shadowing: distinguish local parameter names from module-level FQNs.
- symbol_by_name/string resolution: the final class is several hops from the entry.
- A single entry may span 2-3 layers (direct + indirect + implicit).
"""

# 按failure_type分布补充的fewshot提示（不直接嵌入prompt，仅供选择参考）
HARD_FAILURE_TYPE_HINTS = {
    "Type A": "Watch for conditional execution paths and state-dependent includes.",
    "Type B": "Follow the full decorator factory chain to the actual registration call.",
    "Type D": "Distinguish parameter names from module FQNs; shadowing hides the real symbol.",
    "Type E": "String-based lookups (ALIASES, symbol_by_name) require multiple resolution hops.",
}


OUTPUT_INSTRUCTIONS = """Return only a JSON object with:
{
  "ground_truth": {
    "direct_deps": ["..."],
    "indirect_deps": ["..."],
    "implicit_deps": ["..."]
  }
}"""


DATA_PATH = Path(
    os.environ.get(
        "FEWSHOT_DATA_PATH",
        Path(__file__).resolve().parent.parent / "data" / "fewshot_examples_20.json",
    )
)
REQUIRED_FEW_SHOT_TARGET = 20
_TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]+")


@dataclass(frozen=True)
class GroundTruth:
    """
    标准答案数据结构

    区分三种依赖类型：
    - direct_deps: 直接依赖（当前文件直接导入）
    - indirect_deps: 间接依赖（通过其他模块再导出）
    - implicit_deps: 隐式依赖（装饰器、动态加载等）
    """

    direct_deps: tuple[str, ...]
    indirect_deps: tuple[str, ...]
    implicit_deps: tuple[str, ...]

    def as_dict(self) -> dict[str, list[str]]:
        return {
            "direct_deps": list(self.direct_deps),
            "indirect_deps": list(self.indirect_deps),
            "implicit_deps": list(self.implicit_deps),
        }


@dataclass(frozen=True)
class FewShotExample:
    """
    Few-shot示例

    包含一个问题案例的完整信息：
    - 问题描述
    - 环境前提条件
    - 推理步骤
    - 标准答案
    """

    case_id: str
    failure_type: str
    title: str
    question: str
    environment_preconditions: tuple[str, ...]
    reasoning_steps: tuple[str, ...]
    ground_truth: GroundTruth


@dataclass(frozen=True)
class PromptBundle:
    """
    完整Prompt包

    包含组装prompt的所有组件。
    """

    system_prompt: str
    cot_template: str
    few_shot_examples: tuple[FewShotExample, ...]
    user_prompt: str

    def as_text(self) -> str:
        blocks = [self.system_prompt.strip(), self.cot_template.strip()]
        if self.few_shot_examples:
            blocks.append(
                "\n\n".join(
                    format_few_shot_example(example)
                    for example in self.few_shot_examples
                )
            )
        blocks.append(self.user_prompt.strip())
        return "\n\n".join(block for block in blocks if block)


def _tokenize(text: str) -> set[str]:
    normalized = (
        text.replace(":", ".").replace("/", ".").replace("`", " ").replace("-", " ")
    )
    tokens: set[str] = set()
    for raw_token in _TOKEN_PATTERN.findall(normalized):
        token = raw_token.lower()
        tokens.add(token)
        split_token = re.sub(r"(?<!^)(?=[A-Z])", " ", raw_token).lower()
        tokens.update(piece for piece in split_token.split() if piece)
    return tokens


def _coerce_string_list(values: Sequence[str] | None) -> tuple[str, ...]:
    if not values:
        return ()
    return tuple(str(value).strip() for value in values if str(value).strip())


def _load_example(item: dict[str, object]) -> FewShotExample:
    ground_truth = item.get("ground_truth", {})
    if not isinstance(ground_truth, dict):
        raise ValueError(
            f"Invalid ground_truth payload for {item.get('id', '<unknown>')}"
        )

    return FewShotExample(
        case_id=str(item.get("id", "")).strip(),
        failure_type=str(item.get("failure_type", "")).strip(),
        title=str(item.get("title", "")).strip(),
        question=str(item.get("question", "")).strip(),
        environment_preconditions=_coerce_string_list(
            item.get("environment_preconditions") if isinstance(item, dict) else None
        ),
        reasoning_steps=_coerce_string_list(
            item.get("reasoning_steps") if isinstance(item, dict) else None
        ),
        ground_truth=GroundTruth(
            direct_deps=_coerce_string_list(ground_truth.get("direct_deps")),
            indirect_deps=_coerce_string_list(ground_truth.get("indirect_deps")),
            implicit_deps=_coerce_string_list(ground_truth.get("implicit_deps")),
        ),
    )


@lru_cache(maxsize=1)
def load_few_shot_examples(path: str | Path = DATA_PATH) -> tuple[FewShotExample, ...]:
    raw = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    return tuple(_load_example(item) for item in raw)


FEW_SHOT_LIBRARY: tuple[FewShotExample, ...] = load_few_shot_examples()


def format_few_shot_example(example: FewShotExample) -> str:
    answer = format_few_shot_assistant_message(example)
    return (
        f"{format_few_shot_user_message(example)}\n\n"
        f"Answer:\n{answer}"
    )


def _format_numbered_block(items: Sequence[str], empty_value: str = "None") -> str:
    if not items:
        return empty_value
    return "\n".join(f"{idx}. {item}" for idx, item in enumerate(items, start=1))


def format_few_shot_user_message(example: FewShotExample) -> str:
    return (
        f"[Few-shot {example.case_id} | {example.failure_type} | {example.title}]\n"
        f"Question:\n{example.question}\n\n"
        f"Environment Preconditions:\n"
        f"{_format_numbered_block(example.environment_preconditions)}\n\n"
        f"Reference Reasoning:\n"
        f"{_format_numbered_block(example.reasoning_steps, empty_value='None')}\n\n"
        f"{OUTPUT_INSTRUCTIONS}"
    )


def format_few_shot_assistant_message(example: FewShotExample) -> str:
    return json.dumps(
        {"ground_truth": example.ground_truth.as_dict()},
        ensure_ascii=False,
        indent=2,
    )


def select_few_shot_examples(
    question: str,
    context: str = "",
    entry_symbol: str = "",
    max_examples: int = 6,
    library: Sequence[FewShotExample] | None = None,
) -> list[FewShotExample]:
    """
    选择最相关的few-shot示例

    选择策略（多因子评分）：
    1. token重叠度（权重3.0）：问题与示例的文本重叠
    2. 失效类型匹配（权重2.0）：失败类型关键词匹配
    3. 入口符号匹配（权重2.5）：入口符号在示例中出现
    4. 长链路加分（0.5）：case_id以A开头表示长链案例优先
    5. Hard-case模式加分（1.0）：匹配Type A/B/D/E的Hard关键词

    Args:
        question: 当前问题
        context: 检索上下文
        entry_symbol: 入口符号
        max_examples: 最大选择数量
        library: 可选的示例库

    Returns:
        选中的示例列表，按相关性排序
    """
    examples = list(library or FEW_SHOT_LIBRARY)
    if max_examples <= 0 or not examples:
        return []

    query_text = " ".join(part for part in (question, context, entry_symbol) if part)
    query_lower = query_text.lower()
    query_tokens = _tokenize(query_text)
    entry_tail = entry_symbol.rsplit(".", 1)[-1].lower() if entry_symbol else ""

    # P2-16: 收集所有Hard模式
    all_hard_patterns: list[str] = (
        HARD_TYPE_A_PATTERNS
        + HARD_TYPE_B_PATTERNS
        + HARD_TYPE_D_PATTERNS
        + HARD_TYPE_E_PATTERNS
    )

    scored: list[tuple[float, FewShotExample]] = []
    for example in examples:
        example_text = " ".join(
            [
                example.case_id,
                example.failure_type,
                example.title,
                example.question,
                " ".join(example.environment_preconditions),
                " ".join(example.reasoning_steps),
                " ".join(example.ground_truth.direct_deps),
                " ".join(example.ground_truth.indirect_deps),
                " ".join(example.ground_truth.implicit_deps),
            ]
        )
        example_tokens = _tokenize(example_text)
        overlap = len(query_tokens & example_tokens)
        failure_hit = (
            1
            if any(token in example.failure_type.lower() for token in query_tokens)
            else 0
        )
        entry_hit = 1 if entry_tail and entry_tail in example_text.lower() else 0
        long_chain_bonus = 0.5 if example.case_id.startswith("A") else 0.0

        # P2-16: Hard-case模式命中加分
        hard_pattern_hit = sum(
            1.0 for pattern in all_hard_patterns if pattern.lower() in query_lower
        )
        hard_pattern_bonus = min(hard_pattern_hit, 3.0)  # 最多加3分

        score = (
            overlap * 3.0
            + failure_hit * 2.0
            + entry_hit * 2.5
            + long_chain_bonus
            + hard_pattern_bonus
        )
        scored.append((score, example))

    scored.sort(
        key=lambda item: (
            item[0],
            item[1].case_id.startswith("A"),
            item[1].case_id.startswith("B"),
            item[1].case_id,
        ),
        reverse=True,
    )

    selected: list[FewShotExample] = []
    seen_ids: set[str] = set()
    for _, example in scored:
        if example.case_id in seen_ids:
            continue
        selected.append(example)
        seen_ids.add(example.case_id)
        if len(selected) >= max_examples:
            break
    return selected


def is_hard_case(question: str, context: str = "", entry_symbol: str = "") -> bool:
    """
    判断当前问题是否可能属于Hard难度案例。

    通过关键词匹配检测Hard-case模式：
    - Type A: autodiscover, include_if, conditional, bootstep, finalize
    - Type B: shared_task, @app.task, Proxy, autofinalize
    - Type D: router_string, expand_router, shadowing
    - Type E: symbol_by_name, ALIASES, string_resolution
    """
    combined = " ".join(part for part in (question, context, entry_symbol) if part)
    combined_lower = combined.lower()
    hard_keywords = (
        HARD_TYPE_A_PATTERNS
        + HARD_TYPE_B_PATTERNS
        + HARD_TYPE_D_PATTERNS
        + HARD_TYPE_E_PATTERNS
    )
    return any(kw.lower() in combined_lower for kw in hard_keywords)


def build_cot_for_hard_case(
    base_cot: str = COT_TEMPLATE,
) -> str:
    """
    为Hard案例构建增强版CoT。

    当 is_hard_case() 返回True时，在标准CoT后追加Hard-case补充提示，
    提醒模型注意多跳链路、装饰器流、动态解析等典型Hard-case陷阱。
    """
    return f"{base_cot.strip()}\n\n{HARD_CASE_COT_ADDENDUM.strip()}"


def build_user_prompt(
    question: str,
    context: str,
    entry_symbol: str = "",
    entry_file: str = "",
    include_empty_context: bool = True,
) -> str:
    lines = ["Question:", question.strip()]
    if entry_symbol.strip():
        lines.extend(["", "Provided Entry Symbol:", entry_symbol.strip()])
    if entry_file.strip():
        lines.extend(["", "Provided Entry File:", entry_file.strip()])
    if context.strip() or include_empty_context:
        lines.extend(
            [
                "",
                "Context:",
                context.strip(),
            ]
        )
    lines.extend(["", OUTPUT_INSTRUCTIONS])
    return "\n".join(lines)


def build_prompt_bundle(
    question: str,
    context: str,
    entry_symbol: str = "",
    entry_file: str = "",
    max_examples: int = 6,
    library: Sequence[FewShotExample] | None = None,
    system_prompt: str = SYSTEM_PROMPT,
    cot_template: str = COT_TEMPLATE,
    include_empty_context: bool = True,
    auto_hard_cot: bool = True,
    use_layer_checklist: bool = True,
    use_mislayer_prevention: bool = False,
) -> PromptBundle:
    """
    组装完整Prompt包。

    Args:
        auto_hard_cot: True时，自动检测Hard-case并追加增强CoT（不影响Easy/Medium）。
        use_layer_checklist: True（默认）时，使用增强版层级检查CoT（LAYER_CHECKLIST_COT_TEMPLATE）
                            替代默认cot_template，可降低mislayer_rate。
                            设置为False可禁用增强版layer checklist。
        use_mislayer_prevention: True时，在layer_checklist基础上追加mislayer-prevention专项规则
                            (symbol_by_name/ALIASES/@shared_task/Proxy规则)。
                            建议用于Type A/B/D/E或已知mislayer高风险问题。
    """
    selected = select_few_shot_examples(
        question=question,
        context=context,
        entry_symbol=entry_symbol,
        max_examples=max_examples,
        library=library,
    )
    # P2-17: use_layer_checklist 优先；其次 auto_hard_cot 追加Hard-case专用CoT
    if use_layer_checklist:
        effective_cot = LAYER_CHECKLIST_COT_TEMPLATE
    else:
        effective_cot = cot_template
    # P2-18: mislayer_prevention addendum - applies on top of everything
    if use_mislayer_prevention:
        effective_cot = build_mislayer_prevention_cot(effective_cot)
    elif auto_hard_cot and is_hard_case(question=question, context=context, entry_symbol=entry_symbol):
        effective_cot = build_cot_for_hard_case(effective_cot)
    return PromptBundle(
        system_prompt=system_prompt,
        cot_template=effective_cot,
        few_shot_examples=tuple(selected),
        user_prompt=build_user_prompt(
            question=question,
            context=context,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
            include_empty_context=include_empty_context,
        ),
    )


def build_messages(
    question: str,
    context: str,
    entry_symbol: str = "",
    entry_file: str = "",
    max_examples: int = 6,
    library: Sequence[FewShotExample] | None = None,
    system_prompt: str = SYSTEM_PROMPT,
    cot_template: str = COT_TEMPLATE,
    include_empty_context: bool = True,
    assistant_fewshot: bool = False,
    auto_hard_cot: bool = True,
    use_layer_checklist: bool = True,
    use_mislayer_prevention: bool = False,
) -> list[dict[str, str]]:
    bundle = build_prompt_bundle(
        question=question,
        context=context,
        entry_symbol=entry_symbol,
        entry_file=entry_file,
        max_examples=max_examples,
        library=library,
        system_prompt=system_prompt,
        cot_template=cot_template,
        include_empty_context=include_empty_context,
        auto_hard_cot=auto_hard_cot,
        use_layer_checklist=use_layer_checklist,
        use_mislayer_prevention=use_mislayer_prevention,
    )
    messages = [{"role": "system", "content": bundle.system_prompt.strip()}]
    if bundle.cot_template.strip():
        messages.append({"role": "system", "content": bundle.cot_template.strip()})
    for example in bundle.few_shot_examples:
        if assistant_fewshot:
            messages.append(
                {"role": "user", "content": format_few_shot_user_message(example)}
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": format_few_shot_assistant_message(example),
                }
            )
        else:
            messages.append({"role": "user", "content": format_few_shot_example(example)})
    messages.append({"role": "user", "content": bundle.user_prompt.strip()})
    return messages


# ---------------------------------------------------------------------------
# P2-18: Mislayer-Focus Few-Shot Examples
# ---------------------------------------------------------------------------
# High-risk cases based on mislayer_analysis.md:
# - Type B (@shared_task): 66.7% mislayer rate
# - Type A (autodiscover/finalize): 54.5% mislayer rate
# - Type E (symbol_by_name/ALIASES): 23.1% mislayer rate
# - Top confusion pairs: indirect→direct, implicit→indirect, direct→implicit
#
# These examples specifically demonstrate correct 3-layer split for hard cases.

MISLAYER_FOCUS_FEW_SHOTS: list[dict] = [
    {
        "id": "ML01",
        "title": "symbol_by_name three-component split",
        "failure_type": "Type E",
        "difficulty": "hard",
        "question": "What does `symbol_by_name('celery.backends.redis:RedisBackend')` ultimately resolve to? List all dependency layers.",
        "environment_preconditions": [
            "celery.backends.redis module is installed and accessible.",
            "BACKEND_ALIASES dictionary maps 'redis' key to RedisBackend.",
        ],
        "reasoning_steps": [
            "symbol_by_name() is a runtime string-to-class resolver → implicit_deps.",
            "The intermediate module 'celery.backends.redis' may appear as indirect path.",
            "The FINAL resolved class RedisBackend → direct_deps.",
            "Rule: resolved final class NEVER goes to indirect_deps.",
        ],
        "ground_truth": {
            "direct_deps": ["celery.backends.redis.RedisBackend"],
            "indirect_deps": [],
            "implicit_deps": ["celery.utils.symbols.symbol_by_name"],
        },
    },
    {
        "id": "ML02",
        "title": "BACKEND_ALIASES lookup resolution",
        "failure_type": "Type E",
        "difficulty": "medium",
        "question": "When `BACKEND_ALIASES['redis']` is used to get the backend class, what is the complete dependency chain?",
        "environment_preconditions": [
            "Celery app is configured with backend='redis'.",
            "BACKEND_ALIASES is populated in celery.app.backends.",
        ],
        "reasoning_steps": [
            "BACKEND_ALIASES dictionary is a runtime lookup structure → implicit_deps.",
            "The ALIASES['key'] lookup operation itself → implicit_deps.",
            "The RESOLVED RedisBackend class from the lookup → direct_deps.",
            "NEVER: put RedisBackend in indirect_deps.",
        ],
        "ground_truth": {
            "direct_deps": ["celery.backends.redis.RedisBackend"],
            "indirect_deps": ["celery.app.backends.by_name"],
            "implicit_deps": ["celery.app.backends.BACKEND_ALIASES"],
        },
    },
    {
        "id": "ML03",
        "title": "@shared_task decorator registration",
        "failure_type": "Type B",
        "difficulty": "hard",
        "question": "When `@shared_task` decorates a function, which symbols are in which dependency layers?",
        "environment_preconditions": [
            "A Celery app exists in the current process.",
            "@shared_task decorator is applied to a user-defined function.",
        ],
        "reasoning_steps": [
            "@shared_task decorator CALL → implicit_deps (runtime hook registration).",
            "connect_on_app_finalize() callback → implicit_deps (registration mechanism).",
            "_get_active_apps() → implicit_deps (app discovery).",
            "app._task_from_fun() → direct_deps (actual task registration).",
            "FINAL decorated function / Task class → direct_deps (the result).",
            "NEVER put _task_from_fun in indirect_deps — it is the direct result.",
        ],
        "ground_truth": {
            "direct_deps": ["celery.app.base.Celery._task_from_fun"],
            "indirect_deps": [],
            "implicit_deps": [
                "celery._state.connect_on_app_finalize",
                "celery._state._get_active_apps",
                "celery._state._announce_app_finalized",
            ],
        },
    },
    {
        "id": "ML04",
        "title": "Proxy lazy resolution with cached_property",
        "failure_type": "Type A",
        "difficulty": "hard",
        "question": "When `app.Worker` is accessed on a Celery app (where Worker is a cached_property), what are the dependency layers?",
        "environment_preconditions": [
            "Celery app is created with default configuration.",
            "autofinalize=True (default).",
        ],
        "reasoning_steps": [
            "celery.local.Proxy → implicit_deps (lazy proxy mechanism).",
            "celery._state.current_app → implicit_deps (Proxy instance).",
            "Celery.Worker (cached_property descriptor) → direct_deps (first stable attribute).",
            "subclass_with_self('celery.apps.worker:Worker') → implicit_deps (runtime class generation).",
            "celery.apps.worker.Worker (generated subclass with app bound) → direct_deps (final resolved class).",
            "NEVER put Worker in indirect_deps — it is the direct resolved type.",
        ],
        "ground_truth": {
            "direct_deps": [
                "celery.app.base.Celery.Worker",
                "celery.apps.worker.Worker",
            ],
            "indirect_deps": [],
            "implicit_deps": [
                "celery.local.Proxy",
                "celery._state.current_app",
                "celery.app.base.Celery.subclass_with_self",
            ],
        },
    },
    {
        "id": "ML05",
        "title": "indirect_deps vs direct_deps boundary (over-correction)",
        "failure_type": "Type D",
        "difficulty": "medium",
        "question": "For a re-export chain A→B→C where the entry file imports from B and B imports from C, which symbols belong to direct_deps vs indirect_deps?",
        "environment_preconditions": [
            "Entry file: `from celery.app import base`",
            "celery.app.base imports from celery.app.backends → C",
        ],
        "reasoning_steps": [
            "B (intermediate module that entry file imports from) → direct_deps.",
            "C (what B imports from) → indirect_deps (second hop).",
            "Rule: first-hop stable symbol → direct_deps; second-hop → indirect_deps.",
            "COMMON ERROR: model puts BOTH B and C in direct_deps.",
            "COMMON ERROR: model puts BOTH B and C in indirect_deps.",
        ],
        "ground_truth": {
            "direct_deps": ["celery.app.backends.by_name"],
            "indirect_deps": ["celery.backends.base.BaseBackend"],
            "implicit_deps": [],
        },
    },
    {
        "id": "ML06",
        "title": "instantiate() runtime resolution",
        "failure_type": "Type E",
        "difficulty": "hard",
        "question": "`instantiate('celery.backends.redis:RedisBackend', ...)` — what are the dependency layers for each symbol?",
        "environment_preconditions": [
            "instantiate() is called with a string class path.",
        ],
        "reasoning_steps": [
            "instantiate() function itself → implicit_deps (runtime instantiation).",
            "The intermediate module celery.backends.redis → indirect_deps (only if traversed).",
            "The FINAL instantiated RedisBackend class → direct_deps.",
            "Rule: instantiate() is a runtime mechanism → implicit_deps.",
            "Rule: final instantiated class → direct_deps, NOT indirect_deps.",
        ],
        "ground_truth": {
            "direct_deps": ["celery.backends.redis.RedisBackend"],
            "indirect_deps": [],
            "implicit_deps": ["celery.utils.symbols.instantiate"],
        },
    },
]


def select_mislayer_focus_examples(
    question: str,
    max_examples: int = 3,
) -> list[dict]:
    """
    Select mislayer-focus few-shot examples based on question content.
    Prioritizes Type B (@shared_task), Type E (symbol_by_name/ALIASES),
    and Type A (autodiscover/finalize) patterns.
    """
    question_lower = question.lower()
    scored: list[tuple[float, dict]] = []

    # Keyword to example IDs mapping
    keyword_to_ids = {
        "shared_task": ["ML03"],
        "symbol_by_name": ["ML01"],
        "backend_aliases": ["ML02"],
        "backend_alises": ["ML02"],  # typo variant
        "instantiate": ["ML06"],
        "proxy": ["ML04"],
        "cached_property": ["ML04"],
        "worker": ["ML04"],
        "finalize": ["ML04"],
        "autodiscover": ["ML04"],
    }

    # Score each example
    for example in MISLAYER_FOCUS_FEW_SHOTS:
        score = 0.0
        ex_id = example["id"]
        ex_text = f"{example['title']} {example['question']}".lower()

        # Check keyword matches
        for keyword, ids in keyword_to_ids.items():
            if keyword in question_lower and ex_id in ids:
                score += 5.0
            if keyword in ex_text and any(k in question_lower for k in keyword.split("_")):
                score += 3.0

        # Hard/medium difficulty bonus
        if example["difficulty"] in ("hard", "medium"):
            score += 1.0

        scored.append((score, example))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [ex for _, ex in scored[:max_examples]]


def few_shot_gap(library: Iterable[FewShotExample] | None = None) -> int:
    size = len(list(library)) if library is not None else len(FEW_SHOT_LIBRARY)
    return max(REQUIRED_FEW_SHOT_TARGET - size, 0)
