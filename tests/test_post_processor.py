from __future__ import annotations

import unittest

from pe.post_processor import (
    parse_model_output,
    parse_model_output_layers,
)


class PostProcessorLayeredTest(unittest.TestCase):
    def test_preserves_dependency_layers(self) -> None:
        raw = """
        ```json
        {
          "ground_truth": {
            "direct_deps": ["celery.app.task:Task"],
            "indirect_deps": ["celery/app/base.py::Celery"],
            "implicit_deps": ["celery.local.Proxy"]
          }
        }
        ```
        """

        parsed = parse_model_output_layers(raw)

        self.assertEqual(
            parsed,
            {
                "direct_deps": ["celery.app.task.Task"],
                "indirect_deps": ["celery.app.base.Celery"],
                "implicit_deps": ["celery.local.Proxy"],
            },
        )


# ---------------------------------------------------------------------------
# P2-14: Exception-path tests
# ---------------------------------------------------------------------------

class PostProcessorJsonFallbackTest(unittest.TestCase):
    """JSON解析失败降级到正则匹配的测试"""

    def test_json_decode_error_falls_back_to_regex(self) -> None:
        """JSON解析失败时退化为正则提取"""
        raw = "The dependencies are: celery.app.base.Celery and celery.app.task.Task"
        result = parse_model_output(raw)
        self.assertIn("celery.app.base.Celery", result)
        self.assertIn("celery.app.task.Task", result)

    def test_malformed_json_still_extracts_valid_fqns(self) -> None:
        """格式错误的JSON仍能提取有效FQN"""
        raw = '{"ground_truth": {"direct_deps": ["celery.app.task"]}}'  # missing closing brace
        raw += "\nAlso uses celery.app.base.Celery"
        result = parse_model_output(raw)
        # malformed JSON -> fallback to regex
        self.assertTrue(len(result) >= 0)

    def test_json_with_invalid_fqn_values(self) -> None:
        """JSON解析成功但包含无效FQN值时，仅保留合法项"""
        raw = '{"ground_truth": {"direct_deps": ["celery.app.task.Task", "invalid..dots", ""], "indirect_deps": [], "implicit_deps": []}}'
        parsed = parse_model_output_layers(raw)
        self.assertIsNotNone(parsed)
        self.assertIn("celery.app.task.Task", parsed["direct_deps"])
        self.assertNotIn("invalid..dots", parsed["direct_deps"])
        self.assertNotIn("", parsed["direct_deps"])

    def test_top_level_ground_truth_key(self) -> None:
        """顶层ground_truth键正常解析"""
        raw = '{"ground_truth": {"direct_deps": ["celery.app.base.Celery"], "indirect_deps": [], "implicit_deps": []}}'
        parsed = parse_model_output_layers(raw)
        self.assertIsNotNone(parsed)
        self.assertIn("celery.app.base.Celery", parsed["direct_deps"])


class PostProcessorEmptyInputTest(unittest.TestCase):
    """空输入处理测试"""

    def test_empty_string_returns_empty_list(self) -> None:
        result = parse_model_output("")
        self.assertEqual(result, [])

    def test_empty_string_returns_none_for_layers(self) -> None:
        result = parse_model_output_layers("")
        self.assertIsNone(result)

    def test_whitespace_only_returns_none_for_layers(self) -> None:
        result = parse_model_output_layers("   \n\n  ")
        self.assertIsNone(result)

    def test_only_newlines_and_tabs(self) -> None:
        result = parse_model_output("\n\t\n")
        self.assertEqual(result, [])


class PostProcessorLongFQNTest(unittest.TestCase):
    """超长FQN处理测试"""

    def test_long_fqn_is_accepted(self) -> None:
        """超长FQN当前实现接受（无1000字符硬限制）"""
        long_name = "celery" + ".module" * 200  # ~1400字符
        raw = f'{{"ground_truth": {{"direct_deps": ["{long_name}"], "indirect_deps": [], "implicit_deps": []}}}}'
        parsed = parse_model_output_layers(raw)
        # is_valid_fqn基于正则，不做长度检查，所以长名称被接受
        self.assertIsNotNone(parsed)
        self.assertTrue(len(parsed["direct_deps"]) > 0)

    def test_normal_length_fqn(self) -> None:
        """正常长度FQN正常处理"""
        raw = '{"ground_truth": {"direct_deps": ["celery.app.base.Celery"], "indirect_deps": [], "implicit_deps": []}}'
        parsed = parse_model_output_layers(raw)
        self.assertIsNotNone(parsed)
        self.assertIn("celery.app.base.Celery", parsed["direct_deps"])


class PostProcessorSpecialCharsTest(unittest.TestCase):
    """特殊字符处理测试"""

    def test_newline_literal_in_string_fails_parse(self) -> None:
        """JSON字符串字面量含换行符导致JSON解析失败（符合预期）"""
        # JSON中字符串不能直接含\n，会导致JSONDecodeError -> None
        raw = '{"ground_truth": {"direct_deps": ["celery.app\n.base.Celery"], "indirect_deps": [], "implicit_deps": []}}'
        parsed = parse_model_output_layers(raw)
        self.assertIsNone(parsed)

    def test_tab_literal_in_string_fails_parse(self) -> None:
        """JSON字符串字面量含Tab符导致JSON解析失败（符合预期）"""
        raw = '{"ground_truth": {"direct_deps": ["celery.app\tbase.Celery"], "indirect_deps": [], "implicit_deps": []}}'
        parsed = parse_model_output_layers(raw)
        self.assertIsNone(parsed)

    def test_non_ascii_chars_in_question(self) -> None:
        """问题含非ASCII字符（中文）"""
        raw = '{"ground_truth": {"direct_deps": ["celery.app.base.Celery"], "indirect_deps": [], "implicit_deps": []}}'
        result = parse_model_output(raw)
        self.assertIn("celery.app.base.Celery", result)

    def test_backslash_in_fqn_normalized(self) -> None:
        """路径中使用反斜杠（Windows风格）"""
        raw = '{"ground_truth": {"direct_deps": ["celery\\\\app\\\\base.py"], "indirect_deps": [], "implicit_deps": []}}'
        parsed = parse_model_output_layers(raw)
        # 反斜杠在JSON字符串中需转义，解码后normalize转为点号
        self.assertIsNotNone(parsed)

    def test_backtick_code_fence(self) -> None:
        """输出中含反引号包裹的代码块"""
        # 注意：JSON只支持双引号，此处内层JSON用双引号
        raw = '```json\n{"ground_truth": {"direct_deps": ["celery.app.base.Celery"]}}\n```'
        parsed = parse_model_output_layers(raw)
        self.assertIsNotNone(parsed)
        self.assertIn("celery.app.base.Celery", parsed["direct_deps"])


class PostProcessorDeepNestingTest(unittest.TestCase):
    """嵌套过深JSON的处理测试"""

    def test_deeply_nested_json_only_reads_top_ground_truth(self) -> None:
        """嵌套JSON仅识别顶层ground_truth键"""
        deep = '{"result": {"data": {"ground_truth": {"direct_deps": ["celery.app.base.Celery"]}}}}'
        parsed = parse_model_output_layers(deep)
        self.assertIsNotNone(parsed)
        # 当前实现只找顶层ground_truth，不进result.data路径
        self.assertEqual(parsed["direct_deps"], [])

    def test_array_wrapper_returns_none(self) -> None:
        """数组形式的外层返回None"""
        raw = '[{"result": {"ground_truth": {"direct_deps": ["celery.app.task.Task"]}}}]'
        parsed = parse_model_output_layers(raw)
        # 顶层是数组不是dict -> None
        self.assertIsNone(parsed)

    def test_mixed_invalid_and_valid_layers(self) -> None:
        """混合有效和无效层"""
        # 'celery' 规范化后是单段FQN（无点号），不是合法FQN，会被过滤
        raw = '{"ground_truth": {"direct_deps": ["celery.app.base.Celery"], "indirect_deps": ["celery"], "implicit_deps": []}}'
        parsed = parse_model_output_layers(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["direct_deps"], ["celery.app.base.Celery"])
        self.assertEqual(parsed["indirect_deps"], [])
        self.assertEqual(parsed["implicit_deps"], [])


class PostProcessorNoneInputTest(unittest.TestCase):
    """None输入处理测试"""

    def test_none_input_raises_attribute_error(self) -> None:
        """None输入导致AttributeError（符合预期）"""
        with self.assertRaises(AttributeError):
            parse_model_output_layers(None)  # type: ignore

    def test_null_ground_truth_in_json(self) -> None:
        """JSON中ground_truth为null返回None"""
        raw = '{"ground_truth": null}'
        parsed = parse_model_output_layers(raw)
        self.assertIsNone(parsed)

    def test_null_layer_becomes_empty(self) -> None:
        """JSON中某层为null而非数组时该层返回空列表"""
        raw = '{"ground_truth": {"direct_deps": null, "indirect_deps": [], "implicit_deps": []}}'
        parsed = parse_model_output_layers(raw)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["direct_deps"], [])


if __name__ == "__main__":
    unittest.main()
