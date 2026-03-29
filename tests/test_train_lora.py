from __future__ import annotations

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
        self.assertEqual(total_rows, 500)
        self.assertGreater(train_rows, 0)
        self.assertGreater(effective_batch, 0)
        self.assertGreater(total_steps, 0)


if __name__ == "__main__":
    unittest.main()
