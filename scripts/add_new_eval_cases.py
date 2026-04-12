"""
Add 18 new hard cases to eval_cases.json to expand from 102 to 120+ cases.

Target blind spots:
- celery/canvas.py: chain/group/chord complex combinations
- celery/schedules.py: crontab_parser, schedule timezone
- celery/bin/celery.py: CLI autodiscover
- celery/utils/serialization.py: exception serialization
- celery/result.py: GroupResult deserialization
"""
import json
from pathlib import Path

path = Path(__file__).parent.parent / "data" / "eval_cases.json"
cases = json.loads(path.read_text(encoding="utf-8-sig"))
print(f"Current count: {len(cases)}")

# Track highest IDs per (type_letter, difficulty)
highest_ids = {}
for c in cases:
    cid = c["case_id"]
    parts = cid.replace("celery_type_", "").split("_", 2)
    if len(parts) >= 3:
        type_letter = parts[0]
        diff = parts[1]
        num_str = parts[2]
        key = (type_letter, diff)
        num = int(num_str)
        if key not in highest_ids or num > highest_ids[key]:
            highest_ids[key] = num


def next_id(type_letter: str, diff: str) -> str:
    key = (type_letter, diff)
    n = highest_ids.get(key, 0) + 1
    highest_ids[key] = n
    return f"celery_type_{type_letter}_{diff}_{n:03d}"


# Define 18 new hard cases
new_cases = [
    # === Type D Hard: chain.__new__ reduce(operator.or_) polymorphic dispatch ===
    {
        "difficulty": "hard",
        "category": "chain_polymorphic_dispatch_via_reduce",
        "failure_type": "Type D",
        "implicit_level": 4,
        "question": "In celery/canvas.py, when calling chain(X, Y, Z) with multiple Signatures, how does reduce(operator.or_, tasks, _chain()) flatten the task list step by step? Specifically, what happens when one task is itself a _chain instance?",
        "source_file": "celery/canvas.py",
        "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
        "ground_truth": {
            "direct_deps": ["celery.canvas.chain.__new__"],
            "indirect_deps": [
                "celery.canvas._chain.__or__",
                "celery.canvas.operator.or_",
            ],
            "implicit_deps": [
                "celery.canvas._chain.unchain_tasks",
                "celery.canvas.Signature.__or__",
            ],
        },
        "reasoning_hint": "reduce(or_, tasks) processes left to right. X|Y calls Signature.__or__ returning _chain(X,Y); then _chain(X,Y)|Z calls _chain.__or__ (Z is Signature) returning type(self)(seq_concat_item(unchain_tasks(), Z)) which flattens.",
        "source_note": "Blind spot: canvas chain.__new__ reduce(operator.or_) deep chain reduction not covered",
        "case_id": next_id("d", "hard"),
        "entry_symbol": None,
        "entry_file": None,
    },
    # === Type D Hard: group.__or__ chord upgrade ===
    {
        "difficulty": "hard",
        "category": "group_or_chord_upgrade",
        "failure_type": "Type D",
        "implicit_level": 3,
        "question": "In celery/canvas.py, during the automatic upgrade of group(task1, task2) | task3 to chord, which function does _chord.__init__ call on the body parameter to perform polymorphic deserialization when the body is passed as a dict?",
        "source_file": "celery/canvas.py",
        "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
        "ground_truth": {
            "direct_deps": ["celery.canvas._chord.__init__"],
            "indirect_deps": [
                "celery.canvas.group.__or__",
                "celery.canvas.maybe_signature",
            ],
            "implicit_deps": [
                "celery.canvas._chord.from_dict",
                "celery.canvas._maybe_group",
            ],
        },
        "reasoning_hint": "group.__or__ returns chord(self, body=other); _chord.__init__ calls maybe_signature(body, app=app) which calls Signature.from_dict when body is a dict, triggering polymorphic dispatch.",
        "source_note": "Blind spot: group.__or__ chord upgrade + _chord.__init__ body polymorphic deserialization",
        "case_id": next_id("d", "hard"),
        "entry_symbol": None,
        "entry_file": None,
    },
    # === Type D Hard: crontab_parser._expand_range wrap-around ===
    {
        "difficulty": "hard",
        "category": "crontab_range_wrap_around",
        "failure_type": "Type D",
        "implicit_level": 3,
        "question": "In celery/schedules.py, when crontab_parser._expand_range processes a reverse range like '20-5' (crossing midnight), what specific logic constructs the list that spans across the boundary? How does the condition `to < fr` affect the construction of the final list?",
        "source_file": "celery/schedules.py",
        "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
        "ground_truth": {
            "direct_deps": ["celery.schedules.crontab_parser._expand_range"],
            "indirect_deps": [
                "celery.schedules.crontab_parser.parse",
                "celery.schedules.crontab_parser._parse_part",
            ],
            "implicit_deps": [
                "celery.schedules.crontab_parser._expand_number",
            ],
        },
        "reasoning_hint": "When to < fr (e.g., 20-5 for 20:00 to 05:00 next day), _expand_range constructs range(fr, max_+min_) first (crossing the boundary), then range(min_, to+1). This creates a wrap-around list spanning midnight.",
        "source_note": "Blind spot: crontab_parser._expand_range wrap-around not covered",
        "case_id": next_id("d", "hard"),
        "entry_symbol": None,
        "entry_file": None,
    },
    # === Type D Hard: _prepare_chain_from_options ChainMap mutability ===
    {
        "difficulty": "hard",
        "category": "prepare_chain_chainmap_mutation",
        "failure_type": "Type D",
        "implicit_level": 4,
        "question": "In celery/canvas.py, when _prepare_chain_from_options has options['chain'] already existing and returns ChainMap({'chain': options['chain'] + tasks}, options), is options['chain'] + tasks creating a new list or mutating the original? What specific problem does the comment 'WARNING: Be careful not to mutate options['chain']' guard against?",
        "source_file": "celery/canvas.py",
        "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
        "ground_truth": {
            "direct_deps": ["celery.canvas._prepare_chain_from_options"],
            "indirect_deps": [
                "celery.canvas._chain.run",
                "celery.canvas.group.apply_async",
            ],
            "implicit_deps": ["celery.canvas.ChainMap"],
        },
        "reasoning_hint": "options['chain'] + tasks creates a new list (not mutating the original). The guard prevents shared options dict across multiple tasks in a GroupResult from having chain extended incorrectly, which would cause tasks to inherit the wrong chain list.",
        "source_note": "Blind spot: _prepare_chain_from_options ChainMap immutability guard not covered",
        "case_id": next_id("d", "hard"),
        "entry_symbol": None,
        "entry_file": None,
    },
    # === Type A Hard: group._freeze_unroll deque flattening ===
    {
        "difficulty": "hard",
        "category": "group_freeze_unroll_deque",
        "failure_type": "Type A",
        "implicit_level": 4,
        "question": "In celery/canvas.py, group._freeze_unroll uses a deque with popleft and extendleft operations to flatten nested groups. The traversal order determines the final frozen task list. For a nested structure like [[g1, [g2, [t1, t2]], t3]], what is the final order of frozen tasks?",
        "source_file": "celery/canvas.py",
        "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
        "ground_truth": {
            "direct_deps": ["celery.canvas.group._freeze_unroll"],
            "indirect_deps": [
                "celery.canvas.group._freeze_group_tasks",
                "celery.canvas.maybe_signature",
            ],
            "implicit_deps": [
                "celery.canvas.group.clone",
                "celery.canvas.group.from_dict",
            ],
        },
        "reasoning_hint": "deque.popleft() traverses left to right; extendleft reverses order when appending group tasks. For [[g1,[g2,[t1,t2]],t3]]: deque starts with [g1,g2,t1,t2,t3] (from outer group), extendleft(g2,t1,t2) reverses to [t1,t2,g2], yielding [t1,t2,g2,g1,t3].",
        "source_note": "Blind spot: group._freeze_unroll deque flatten order not covered",
        "case_id": next_id("a", "hard"),
        "entry_symbol": None,
        "entry_file": None,
    },
    # === Type A Hard: StampingVisitor.on_signature recursive stamping ===
    {
        "difficulty": "hard",
        "category": "stamping_visitor_recursive_stamp",
        "failure_type": "Type A",
        "implicit_level": 4,
        "question": "In celery/canvas.py, Signature.stamp_links iterates over callbacks and errbacks calling link.stamp(visitor, ...) for each. How does this implement the recursive visitor pattern through visitor.on_callback and visitor.on_errback? Which visitor methods may be short-circuited (returning empty dict by default)?",
        "source_file": "celery/canvas.py",
        "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
        "ground_truth": {
            "direct_deps": ["celery.canvas.Signature.stamp_links"],
            "indirect_deps": [
                "celery.canvas.StampingVisitor.on_callback",
                "celery.canvas.StampingVisitor.on_errback",
            ],
            "implicit_deps": [
                "celery.canvas.Signature.stamp",
                "celery.canvas.StampingVisitor.on_signature",
            ],
        },
        "reasoning_hint": "stamp_links iterates link/link_error via maybe_list, calls maybe_signature on each dict, then calls stamp(). stamp() calls visitor.on_signature/on_callback/on_errback which return empty dict by default (short-circuit). If user implements recursive visitor, it depth-first traverses the full callback tree.",
        "source_note": "Blind spot: StampingVisitor recursive stamp_links traversal not covered",
        "case_id": next_id("a", "hard"),
        "entry_symbol": None,
        "entry_file": None,
    },
    # === Type A Hard: chain.prepare_steps group->chord auto upgrade ===
    {
        "difficulty": "hard",
        "category": "chain_prepare_steps_group_chord_upgrade",
        "failure_type": "Type A",
        "implicit_level": 5,
        "question": "In celery/canvas.py _chain.prepare_steps, when traversing the deque encounters a group with prev_task already set, how does the code automatically upgrade the group to a chord? What internal data structures (tasks/results list) are modified during this upgrade?",
        "source_file": "celery/canvas.py",
        "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
        "ground_truth": {
            "direct_deps": ["celery.canvas._chain.prepare_steps"],
            "indirect_deps": [
                "celery.canvas._chord",
                "celery.canvas.group",
                "celery.canvas.maybe_unroll_group",
            ],
            "implicit_deps": [
                "celery.canvas.maybe_signature",
                "celery.canvas._chain.unchain_tasks",
            ],
        },
        "reasoning_hint": "When encountering group with prev_task: 1) tasks.pop() and results.pop() remove prev_task; 2) chord(task=group, body=prev_task, ...) constructs the chord replacing the group. The current group's tasks remain in the header, prev_task moves to body, and prev_task/prev_res are updated.",
        "source_note": "Blind spot: _chain.prepare_steps group->chord auto-upgrade data structure mutation",
        "case_id": next_id("a", "hard"),
        "entry_symbol": None,
        "entry_file": None,
    },
    # === Type B Hard: Signature.flatten_links recursive collection ===
    {
        "difficulty": "hard",
        "category": "flatten_links_recursive_callback_collection",
        "failure_type": "Type B",
        "implicit_level": 4,
        "question": "In celery/canvas.py, Signature.flatten_links uses itertools.chain.from_iterable recursively to collect all callback chains. When a callback itself links to another callback, how does the recursion terminate? What happens when a signature has no further callbacks?",
        "source_file": "celery/canvas.py",
        "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
        "ground_truth": {
            "direct_deps": ["celery.canvas.Signature.flatten_links"],
            "indirect_deps": ["celery.canvas.maybe_list"],
            "implicit_deps": ["celery.canvas.Signature.link"],
        },
        "reasoning_hint": "flatten_links generates [[self], flatten_links(link1), flatten_links(link2), ...] then chain.from_iterable flattens. Recursion terminates when a link has no further callbacks (maybe_list returns [] which produces empty iterator).",
        "source_note": "Blind spot: Signature.flatten_links recursive callback chain collection",
        "case_id": next_id("b", "hard"),
        "entry_symbol": None,
        "entry_file": None,
    },
    # === Type B Hard: group._apply_tasks itertools.tee ===
    {
        "difficulty": "hard",
        "category": "group_apply_tasks_generator_tee",
        "failure_type": "Type B",
        "implicit_level": 4,
        "question": "In celery/canvas.py, group._apply_tasks uses itertools.tee to duplicate the tasks generator. How does this allow the loop to look ahead at the next task while processing the current one? Specifically, how does the code determine the last task in the group to finalize the chord size?",
        "source_file": "celery/canvas.py",
        "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
        "ground_truth": {
            "direct_deps": ["celery.canvas.group._apply_tasks"],
            "indirect_deps": [
                "celery.canvas.group.apply_async",
                "celery.canvas.maybe_signature",
            ],
            "implicit_deps": ["celery.canvas._chord._descend"],
        },
        "reasoning_hint": "itertools.tee creates two independent iterators: tasks_shifted and tasks. next(tasks_shifted) peeks ahead; if it returns None, the current task in the main 'tasks' iterator is the last one, triggering app.backend.set_chord_size(group_id, chord_size).",
        "source_note": "Blind spot: group._apply_tasks itertools.tee lookahead for chord finalization",
        "case_id": next_id("b", "hard"),
        "entry_symbol": None,
        "entry_file": None,
    },
    # === Type B Hard: Signature.on_error chaining ===
    {
        "difficulty": "hard",
        "category": "on_error_return_value_chain",
        "failure_type": "Type B",
        "implicit_level": 2,
        "question": "In celery/canvas.py, what is the essential difference in return value between Signature.on_error(errback) and Signature.link_error(errback)? How does this difference affect the semantics of canvas chaining (|) when composing error-handling workflows?",
        "source_file": "celery/canvas.py",
        "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
        "ground_truth": {
            "direct_deps": ["celery.canvas.Signature.on_error"],
            "indirect_deps": ["celery.canvas.Signature.link_error"],
            "implicit_deps": ["celery.canvas.Signature.link"],
        },
        "reasoning_hint": "on_error calls link_error then returns self (original signature); link_error returns the errback signature. Therefore sig.on_error(e) | next_task links next_task to sig, while sig.link_error(e) | next_task links next_task to the errback.",
        "source_note": "Blind spot: Signature.on_error vs link_error return value difference",
        "case_id": next_id("b", "hard"),
        "entry_symbol": None,
        "entry_file": None,
    },
    # === Type C Hard: xmap/xstarmap/_basemap Signature subclassing ===
    {
        "difficulty": "hard",
        "category": "xmap_xstarmap_signature_subclass_registry",
        "failure_type": "Type C",
        "implicit_level": 3,
        "question": "In celery/canvas.py, xmap, xstarmap, and chunks all inherit from _basemap which inherits from Signature. When deserializing via Signature.from_dict({'subtask_type': 'xmap', ...}), which registry does the polymorphic lookup use? How does each subclass register itself via the @Signature.register_type() decorator?",
        "source_file": "celery/canvas.py",
        "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
        "ground_truth": {
            "direct_deps": ["celery.canvas._basemap"],
            "indirect_deps": [
                "celery.canvas.Signature.TYPES",
                "celery.canvas.xmap",
                "celery.canvas.xstarmap",
                "celery.canvas.chunks",
            ],
            "implicit_deps": [
                "celery.canvas.Signature.from_dict",
                "celery.canvas.Signature.register_type",
            ],
        },
        "reasoning_hint": "@Signature.register_type() stores subclasses in cls.TYPES dict (key=decorator arg name, defaults to class name). Signature.from_dict uses d.get('subtask_type') to look up cls.TYPES and calls the subclass's from_dict. xmap/xstarmap/chunks use their class names as keys since no name arg is specified.",
        "source_note": "Blind spot: xmap/xstarmap/chunks Signature.register_type polymorphic dispatch",
        "case_id": next_id("c", "hard"),
        "entry_symbol": None,
        "entry_file": None,
    },
    # === Type C Hard: crontab_parser._expand_number weekday/yearmonth names ===
    {
        "difficulty": "hard",
        "category": "crontab_parser_expand_number_literal_names",
        "failure_type": "Type C",
        "implicit_level": 3,
        "question": "In celery/schedules.py, crontab_parser._expand_number attempts three sequential conversion strategies for string literals (e.g., 'monday', 'jan'). What are these three strategies in order, and what happens when the string is neither a valid weekday nor month abbreviation?",
        "source_file": "celery/schedules.py",
        "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
        "ground_truth": {
            "direct_deps": ["celery.schedules.crontab_parser._expand_number"],
            "indirect_deps": [
                "celery.schedules.crontab_parser.parse",
                "celery.schedules.crontab_parser._parse_part",
            ],
            "implicit_deps": [
                "celery.utils.time.weekday",
                "celery.utils.time.yearmonth",
            ],
        },
        "reasoning_hint": "The three strategies are: 1) int(s) 2) yearmonth(s) for month abbreviations (jan->1) 3) weekday(s) for day abbreviations (monday->0). If all fail, it raises ValueError caught as ParseException. The order matters: 'wed' (3) would be parsed as int(3) if integer parsing happened first.",
        "source_note": "Blind spot: crontab_parser._expand_number 3-tier name->int resolution",
        "case_id": next_id("c", "hard"),
        "entry_symbol": None,
        "entry_file": None,
    },
    # === Type E Hard: crontab._expand_cronspec type-based dispatch ===
    {
        "difficulty": "hard",
        "category": "crontab_expand_cronspec_type_dispatch",
        "failure_type": "Type E",
        "implicit_level": 3,
        "question": "In celery/schedules.py, crontab._expand_cronspec dispatches based on the type of cronspec input (int/str/set/Iterable). When a Python set (e.g., {0, 15, 30, 45}) is passed as the cronspec, what does this method return directly without parsing? How does this design ensure type safety?",
        "source_file": "celery/schedules.py",
        "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
        "ground_truth": {
            "direct_deps": ["celery.schedules.crontab._expand_cronspec"],
            "indirect_deps": [
                "celery.schedules.crontab_parser.parse",
                "celery.schedules.crontab.__init__",
            ],
            "implicit_deps": ["celery.schedules.crontab_parser"],
        },
        "reasoning_hint": "When cronspec is a set type, _expand_cronspec directly returns set(cronspec) without parsing. This bypasses the string parsing path, preventing injection attacks, and allows users to pass pre-validated sets directly.",
        "source_note": "Blind spot: crontab._expand_cronspec set type fast path",
        "case_id": next_id("e", "hard"),
        "entry_symbol": None,
        "entry_file": None,
    },
    # === Type E Hard: schedule.to_local utc_enabled decision ===
    {
        "difficulty": "hard",
        "category": "schedule_to_local_utc_enabled_resolution",
        "failure_type": "Type E",
        "implicit_level": 3,
        "question": "In celery/schedules.py schedule.to_local, when self.utc_enabled is False, it calls timezone.to_local_fallback. What is the actual configuration value self.utc_enabled resolves to? What is its default value, and in what scenarios would it be set to False?",
        "source_file": "celery/schedules.py",
        "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
        "ground_truth": {
            "direct_deps": ["celery.schedules.schedule.to_local"],
            "indirect_deps": ["celery.schedules.BaseSchedule.utc_enabled"],
            "implicit_deps": ["celery.app.defaults.enable_utc"],
        },
        "reasoning_hint": "BaseSchedule.utc_enabled is a @cached_property returning self.app.conf.enable_utc. Celery default is enable_utc=True (UTC timezone). When False, to_local_fallback treats naive datetime as local time rather than UTC, which is critical for legacy systems.",
        "source_note": "Blind spot: schedule.to_local -> enable_utc config resolution",
        "case_id": next_id("e", "hard"),
        "entry_symbol": None,
        "entry_file": None,
    },
    # === Type E Hard: celery CLI entry_points autodiscover ===
    {
        "difficulty": "hard",
        "category": "celery_cli_entry_points_autodiscover",
        "failure_type": "Type E",
        "implicit_level": 4,
        "question": "In celery/bin/celery.py, entry_points(group='celery.commands') returns discovered CLI plugins from installed packages. These are registered to @celery.group via with_plugins(_PLUGINS). Describe the complete discovery-to-registration pipeline and how a third-party package would register a custom celery command without modifying Celery source code.",
        "source_file": "celery/bin/celery.py",
        "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
        "ground_truth": {
            "direct_deps": ["celery.bin.celery.celery"],
            "indirect_deps": ["celery.bin.base.CLIContext"],
            "implicit_deps": ["celery.bin.base.CeleryCommand"],
        },
        "reasoning_hint": "importlib.metadata.entry_points reads celery.commands entry point group from installed packages' pkg_resources. click_plugins.with_plugins iterates these and calls celery.add_command(ep.load()). Third-party packages declare entry_points={'celery.commands': ['mycmd=mypackage.commands:cmd']} in setup.py/pyproject.toml.",
        "source_note": "Blind spot: celery CLI entry_points autodiscover via click_plugins",
        "case_id": next_id("e", "hard"),
        "entry_symbol": None,
        "entry_file": None,
    },
    # === Type E Hard: UnpickleableExceptionWrapper serialization roundtrip ===
    {
        "difficulty": "hard",
        "category": "unpickleable_exception_wrapper_roundtrip",
        "failure_type": "Type E",
        "implicit_level": 4,
        "question": "In celery/utils/serialization.py, UnpickleableExceptionWrapper wraps exceptions that cannot be pickled. During deserialization, raise_with_context decides whether to reconstruct the original exception type or fall back to Exception based on specific conditions. What is the complete conditional logic for this decision?",
        "source_file": "celery/utils/serialization.py",
        "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
        "ground_truth": {
            "direct_deps": ["celery.utils.serialization.raise_with_context"],
            "indirect_deps": [
                "celery.utils.serialization.get_pickleable_exception",
                "celery.utils.serialization.create_exception_cls",
            ],
            "implicit_deps": ["celery.utils.serialization.get_pickled_exception"],
        },
        "reasoning_hint": "raise_with_context first tries get_pickled_exception(wrapper). If pickle roundtrip preserves original type and message, it raises the original exception directly. Otherwise, it calls create_exception_cls which reconstructs from exc_type string. Only when the original exception was pickle-compatible is the exact type preserved.",
        "source_note": "Blind spot: UnpickleableExceptionWrapper roundtrip pickle fidelity check",
        "case_id": next_id("e", "hard"),
        "entry_symbol": None,
        "entry_file": None,
    },
    # === Type B Hard: _chord.__init__ header body construction ===
    {
        "difficulty": "hard",
        "category": "chord_init_header_body_constructor",
        "failure_type": "Type B",
        "implicit_level": 3,
        "question": "In celery/canvas.py _chord.__init__, the header and body parameters are lazily converted via _maybe_group(header, app) and maybe_signature(body, app=app). When calling chord([{'task': 'add'}, {'task': 'mul'}], body={'task': 'sum'}), describe the exact signature transformation each parameter undergoes.",
        "source_file": "celery/canvas.py",
        "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
        "ground_truth": {
            "direct_deps": ["celery.canvas._chord.__init__"],
            "indirect_deps": [
                "celery.canvas._maybe_group",
                "celery.canvas.maybe_signature",
            ],
            "implicit_deps": [
                "celery.canvas.Signature.from_dict",
                "celery.canvas.group.from_dict",
            ],
        },
        "reasoning_hint": "_maybe_group converts list [{'task':'add'}, {'task':'mul'}] to a group (internally calling maybe_signature on each dict -> Signature.from_dict). maybe_signature converts dict {'task':'sum'} to a Signature via Signature.from_dict (polymorphic dispatch on subtask_type).",
        "source_note": "Blind spot: _chord.__init__ _maybe_group + maybe_signature dual polymorphic deserialization",
        "case_id": next_id("b", "hard"),
        "entry_symbol": None,
        "entry_file": None,
    },
    # === Type C Hard: GroupResult nested deserialization ===
    {
        "difficulty": "hard",
        "category": "group_result_nested_deserialization",
        "failure_type": "Type C",
        "implicit_level": 4,
        "question": "In celery/result.py GroupResult.__getitem__, when the index is a nested GroupResult tuple form (e.g., [('root_id', (...)), ...]), how does result_from_tuple recursively process this nested structure? How is the parent reference of the inner GroupResult set during deserialization?",
        "source_file": "celery/result.py",
        "source_commit": "b8f85213f45c937670a6a6806ce55326a0eb537f",
        "ground_truth": {
            "direct_deps": ["celery.result.GroupResult.__getitem__"],
            "indirect_deps": [
                "celery.result.result_from_tuple",
                "celery.result.AsyncResult.as_tuple",
            ],
            "implicit_deps": [
                "celery.result.GroupResult.__iter__",
                "celery.result.GroupResult.__len__",
            ],
        },
        "reasoning_hint": "GroupResult.__getitem__ calls result_from_tuple; result_from_tuple parses tuple format (id, parent_tuple). For nested groups, it recursively calls result_from_tuple(parent_tuple) to reconstruct the child GroupResult and sets its parent attribute pointing to the current result object.",
        "source_note": "Blind spot: GroupResult nested deserialization with parent linking",
        "case_id": next_id("c", "hard"),
        "entry_symbol": None,
        "entry_file": None,
    },
]

print(f"\nNew cases defined: {len(new_cases)}")
for c in new_cases:
    print(f"  {c['case_id']}: {c['category']}")

# Append new cases to existing list
cases.extend(new_cases)
print(f"\nTotal after append: {len(cases)}")

# Write back
path.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Written to: {path}")
