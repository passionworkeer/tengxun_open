from __future__ import annotations

import unittest

from evaluation.metrics import (
    canonicalize_dependency_symbol,
    compute_layered_dependency_metrics,
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


if __name__ == "__main__":
    unittest.main()
