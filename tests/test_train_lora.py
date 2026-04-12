from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from finetune.train_lora import estimate_total_steps, load_simple_yaml, resolve_dataset_path


class TrainLoraPreflightTest(unittest.TestCase):
    def test_resolve_dataset_path_prefers_repo_data_dir(self) -> None:
        config = load_simple_yaml(Path("configs/train_config_strict_replay_20260329.yaml"))
        dataset_path = resolve_dataset_path(config)

        self.assertIsNotNone(dataset_path)
        self.assertEqual(dataset_path, Path("data/finetune_dataset_500_strict.jsonl"))
        self.assertTrue(dataset_path.exists())

    def test_estimate_total_steps_available_for_strict_replay_config(self) -> None:
        config = load_simple_yaml(Path("configs/train_config_strict_replay_20260329.yaml"))
        estimate = estimate_total_steps(config)

        self.assertIsNotNone(estimate)
        total_rows, train_rows, effective_batch, total_steps = estimate
        self.assertEqual(total_rows, 497)
        self.assertGreater(train_rows, 0)
        self.assertGreater(effective_batch, 0)
        self.assertGreater(total_steps, 0)


class LoadSimpleYamlTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_yaml(self, filename: str, content: str) -> Path:
        path = self.root / filename
        path.write_text(content, encoding="utf-8")
        return path

    def test_parses_simple_key_value(self) -> None:
        path = self._write_yaml(
            "simple.yaml",
            "key1: value1\nkey2: 42\nkey3: true\nkey4: false\n",
        )
        config = load_simple_yaml(path)

        self.assertEqual(config["key1"], "value1")
        self.assertEqual(config["key2"], 42)
        self.assertEqual(config["key3"], True)
        self.assertEqual(config["key4"], False)

    def test_handles_comments(self) -> None:
        path = self._write_yaml(
            "with_comments.yaml",
            "# This is a comment\nkey1: value1  # inline comment\n# Another comment\nkey2: value2\n",
        )
        config = load_simple_yaml(path)

        self.assertEqual(config["key1"], "value1")
        self.assertEqual(config["key2"], "value2")

    def test_handles_multiline_literal_string(self) -> None:
        path = self._write_yaml(
            "multiline.yaml",
            "prompt: |\n  line1\n  line2\n  line3\n",
        )
        config = load_simple_yaml(path)

        self.assertEqual(config["prompt"], "line1\nline2\nline3\n")

    def test_handles_multiline_folded_string(self) -> None:
        path = self._write_yaml(
            "folded.yaml",
            "description: >\n  This is a long\n  description that\n  wraps across lines.\n",
        )
        config = load_simple_yaml(path)

        self.assertEqual(config["description"], "This is a long description that wraps across lines.\n")

    def test_handles_nested_structure(self) -> None:
        path = self._write_yaml(
            "nested.yaml",
            "outer:\n  inner1: value1\n  inner2: 100\n",
        )
        config = load_simple_yaml(path)

        self.assertIsInstance(config["outer"], dict)
        self.assertEqual(config["outer"]["inner1"], "value1")
        self.assertEqual(config["outer"]["inner2"], 100)

    def test_handles_list(self) -> None:
        path = self._write_yaml(
            "list.yaml",
            "items:\n  - item1\n  - item2\n  - item3\n",
        )
        config = load_simple_yaml(path)

        self.assertIsInstance(config["items"], list)
        self.assertEqual(config["items"], ["item1", "item2", "item3"])

    def test_handles_quoted_values(self) -> None:
        path = self._write_yaml(
            "quoted.yaml",
            'single: \'single quoted\'\ndouble: "double quoted"\n',
        )
        config = load_simple_yaml(path)

        self.assertEqual(config["single"], "single quoted")
        self.assertEqual(config["double"], "double quoted")


if __name__ == "__main__":
    unittest.main()
