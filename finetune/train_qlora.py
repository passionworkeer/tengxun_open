from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class TrainingConfig:
    model_name: str
    dataset_path: str
    output_dir: str
    learning_rate: float
    batch_size: int
    num_epochs: int
    lora_r: int
    lora_alpha: int
    validation_split: float
    early_stopping_patience: int


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QLoRA training scaffold.")
    parser.add_argument("--model-name", default="Qwen2.5-Coder-7B")
    parser.add_argument("--dataset-path", default="data/finetune_dataset.jsonl")
    parser.add_argument("--output-dir", default="artifacts/qlora")
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--num-epochs", type=int, default=3)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--validation-split", type=float, default=0.1)
    parser.add_argument("--early-stopping-patience", type=int, default=2)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = TrainingConfig(
        model_name=args.model_name,
        dataset_path=args.dataset_path,
        output_dir=args.output_dir,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        num_epochs=args.num_epochs,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        validation_split=args.validation_split,
        early_stopping_patience=args.early_stopping_patience,
    )

    Path(config.output_dir).mkdir(parents=True, exist_ok=True)
    print(json.dumps(asdict(config), indent=2, ensure_ascii=False))
    print("TODO: wire this scaffold to the actual trainer and logging backend.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

