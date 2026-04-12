from __future__ import annotations

import unittest

from evaluation.metrics import (
    _safe_divide,
    canonicalize_dependency_symbol,
    compute_layered_dependency_metrics,
    compute_set_metrics,
)


class LayeredDependencyMetricsTest(unittest.TestCase):
    def test_penalizes_wrong_layer_assignment(self) -> None:
        gold = {
            "direct_deps": ["celery.app.base.Celery"],
            "indirect_deps": ["celery.app.base"],
            "implicit_deps": [],
        }
        predicted = {
            "direct_deps": ["celery.app.base"],
            "indirect_deps": ["celery.app.base.Celery"],
            "implicit_deps": [],
        }

        metrics = compute_layered_dependency_metrics(gold, predicted)

        self.assertEqual(metrics.union.f1, 1.0)
        self.assertEqual(metrics.macro_f1, 0.0)
        self.assertEqual(metrics.direct.f1, 0.0)
        self.assertEqual(metrics.indirect.f1, 0.0)
        self.assertEqual(metrics.active_layer_count, 2)
        self.assertEqual(metrics.mislayered_matches, 2)
        self.assertEqual(metrics.mislayer_rate, 1.0)
        self.assertFalse(metrics.exact_layer_match)

    def test_exact_match_stays_exact(self) -> None:
        gold = {
            "direct_deps": ["celery.local.recreate_module"],
            "indirect_deps": [],
            "implicit_deps": ["celery.local.Proxy"],
        }
        predicted = {
            "direct_deps": ["celery.local.recreate_module"],
            "indirect_deps": [],
            "implicit_deps": ["celery.local.Proxy"],
        }

        metrics = compute_layered_dependency_metrics(gold, predicted)

        self.assertEqual(metrics.union.f1, 1.0)
        self.assertEqual(metrics.macro_f1, 1.0)
        self.assertEqual(metrics.active_layer_count, 2)
        self.assertEqual(metrics.mislayer_rate, 0.0)
        self.assertTrue(metrics.exact_layer_match)
        self.assertTrue(metrics.exact_union_match)

    def test_canonicalizes_common_symbol_path_variants(self) -> None:
        gold = {
            "direct_deps": ["celery.app.base.gen_task_name"],
            "indirect_deps": [],
            "implicit_deps": [],
        }
        predicted = {
            "direct_deps": ["celery/app/base.py::gen_task_name"],
            "indirect_deps": [],
            "implicit_deps": [],
        }

        metrics = compute_layered_dependency_metrics(gold, predicted)

        self.assertEqual(metrics.union.f1, 1.0)
        self.assertEqual(
            canonicalize_dependency_symbol("celery/app/base.py::gen_task_name"),
            "celery.app.base.gen_task_name",
        )


# ---------------------------------------------------------------------------
# P2-15: Boundary value tests
# ---------------------------------------------------------------------------

class MetricsSafeDivideBoundaryTest(unittest.TestCase):
    """_safe_divide 边界值测试"""

    def test_zero_denominator_returns_zero(self) -> None:
        self.assertEqual(_safe_divide(0, 0), 0.0)
        self.assertEqual(_safe_divide(5, 0), 0.0)
        self.assertEqual(_safe_divide(100, 0), 0.0)

    def test_zero_numerator_returns_zero(self) -> None:
        self.assertEqual(_safe_divide(0, 5), 0.0)
        self.assertEqual(_safe_divide(0, 1), 0.0)

    def test_normal_division(self) -> None:
        self.assertAlmostEqual(_safe_divide(2, 4), 0.5)
        self.assertAlmostEqual(_safe_divide(3, 6), 0.5)

    def test_negative_values(self) -> None:
        self.assertAlmostEqual(_safe_divide(-2, 4), -0.5)
        self.assertAlmostEqual(_safe_divide(2, -4), -0.5)


class SetMetricsBoundaryTest(unittest.TestCase):
    """compute_set_metrics 边界值测试"""

    def test_all_zero_precision_recall(self) -> None:
        """全零输入 precision=0, recall=0 -> F1 = 0"""
        metrics = compute_set_metrics([], [])
        self.assertEqual(metrics.precision, 0.0)
        self.assertEqual(metrics.recall, 0.0)
        self.assertEqual(metrics.f1, 0.0)

    def test_perfect_match(self) -> None:
        """完美匹配 precision=1, recall=1 -> F1 = 1"""
        gold = ["celery.app.base.Celery", "celery.app.task.Task"]
        predicted = ["celery.app.base.Celery", "celery.app.task.Task"]
        metrics = compute_set_metrics(gold, predicted)
        self.assertEqual(metrics.precision, 1.0)
        self.assertEqual(metrics.recall, 1.0)
        self.assertEqual(metrics.f1, 1.0)

    def test_only_precision_predicted(self) -> None:
        """仅predicted有值，recall=0"""
        gold = ["celery.app.base.Celery"]
        predicted = ["celery.app.task.Task", "celery.app.base.Celery"]
        metrics = compute_set_metrics(gold, predicted)
        self.assertAlmostEqual(metrics.precision, 0.5)
        self.assertEqual(metrics.recall, 1.0)
        self.assertAlmostEqual(metrics.f1, 2 * 0.5 * 1.0 / (0.5 + 1.0))

    def test_only_recall_gold(self) -> None:
        """仅gold有值，precision=0"""
        gold = ["celery.app.task.Task", "celery.app.base.Celery"]
        predicted = ["celery.app.base.Celery"]
        metrics = compute_set_metrics(gold, predicted)
        self.assertEqual(metrics.precision, 1.0)
        self.assertAlmostEqual(metrics.recall, 0.5)
        self.assertAlmostEqual(metrics.f1, 2 * 1.0 * 0.5 / (1.0 + 0.5))

    def test_empty_predicted_all_gold(self) -> None:
        """predicted为空，recall=0"""
        gold = ["celery.app.base.Celery"]
        predicted = []
        metrics = compute_set_metrics(gold, predicted)
        self.assertEqual(metrics.precision, 0.0)
        self.assertEqual(metrics.recall, 0.0)
        self.assertEqual(metrics.f1, 0.0)

    def test_empty_gold_all_predicted(self) -> None:
        """gold为空，predicted非空"""
        gold = []
        predicted = ["celery.app.base.Celery"]
        metrics = compute_set_metrics(gold, predicted)
        self.assertEqual(metrics.precision, 0.0)
        self.assertEqual(metrics.recall, 0.0)
        self.assertEqual(metrics.f1, 0.0)

    def test_partial_overlap(self) -> None:
        """部分重叠"""
        gold = ["a.A", "b.B", "c.C"]
        predicted = ["a.A", "b.B", "d.D"]
        metrics = compute_set_metrics(gold, predicted)
        self.assertAlmostEqual(metrics.precision, 2 / 3)
        self.assertAlmostEqual(metrics.recall, 2 / 3)
        self.assertAlmostEqual(metrics.f1, 2 / 3)


class LayeredMetricsBoundaryTest(unittest.TestCase):
    """compute_layered_dependency_metrics 边界值测试"""

    def test_empty_dependency_lists(self) -> None:
        """空依赖列表场景"""
        gold = {"direct_deps": [], "indirect_deps": [], "implicit_deps": []}
        predicted = {"direct_deps": [], "indirect_deps": [], "implicit_deps": []}
        metrics = compute_layered_dependency_metrics(gold, predicted)
        self.assertEqual(metrics.union.f1, 1.0)
        self.assertEqual(metrics.macro_f1, 1.0)
        self.assertEqual(metrics.active_layer_count, 0)
        self.assertTrue(metrics.exact_layer_match)
        self.assertTrue(metrics.exact_union_match)

    def test_only_direct_layer_active(self) -> None:
        """仅有direct层活跃"""
        gold = {"direct_deps": ["celery.app.base.Celery"], "indirect_deps": [], "implicit_deps": []}
        predicted = {"direct_deps": ["celery.app.base.Celery"], "indirect_deps": [], "implicit_deps": []}
        metrics = compute_layered_dependency_metrics(gold, predicted)
        self.assertEqual(metrics.active_layer_count, 1)
        self.assertEqual(metrics.macro_f1, 1.0)

    def test_only_indirect_layer_active(self) -> None:
        """仅有indirect层活跃"""
        gold = {"direct_deps": [], "indirect_deps": ["celery.backends.redis"], "implicit_deps": []}
        predicted = {"direct_deps": [], "indirect_deps": ["celery.backends.redis"], "implicit_deps": []}
        metrics = compute_layered_dependency_metrics(gold, predicted)
        self.assertEqual(metrics.active_layer_count, 1)
        self.assertEqual(metrics.macro_f1, 1.0)

    def test_only_implicit_layer_active(self) -> None:
        """仅有implicit层活跃"""
        gold = {"direct_deps": [], "indirect_deps": [], "implicit_deps": ["celery.local.Proxy"]}
        predicted = {"direct_deps": [], "indirect_deps": [], "implicit_deps": ["celery.local.Proxy"]}
        metrics = compute_layered_dependency_metrics(gold, predicted)
        self.assertEqual(metrics.active_layer_count, 1)
        self.assertEqual(metrics.macro_f1, 1.0)

    def test_gold_empty_predicted_full(self) -> None:
        """gold空，predicted有值"""
        gold = {"direct_deps": [], "indirect_deps": [], "implicit_deps": []}
        predicted = {
            "direct_deps": ["celery.app.base.Celery"],
            "indirect_deps": ["celery.app.task"],
            "implicit_deps": ["celery.local.Proxy"],
        }
        metrics = compute_layered_dependency_metrics(gold, predicted)
        self.assertEqual(metrics.union.f1, 0.0)
        self.assertEqual(metrics.union.precision, 0.0)
        self.assertEqual(metrics.union.recall, 0.0)

    def test_gold_full_predicted_empty(self) -> None:
        """gold有值，predicted空"""
        gold = {
            "direct_deps": ["celery.app.base.Celery"],
            "indirect_deps": [],
            "implicit_deps": [],
        }
        predicted = {"direct_deps": [], "indirect_deps": [], "implicit_deps": []}
        metrics = compute_layered_dependency_metrics(gold, predicted)
        self.assertEqual(metrics.union.f1, 0.0)
        self.assertEqual(metrics.union.precision, 0.0)
        self.assertEqual(metrics.union.recall, 0.0)

    def test_none_inputs_handled(self) -> None:
        """None输入处理"""
        metrics = compute_layered_dependency_metrics(None, None)
        self.assertEqual(metrics.union.f1, 1.0)
        self.assertEqual(metrics.macro_f1, 1.0)
        self.assertEqual(metrics.active_layer_count, 0)


if __name__ == "__main__":
    unittest.main()
