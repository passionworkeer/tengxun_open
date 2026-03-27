from __future__ import annotations

import unittest

from finetune.data_guard import validate_record


class ValidateRecordTest(unittest.TestCase):
    def test_rejects_invalid_external_fqn(self) -> None:
        record = {
            "instruction": "test",
            "input": "context",
            "output": (
                "最终依赖：\n"
                '{"direct_deps": ["importlib.import_module"], "indirect_deps": [], "implicit_deps": []}'
            ),
            "difficulty": "medium",
            "verified": True,
            "verify_method": "manual",
        }

        errors = validate_record(record)

        self.assertTrue(
            any("FQN invalid: importlib.import_module" in error for error in errors)
        )

    def test_accepts_internal_ground_truth(self) -> None:
        record = {
            "instruction": "test",
            "input": "context",
            "output": (
                "最终依赖：\n"
                '{"direct_deps": ["celery.app.base.Celery"], "indirect_deps": [], "implicit_deps": []}'
            ),
            "difficulty": "easy",
            "verified": True,
            "verify_method": "manual",
        }

        errors = validate_record(record)

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
