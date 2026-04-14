"""Prompt engineering core module for Python cross-file dependency analysis.

This module provides the prompt construction logic used by the PE (Prompt Engineering)
pipeline to resolve fully qualified names (FQNs) in Celery source code.

Main components:
    - SYSTEM_PROMPT / COT_TEMPLATE: Fixed instruction scaffolds guiding the model
      to perform static analysis and return only a JSON array of FQNs.
    - FewShotExample / PromptBundle: Data structures for few-shot example management
      and prompt composition.
    - FEW_SHOT_LIBRARY: Curated examples spanning re-export, alias resolution,
      loader/backend alias, cached-property delegation, and finalize-callback
      registration patterns at easy / medium / hard difficulty levels.
    - select_few_shot_examples(): Scores and selects the top-k relevant examples
      from the library using an overlap + category + entry + hard-bonus scheme.
    - build_user_prompt() / build_prompt_bundle() / build_messages(): Assemble
      individual prompt components into user-facing strings or chat-style message
      lists suitable for model inference.

The module is intentionally stateless; all state (selected examples, bundle)
is returned as plain dataclass instances or lists so callers control caching
and injection.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable, Sequence


SYSTEM_PROMPT = """\
You are a senior Python static analysis expert working on cross-file dependency resolution.
Resolve the final dependency targets precisely against the provided Celery source context.
Only output a JSON array of fully qualified names (FQNs).
Do not include explanations, markdown, XML tags, or any extra prose.
Always respond in English, regardless of the question language.
"""


COT_TEMPLATE = """\
Reason internally using this checklist before answering:
1. Locate the entry symbol and identify whether it is a re-export, alias, decorator flow, or dynamic string target.
2. Resolve explicit imports, alias maps, cached properties, and string-based targets in the provided files.
3. Follow the final registration or lookup hop instead of stopping at an intermediate trampoline.
4. Return the final dependency targets as a JSON array of Python-style FQNs.
"""


OUTPUT_INSTRUCTIONS = (
    "Return only a JSON array of final FQNs. "
    "Use dotted Python paths such as `celery.app.base.Celery`."
)


_TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]+")


@dataclass(frozen=True)
class FewShotExample:
    case_id: str
    difficulty: str
    category: str
    question: str
    context: str
    answer: tuple[str, ...]
    reasoning: str


@dataclass(frozen=True)
class PromptBundle:
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


REQUIRED_FEW_SHOT_TARGET = 20


def _example(
    case_id: str,
    difficulty: str,
    category: str,
    question: str,
    context: str,
    answer: Sequence[str],
    reasoning: str,
) -> FewShotExample:
    return FewShotExample(
        case_id=case_id,
        difficulty=difficulty,
        category=category,
        question=question,
        context=context.strip(),
        answer=tuple(answer),
        reasoning=reasoning.strip(),
    )


FEW_SHOT_LIBRARY: list[FewShotExample] = [
    _example(
        "fs_001",
        "easy",
        "re_export",
        "Which real class does `celery.Celery` resolve to in the top-level lazy API?",
        """
File: celery/__init__.py
old_module, new_module = local.recreate_module(
    __name__,
    by_module={'celery.app': ['Celery', 'bugreport', 'shared_task'], ...},
)

File: celery/app/__init__.py
from .base import Celery
""",
        ["celery.app.base.Celery"],
        "The top-level `celery` module lazily re-exports `Celery` from `celery.app`, and `celery.app` imports it from `.base`.",
    ),
    _example(
        "fs_002",
        "easy",
        "re_export",
        "Which real function does the top-level `celery.shared_task` symbol resolve to?",
        """
File: celery/__init__.py
by_module={'celery.app': ['Celery', 'bugreport', 'shared_task'], ...}

File: celery/app/__init__.py
def shared_task(*args, **kwargs):
    ...
""",
        ["celery.app.shared_task"],
        "`celery.__init__` forwards `shared_task` to the `celery.app` module, where the function is defined directly.",
    ),
    _example(
        "fs_003",
        "easy",
        "re_export",
        "Which real class does `celery.Task` resolve to?",
        """
File: celery/__init__.py
by_module={'celery.app.task': ['Task'], ...}

File: celery/app/task.py
class Task:
    ...
""",
        ["celery.app.task.Task"],
        "The top-level module re-exports `Task` from `celery.app.task`, and the concrete class is defined there.",
    ),
    _example(
        "fs_004",
        "easy",
        "re_export",
        "Which real symbol does `celery.current_app` resolve to?",
        """
File: celery/__init__.py
by_module={'celery._state': ['current_app', 'current_task'], ...}

File: celery/_state.py
current_app = Proxy(get_current_app)
""",
        ["celery._state.current_app"],
        "The symbol is lazily forwarded to `celery._state`, which defines the exported proxy object.",
    ),
    _example(
        "fs_005",
        "easy",
        "re_export",
        "Which real symbol does `celery.current_task` resolve to?",
        """
File: celery/__init__.py
by_module={'celery._state': ['current_app', 'current_task'], ...}

File: celery/_state.py
current_task = Proxy(get_current_task)
""",
        ["celery._state.current_task"],
        "The top-level export points to `celery._state`, and `current_task` is defined there as the exported proxy.",
    ),
    _example(
        "fs_006",
        "medium",
        "loader_alias",
        "In `celery.loaders.get_loader_cls`, what does `get_loader_cls('default')` resolve to?",
        """
File: celery/loaders/__init__.py
LOADER_ALIASES = {
    'app': 'celery.loaders.app:AppLoader',
    'default': 'celery.loaders.default:Loader',
}

def get_loader_cls(loader):
    return symbol_by_name(loader, LOADER_ALIASES, imp=import_from_cwd)
""",
        ["celery.loaders.default.Loader"],
        "The alias map binds the string `default` to `celery.loaders.default:Loader`, which becomes the dotted FQN `celery.loaders.default.Loader`.",
    ),
    _example(
        "fs_007",
        "medium",
        "loader_alias",
        "In `celery.loaders.get_loader_cls`, what does `get_loader_cls('app')` resolve to?",
        """
File: celery/loaders/__init__.py
LOADER_ALIASES = {
    'app': 'celery.loaders.app:AppLoader',
    'default': 'celery.loaders.default:Loader',
}
""",
        ["celery.loaders.app.AppLoader"],
        "The alias `app` maps directly to `celery.loaders.app:AppLoader`.",
    ),
    _example(
        "fs_008",
        "medium",
        "alias_resolution",
        "What pool implementation does `celery.concurrency.get_implementation('processes')` resolve to?",
        """
File: celery/concurrency/__init__.py
ALIASES = {
    'prefork': 'celery.concurrency.prefork:TaskPool',
    'processes': 'celery.concurrency.prefork:TaskPool',
}

def get_implementation(cls):
    return symbol_by_name(cls, ALIASES)
""",
        ["celery.concurrency.prefork.TaskPool"],
        "The compatibility alias `processes` points to the same `prefork` task pool class.",
    ),
    _example(
        "fs_009",
        "medium",
        "alias_resolution",
        "What pool implementation does `celery.concurrency.get_implementation('threads')` resolve to?",
        """
File: celery/concurrency/__init__.py
try:
    import concurrent.futures
except ImportError:
    pass
else:
    ALIASES['threads'] = 'celery.concurrency.thread:TaskPool'
""",
        ["celery.concurrency.thread.TaskPool"],
        "When thread support is available, the alias map explicitly binds `threads` to `celery.concurrency.thread:TaskPool`.",
    ),
    _example(
        "fs_010",
        "medium",
        "backend_alias",
        "Which backend class does `celery.app.backends.by_name('redis')` resolve to?",
        """
File: celery/app/backends.py
BACKEND_ALIASES = {
    'redis': 'celery.backends.redis:RedisBackend',
    'rediss': 'celery.backends.redis:RedisBackend',
    ...
}

def by_name(backend=None, loader=None, ...):
    cls = symbol_by_name(backend, aliases)
""",
        ["celery.backends.redis.RedisBackend"],
        "The backend alias table maps `redis` directly to `celery.backends.redis:RedisBackend`.",
    ),
    _example(
        "fs_011",
        "medium",
        "backend_alias",
        "Which backend class does `celery.app.backends.by_name('database')` resolve to?",
        """
File: celery/app/backends.py
BACKEND_ALIASES = {
    'db': 'celery.backends.database:DatabaseBackend',
    'database': 'celery.backends.database:DatabaseBackend',
}
""",
        ["celery.backends.database.DatabaseBackend"],
        "Both `db` and `database` point to the database backend class, so the final FQN is `celery.backends.database.DatabaseBackend`.",
    ),
    _example(
        "fs_012",
        "medium",
        "backend_alias",
        "Which backend class does `celery.app.backends.by_name('cache')` resolve to?",
        """
File: celery/app/backends.py
BACKEND_ALIASES = {
    'cache': 'celery.backends.cache:CacheBackend',
    ...
}
""",
        ["celery.backends.cache.CacheBackend"],
        "The alias table maps `cache` to `celery.backends.cache:CacheBackend`.",
    ),
    _example(
        "fs_013",
        "medium",
        "delegation",
        "Which helper function does `Celery.gen_task_name` delegate to?",
        """
File: celery/app/base.py
from celery.utils.imports import gen_task_name

def gen_task_name(self, name, module):
    return gen_task_name(self, name, module)
""",
        ["celery.utils.imports.gen_task_name"],
        "`Celery.gen_task_name` is a thin delegator and forwards directly to the imported helper.",
    ),
    _example(
        "fs_014",
        "medium",
        "cached_property",
        "Which concrete worker class does `Celery.Worker` resolve to?",
        """
File: celery/app/base.py
@cached_property
def Worker(self):
    return self.subclass_with_self('celery.apps.worker:Worker')

def subclass_with_self(self, Class, ...):
    Class = symbol_by_name(Class)
""",
        ["celery.apps.worker.Worker"],
        "The cached property calls `subclass_with_self` with the string path `celery.apps.worker:Worker`, which resolves via `symbol_by_name`.",
    ),
    _example(
        "fs_015",
        "medium",
        "cached_property",
        "Which result class does `Celery.AsyncResult` resolve to?",
        """
File: celery/app/base.py
@cached_property
def AsyncResult(self):
    return self.subclass_with_self('celery.result:AsyncResult')
""",
        ["celery.result.AsyncResult"],
        "The property wraps the concrete `celery.result:AsyncResult` class, so the resolved FQN is `celery.result.AsyncResult`.",
    ),
    _example(
        "fs_016",
        "medium",
        "default_loader",
        "If no explicit loader is passed, which class does `Celery.loader` instantiate by default?",
        """
File: celery/app/base.py
def _get_default_loader(self):
    return os.environ.get('CELERY_LOADER') or self.loader_cls or 'celery.loaders.app:AppLoader'

@cached_property
def loader(self):
    return get_loader_cls(self.loader_cls)(app=self)
""",
        ["celery.loaders.app.AppLoader"],
        "Without overrides, `_get_default_loader` returns the string `celery.loaders.app:AppLoader`, and `loader` resolves and instantiates that class.",
    ),
    _example(
        "fs_017",
        "hard",
        "shared_task_registration",
        "When `@shared_task` decorates a function, which real app method ultimately creates the task instance?",
        """
File: celery/app/__init__.py
_state.connect_on_app_finalize(
    lambda app: app._task_from_fun(fun, **options)
)

for app in _state._get_active_apps():
    if app.finalized:
        app._task_from_fun(fun, **options)
""",
        ["celery.app.base.Celery._task_from_fun"],
        "Both the finalize callback and the eager branch call `app._task_from_fun`, so that is the true registration target.",
    ),
    _example(
        "fs_018",
        "hard",
        "app_task_registration",
        "Inside the `@app.task` decorator flow, which real method ultimately constructs and registers the task?",
        """
File: celery/app/base.py
def task(self, *args, **opts):
    def inner_create_task_cls(...):
        def _create_task_cls(fun):
            if shared:
                def cons(app):
                    return app._task_from_fun(fun, **opts)
                connect_on_app_finalize(cons)
            if not lazy or self.finalized:
                ret = self._task_from_fun(fun, **opts)
""",
        ["celery.app.base.Celery._task_from_fun"],
        "The decorator eventually funnels both the shared and non-shared branches into `self._task_from_fun`.",
    ),
    _example(
        "fs_019",
        "hard",
        "finalize_callback",
        "Which function is responsible for firing all shared-task and built-in finalize callbacks?",
        """
File: celery/_state.py
def connect_on_app_finalize(callback):
    _on_app_finalizers.add(callback)

def _announce_app_finalized(app):
    callbacks = set(_on_app_finalizers)
    for callback in callbacks:
        callback(app)

File: celery/app/base.py
def finalize(self, auto=False):
    self.finalized = True
    _announce_app_finalized(self)
""",
        ["celery._state._announce_app_finalized"],
        "Callbacks are registered via `connect_on_app_finalize`, but `_announce_app_finalized` is the function that actually invokes them during app finalization.",
    ),
    _example(
        "fs_020",
        "hard",
        "symbol_by_name_resolution",
        "In `celery.worker.strategy.default`, what real class does `task.Request` resolve to?",
        """
File: celery/worker/strategy.py
Request = symbol_by_name(task.Request)

File: celery/app/task.py
class Task:
    Request = 'celery.worker.request:Request'
""",
        ["celery.worker.request.Request"],
        "The strategy resolves the string held in `Task.Request`, which points to `celery.worker.request:Request`.",
    ),
    _example(
        "fs_021",
        "hard",
        "builtin_registration",
        "Which real registration method ultimately registers the built-in `celery.backend_cleanup` task?",
        """
File: celery/app/builtins.py
@connect_on_app_finalize
def add_backend_cleanup_task(app):
    @app.task(name='celery.backend_cleanup', shared=False, lazy=False)
    def backend_cleanup():
        app.backend.cleanup()

File: celery/app/base.py
def task(...):
    ret = self._task_from_fun(fun, **opts)
""",
        ["celery.app.base.Celery._task_from_fun"],
        "The built-in finalize hook wraps the inner function with `@app.task`, and that decorator path ultimately calls `_task_from_fun`.",
    ),
    _example(
        "fs_022",
        "medium",
        "strategy_resolution",
        "Which execution strategy function does `Task.Strategy` point to?",
        """
File: celery/app/task.py
class Task:
    Strategy = 'celery.worker.strategy:default'
""",
        ["celery.worker.strategy.default"],
        "The class attribute already stores the fully qualified strategy target in `module:callable` form.",
    ),
]


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


def format_few_shot_example(example: FewShotExample) -> str:
    return (
        f"[Few-shot {example.case_id} | {example.difficulty} | {example.category}]\n"
        f"Question:\n{example.question}\n\n"
        f"Context:\n{example.context}\n\n"
        f"Reasoning:\n{example.reasoning}\n\n"
        f"Answer:\n{json.dumps(list(example.answer), ensure_ascii=False)}"
    )


def select_few_shot_examples(
    question: str,
    context: str = "",
    entry_symbol: str = "",
    max_examples: int = 6,
    library: Sequence[FewShotExample] | None = None,
) -> list[FewShotExample]:
    """Select the top-k few-shot examples most relevant to the given query.

    Each candidate is scored using a weighted four-signal scheme:

    1. **Token overlap (weight 3.0):** Jaccard-like signal; the query and the
       example are both tokenised (lowercased, CamelCase split) and the
       cardinality of their intersection drives the base score.

    2. **Category hit (weight 2.0):** A binary bonus of 1 when at least one
       query token appears inside the example's ``category`` field, encouraging
       selection of examples from the same resolution pattern
       (e.g. ``re_export``, ``alias_resolution``).

    3. **Entry symbol tail hit (weight 2.5):** A binary bonus when the last
       component of the supplied ``entry_symbol`` (e.g. ``Celery`` from
       ``celery.app.base.Celery``) occurs verbatim anywhere in the example
       text, capturing structural similarity.

    4. **Hard-example bonus (+0.25):** A small additive bonus for ``hard``
       examples so that they appear earlier in ties, improving coverage of
       complex patterns without dominating the selection.

    The final sort key is ``(score DESC, hard_examples_first, medium_examples_first, case_id ASC)``,
    guaranteeing a stable order and deterministic output.

    Args:
        question: The user's dependency-resolution question.
        context: Concatenated source-file snippets providing the analysis context.
        entry_symbol: The symbol whose final target is being asked for.
        max_examples: Maximum number of examples to return (0 returns ``[]``).
        library: Override the example pool; defaults to ``FEW_SHOT_LIBRARY``.

    Returns:
        A list of up to ``max_examples`` selected ``FewShotExample`` instances,
        ordered by relevance score descending.
    """
    examples = list(library or FEW_SHOT_LIBRARY)
    if max_examples <= 0 or not examples:
        return []

    query_text = " ".join(part for part in (question, context, entry_symbol) if part)
    query_tokens = _tokenize(query_text)
    entry_tail = entry_symbol.rsplit(".", 1)[-1].lower() if entry_symbol else ""

    scored: list[tuple[float, FewShotExample]] = []
    for example in examples:
        example_text = " ".join(
            [
                example.question,
                example.context,
                example.reasoning,
                example.category,
                example.difficulty,
                " ".join(example.answer),
            ]
        )
        example_tokens = _tokenize(example_text)
        overlap = len(query_tokens & example_tokens)
        category_hit = (
            1 if any(token in example.category for token in query_tokens) else 0
        )
        entry_hit = 1 if entry_tail and entry_tail in example_text.lower() else 0
        hard_bonus = 0.25 if example.difficulty == "hard" else 0.0
        score = overlap * 3.0 + category_hit * 2.0 + entry_hit * 2.5 + hard_bonus
        scored.append((score, example))

    scored.sort(
        key=lambda item: (
            item[0],
            item[1].difficulty == "hard",
            item[1].difficulty == "medium",
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


def build_user_prompt(
    question: str,
    context: str,
    entry_symbol: str = "",
    entry_file: str = "",
) -> str:
    lines = ["Question:", question.strip()]
    if entry_symbol.strip():
        lines.extend(["", "Provided Entry Symbol:", entry_symbol.strip()])
    if entry_file.strip():
        lines.extend(["", "Provided Entry File:", entry_file.strip()])
    lines.extend(
        [
            "",
            "Context:",
            context.strip(),
            "",
            OUTPUT_INSTRUCTIONS,
        ]
    )
    return "\n".join(lines)


def build_prompt_bundle(
    question: str,
    context: str,
    entry_symbol: str = "",
    entry_file: str = "",
    max_examples: int = 6,
    library: Sequence[FewShotExample] | None = None,
) -> PromptBundle:
    selected = select_few_shot_examples(
        question=question,
        context=context,
        entry_symbol=entry_symbol,
        max_examples=max_examples,
        library=library,
    )
    return PromptBundle(
        system_prompt=SYSTEM_PROMPT,
        cot_template=COT_TEMPLATE,
        few_shot_examples=tuple(selected),
        user_prompt=build_user_prompt(
            question=question,
            context=context,
            entry_symbol=entry_symbol,
            entry_file=entry_file,
        ),
    )


def build_messages(
    question: str,
    context: str,
    entry_symbol: str = "",
    entry_file: str = "",
    max_examples: int = 6,
) -> list[dict[str, str]]:
    bundle = build_prompt_bundle(
        question=question,
        context=context,
        entry_symbol=entry_symbol,
        entry_file=entry_file,
        max_examples=max_examples,
    )
    messages = [{"role": "system", "content": bundle.system_prompt.strip()}]
    if bundle.cot_template.strip():
        messages.append({"role": "system", "content": bundle.cot_template.strip()})
    for example in bundle.few_shot_examples:
        messages.append({"role": "user", "content": format_few_shot_example(example)})
    messages.append({"role": "user", "content": bundle.user_prompt.strip()})
    return messages


def few_shot_gap(library: Iterable[FewShotExample] | None = None) -> int:
    size = len(list(library)) if library is not None else len(FEW_SHOT_LIBRARY)
    return max(REQUIRED_FEW_SHOT_TARGET - size, 0)
