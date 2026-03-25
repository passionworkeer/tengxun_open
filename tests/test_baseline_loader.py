from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evaluation.baseline import load_eval_cases


class LoadEvalCasesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_loads_legacy_schema_strictly(self) -> None:
        path = self._write_json(
            "legacy.json",
            [
                {
                    "id": "legacy_001",
                    "difficulty": "easy",
                    "category": "re_export",
                    "question": "Where does celery.Celery resolve?",
                    "entry_file": "celery/__init__.py",
                    "entry_symbol": "celery.Celery",
                    "gold_fqns": ["celery.app.base.Celery"],
                }
            ],
        )

        cases = load_eval_cases(path)

        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0].source_schema, "legacy_v1")
        self.assertEqual(cases[0].entry_symbol, "celery.Celery")
        self.assertEqual(cases[0].gold_fqns, ("celery.app.base.Celery",))

    def test_loads_schema_v2_and_flattens_gold_union(self) -> None:
        path = self._write_json(
            "draft_round4.json",
            [
                {
                    "id": "draft_001",
                    "difficulty": "hard",
                    "category": "dynamic_resolution",
                    "failure_type": "Type E",
                    "implicit_level": 5,
                    "question": "Which backend is resolved?",
                    "source_file": "celery/app/backends.py",
                    "ground_truth": {
                        "direct_deps": [
                            "celery.backends.redis.RedisBackend",
                            "celery.app.backends.by_name",
                        ],
                        "indirect_deps": [
                            "celery.app.backends.by_name",
                            "kombu.utils.imports.symbol_by_name",
                        ],
                        "implicit_deps": [
                            "kombu.utils.imports.symbol_by_name",
                        ],
                    },
                }
            ],
            encoding="utf-8-sig",
        )

        cases = load_eval_cases(path)

        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0].source_schema, "schema_v2")
        self.assertEqual(cases[0].entry_file, "celery/app/backends.py")
        self.assertEqual(cases[0].entry_symbol, "")
        self.assertEqual(
            cases[0].gold_fqns,
            (
                "celery.backends.redis.RedisBackend",
                "celery.app.backends.by_name",
                "kombu.utils.imports.symbol_by_name",
            ),
        )
        self.assertEqual(cases[0].failure_type, "Type E")
        self.assertEqual(cases[0].implicit_level, 5)

    def test_rejects_empty_schema_v2_ground_truth(self) -> None:
        path = self._write_json(
            "invalid.json",
            [
                {
                    "id": "draft_002",
                    "difficulty": "medium",
                    "category": "broken",
                    "question": "Broken sample",
                    "source_file": "celery/app/base.py",
                    "ground_truth": {
                        "direct_deps": [],
                        "indirect_deps": [],
                        "implicit_deps": [],
                    },
                }
            ],
        )

        with self.assertRaisesRegex(ValueError, "has no gold dependencies"):
            load_eval_cases(path)

    def _write_json(
        self,
        filename: str,
        payload: object,
        encoding: str = "utf-8",
    ) -> Path:
        path = self.root / filename
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding=encoding)
        return path


if __name__ == "__main__":
    unittest.main()
