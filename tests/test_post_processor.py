from __future__ import annotations

import unittest

from pe.post_processor import parse_model_output_layers


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


if __name__ == "__main__":
    unittest.main()
