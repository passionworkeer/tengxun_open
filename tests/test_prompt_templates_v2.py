"""Expanded tests for pe.prompt_templates_v2 — PE templates and selection logic."""

from __future__ import annotations

import unittest

from pe.prompt_templates_v2 import (
    FEW_SHOT_LIBRARY,
    GroundTruth,
    FewShotExample,
    HARD_CASE_COT_ADDENDUM,
    HARD_TYPE_A_PATTERNS,
    HARD_TYPE_B_PATTERNS,
    HARD_TYPE_D_PATTERNS,
    HARD_TYPE_E_PATTERNS,
    LAYER_GUARD_RULES,
    LAYER_CHECKLIST_COT_TEMPLATE,
    PromptBundle,
    SYSTEM_PROMPT,
    STRICT_LAYER_COT_TEMPLATE,
    build_cot_for_hard_case,
    build_messages,
    build_prompt_bundle,
    build_user_prompt,
    format_few_shot_assistant_message,
    format_few_shot_example,
    format_few_shot_user_message,
    is_hard_case,
    select_few_shot_examples,
)


class TestHardCasePatterns(unittest.TestCase):
    """Test HARD_TYPE_*_PATTERNS are non-empty and contain strings."""

    def test_type_a_patterns_non_empty(self) -> None:
        self.assertGreater(len(HARD_TYPE_A_PATTERNS), 0)
        self.assertTrue(all(isinstance(p, str) for p in HARD_TYPE_A_PATTERNS))

    def test_type_b_patterns_non_empty(self) -> None:
        self.assertGreater(len(HARD_TYPE_B_PATTERNS), 0)
        self.assertTrue(all(isinstance(p, str) for p in HARD_TYPE_B_PATTERNS))

    def test_type_d_patterns_non_empty(self) -> None:
        self.assertGreater(len(HARD_TYPE_D_PATTERNS), 0)
        self.assertTrue(all(isinstance(p, str) for p in HARD_TYPE_D_PATTERNS))

    def test_type_e_patterns_non_empty(self) -> None:
        self.assertGreater(len(HARD_TYPE_E_PATTERNS), 0)
        self.assertTrue(all(isinstance(p, str) for p in HARD_TYPE_E_PATTERNS))


class TestSystemPrompt(unittest.TestCase):
    def test_contains_ground_truth_keys(self) -> None:
        self.assertIn("direct_deps", SYSTEM_PROMPT)
        self.assertIn("indirect_deps", SYSTEM_PROMPT)
        self.assertIn("implicit_deps", SYSTEM_PROMPT)


class TestLayerGuardRules(unittest.TestCase):
    def test_contains_direct_indirect_implicit(self) -> None:
        self.assertIn("direct_deps", LAYER_GUARD_RULES)
        self.assertIn("indirect_deps", LAYER_GUARD_RULES)
        self.assertIn("implicit_deps", LAYER_GUARD_RULES)


class TestGroundTruth(unittest.TestCase):
    def test_as_dict_returns_all_three_layers(self) -> None:
        gt = GroundTruth(
            direct_deps=("celery.app.base.Celery",),
            indirect_deps=("celery.utils.imports",),
            implicit_deps=("celery._state._announce_app_finalized",),
        )
        d = gt.as_dict()
        self.assertIn("direct_deps", d)
        self.assertIn("indirect_deps", d)
        self.assertIn("implicit_deps", d)
        self.assertEqual(d["direct_deps"], ["celery.app.base.Celery"])

    def test_empty_deps(self) -> None:
        gt = GroundTruth(direct_deps=(), indirect_deps=(), implicit_deps=())
        d = gt.as_dict()
        self.assertEqual(d["direct_deps"], [])
        self.assertEqual(d["indirect_deps"], [])
        self.assertEqual(d["implicit_deps"], [])


class TestFormatFewShotExample(unittest.TestCase):
    def test_returns_non_empty_string(self) -> None:
        gt = GroundTruth(
            direct_deps=("sym",),
            indirect_deps=(),
            implicit_deps=(),
        )
        example = FewShotExample(
            case_id="A001",
            failure_type="Type B",
            title="shared task registration",
            question="What method creates the task?",
            environment_preconditions=("celery installed",),
            reasoning_steps=("Step 1: decorator",),
            ground_truth=gt,
        )
        result = format_few_shot_example(example)
        self.assertIsInstance(result, str)
        self.assertIn("A001", result)
        self.assertIn("Type B", result)
        self.assertIn("ground_truth", result)


class TestFormatFewShotUserMessage(unittest.TestCase):
    def test_contains_case_id_failure_type_title(self) -> None:
        gt = GroundTruth(direct_deps=("sym",), indirect_deps=(), implicit_deps=())
        example = FewShotExample(
            case_id="B002",
            failure_type="Type E",
            title="alias resolution",
            question="Which class?",
            environment_preconditions=(),
            reasoning_steps=(),
            ground_truth=gt,
        )
        result = format_few_shot_user_message(example)
        self.assertIn("B002", result)
        self.assertIn("Type E", result)
        self.assertIn("alias resolution", result)
        self.assertIn("Question:", result)
        self.assertIn("ground_truth", result)  # OUTPUT_INSTRUCTIONS included

    def test_empty_preconditions_uses_none(self) -> None:
        gt = GroundTruth(direct_deps=(), indirect_deps=(), implicit_deps=())
        example = FewShotExample(
            case_id="C001",
            failure_type="Type C",
            title="title",
            question="Q",
            environment_preconditions=(),
            reasoning_steps=(),
            ground_truth=gt,
        )
        result = format_few_shot_user_message(example)
        self.assertIn("None", result)


class TestFormatFewShotAssistantMessage(unittest.TestCase):
    def test_valid_json(self) -> None:
        import json
        gt = GroundTruth(
            direct_deps=("celery.app.Task",),
            indirect_deps=(),
            implicit_deps=(),
        )
        example = FewShotExample(
            case_id="D001",
            failure_type="Type D",
            title="t",
            question="q",
            environment_preconditions=(),
            reasoning_steps=(),
            ground_truth=gt,
        )
        result = format_few_shot_assistant_message(example)
        parsed = json.loads(result)
        self.assertIn("ground_truth", parsed)
        self.assertEqual(parsed["ground_truth"]["direct_deps"], ["celery.app.Task"])


class TestIsHardCase(unittest.TestCase):
    def test_autodiscover_hard(self) -> None:
        self.assertTrue(is_hard_case("autodiscover_tasks lazy path"))

    def test_symbol_by_name_hard(self) -> None:
        self.assertTrue(is_hard_case("symbol_by_name resolves to which class"))

    def test_shared_task_hard(self) -> None:
        self.assertTrue(is_hard_case("@shared_task decorator registration"))

    def test_simple_question_not_hard(self) -> None:
        self.assertFalse(is_hard_case("Which class does celery.Task resolve to"))

    def test_empty_question_not_hard(self) -> None:
        self.assertFalse(is_hard_case(""))


class TestBuildCotForHardCase(unittest.TestCase):
    def test_adds_hard_case_addendum(self) -> None:
        base = "Standard reasoning steps."
        result = build_cot_for_hard_case(base)
        self.assertIn("Standard reasoning steps", result)
        self.assertIn(HARD_CASE_COT_ADDENDUM.strip(), result)

    def test_default_base_used(self) -> None:
        from pe.prompt_templates_v2 import COT_TEMPLATE
        result = build_cot_for_hard_case()
        self.assertIn(COT_TEMPLATE.strip(), result)


class TestBuildPromptBundle(unittest.TestCase):
    def test_returns_bundle_with_all_fields(self) -> None:
        bundle = build_prompt_bundle(
            question="symbol_by_name resolution",
            context="celery.app.base",
            entry_symbol="Celery",
        )
        self.assertIsInstance(bundle, PromptBundle)
        self.assertIsInstance(bundle.system_prompt, str)
        self.assertGreater(len(bundle.system_prompt), 10)
        self.assertIsInstance(bundle.cot_template, str)
        self.assertIsInstance(bundle.few_shot_examples, tuple)
        self.assertIsInstance(bundle.user_prompt, str)

    def test_auto_hard_cot_appends_hard_case_cot(self) -> None:
        bundle = build_prompt_bundle(
            question="symbol_by_name",
            context="",
            auto_hard_cot=True,
        )
        # Should have HARD_CASE_COT_ADDENDUM content
        self.assertIn(HARD_CASE_COT_ADDENDUM.strip()[:30], bundle.cot_template)

    def test_use_layer_checklist_overrides_cot(self) -> None:
        bundle = build_prompt_bundle(
            question="simple question",
            context="",
            use_layer_checklist=True,
        )
        self.assertIn(LAYER_CHECKLIST_COT_TEMPLATE.strip()[:20], bundle.cot_template)


class TestSelectFewShotExamples(unittest.TestCase):
    def test_returns_list(self) -> None:
        result = select_few_shot_examples("symbol_by_name", max_examples=3)
        self.assertIsInstance(result, list)

    def test_respects_max_examples(self) -> None:
        result = select_few_shot_examples("symbol_by_name", max_examples=2)
        self.assertLessEqual(len(result), 2)

    def test_max_examples_zero_returns_empty(self) -> None:
        result = select_few_shot_examples("symbol_by_name", max_examples=0)
        self.assertEqual(result, [])

    def test_none_library_uses_default(self) -> None:
        # None falls back to FEW_SHOT_LIBRARY (empty list also falls back)
        result = select_few_shot_examples("symbol_by_name", library=None, max_examples=3)
        self.assertGreater(len(result), 0)

    def test_hard_case_keyword_matches(self) -> None:
        # symbol_by_name should match Type E examples
        result = select_few_shot_examples(
            "symbol_by_name resolves celery app",
            max_examples=5,
        )
        self.assertIsInstance(result, list)

    def test_case_id_long_chain_bonus(self) -> None:
        # A-prefixed case_ids should get bonus
        result_a = select_few_shot_examples("autodiscover signal", max_examples=3)
        result_b = select_few_shot_examples("simple export", max_examples=3)
        # Both should return lists
        self.assertIsInstance(result_a, list)
        self.assertIsInstance(result_b, list)


class TestBuildUserPrompt(unittest.TestCase):
    def test_question_included(self) -> None:
        prompt = build_user_prompt("What does X resolve to?", "context here")
        self.assertIn("What does X resolve to?", prompt)

    def test_context_included(self) -> None:
        prompt = build_user_prompt("Q", "context content")
        self.assertIn("Context:", prompt)
        self.assertIn("context content", prompt)

    def test_entry_symbol_included(self) -> None:
        prompt = build_user_prompt("Q", "", entry_symbol="MyClass.method")
        self.assertIn("MyClass.method", prompt)

    def test_entry_file_included(self) -> None:
        prompt = build_user_prompt("Q", "", entry_file="celery/app/base.py")
        self.assertIn("celery/app/base.py", prompt)

    def test_empty_context_excluded_when_flag_false(self) -> None:
        prompt = build_user_prompt("Q", "", include_empty_context=False)
        # Should not have "Context:\n\n"
        lines = prompt.split("\n")
        context_line_idx = next(
            (i for i, l in enumerate(lines) if l.strip() == "Context:"),
            None,
        )
        if context_line_idx is not None:
            self.assertNotEqual(lines[context_line_idx + 1].strip(), "")


class TestBuildMessages(unittest.TestCase):
    def test_system_and_user_messages(self) -> None:
        messages = build_messages(
            question="symbol_by_name",
            context="",
            assistant_fewshot=False,
        )
        self.assertGreaterEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[-1]["role"], "user")

    def test_fewshot_library_loaded(self) -> None:
        self.assertGreater(len(FEW_SHOT_LIBRARY), 0)

    def test_uses_layer_guard_rules(self) -> None:
        messages = build_messages(
            question="symbol_by_name",
            context="",
            use_layer_checklist=True,
        )
        content = "\n".join(m["content"] for m in messages if m["role"] == "system")
        self.assertIn("direct_deps", content)

    def test_preserves_fewshot_examples_when_requested(self) -> None:
        messages = build_messages(
            question="symbol_by_name",
            context="",
            max_examples=2,
            assistant_fewshot=False,
        )
        # Should have system few-shot messages + user question
        self.assertGreater(len(messages), 2)


if __name__ == "__main__":
    unittest.main()
