"""
LoRA微调训练模块

功能：
1. 训练配置管理（TOML配置文件支持）
2. 命令行参数解析
3. 数据集预检

训练后端尚未实现，当前仅为脚手架代码。
"""

from __future__ import annotations

import argparse
import json
import tomllib
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TrainingConfig:
    """
    训练配置

    基于Qwen3.5-9B的LoRA微调配置。
    """

    model_name: str = "Qwen3.5-9B"
    dataset_path: str = "data/finetune_dataset_500.jsonl"
    output_dir: str = "artifacts/lora/qwen3.5-9b"
    learning_rate: float = 2e-4
    batch_size: int = 2
    num_epochs: int = 3
    lora_r: int = 16  # LoRA秩
    lora_alpha: int = 32  # LoRA缩放因子
    lora_dropout: float = 0.05
    # 目标模块：Qwen的attention参数
    target_modules: tuple[str, ...] = ("q_proj", "k_proj", "v_proj", "o_proj")
    validation_split: float = 0.1  # 10%验证集
    early_stopping_patience: int = 3  # 早停耐心值
    max_seq_length: int = 2048  # 最大序列长度
    gradient_accumulation_steps: int = 8  # 梯度累积
    gradient_checkpointing: bool = True  # 梯度检查点，防OOM
    load_in_4bit: bool = True  # 4bit量化加载
    eval_steps: int = 50  # 评估间隔
    metric_for_best_model: str = "eval_f1"  # 最佳模型指标


CONFIG_FIELD_NAMES = {field.name for field in fields(TrainingConfig)}


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器"""
    parser = argparse.ArgumentParser(description="LoRA training scaffold.")
    parser.add_argument("--config", type=Path, help="Optional TOML config file.")
    parser.add_argument("--model-name")
    parser.add_argument("--dataset-path")
    parser.add_argument("--output-dir")
    parser.add_argument("--learning-rate", type=float)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--num-epochs", type=int)
    parser.add_argument("--lora-r", type=int)
    parser.add_argument("--lora-alpha", type=int)
    parser.add_argument("--lora-dropout", type=float)
    parser.add_argument("--target-modules", nargs="+")
    parser.add_argument("--validation-split", type=float)
    parser.add_argument("--early-stopping-patience", type=int)
    parser.add_argument("--max-seq-length", type=int)
    parser.add_argument("--gradient-accumulation-steps", type=int)
    parser.add_argument("--eval-steps", type=int)
    parser.add_argument("--metric-for-best-model")
    parser.add_argument(
        "--gradient-checkpointing",
        dest="gradient_checkpointing",
        action="store_true",
        help="Enable gradient checkpointing.",
    )
    parser.add_argument(
        "--no-gradient-checkpointing",
        dest="gradient_checkpointing",
        action="store_false",
        help="Disable gradient checkpointing.",
    )
    parser.add_argument(
        "--load-in-4bit",
        dest="load_in_4bit",
        action="store_true",
        help="Enable 4-bit loading for LoRA.",
    )
    parser.add_argument(
        "--no-load-in-4bit",
        dest="load_in_4bit",
        action="store_false",
        help="Disable 4-bit loading.",
    )
    parser.set_defaults(gradient_checkpointing=None, load_in_4bit=None)
    return parser


def load_config_file(path: Path) -> dict[str, Any]:
    """
    加载TOML配置文件

    Args:
        path: 配置文件路径

    Returns:
        配置字典
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    if path.suffix.lower() != ".toml":
        raise ValueError(f"Only TOML configs are supported right now: {path}")

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    unknown = sorted(set(data) - CONFIG_FIELD_NAMES)
    if unknown:
        raise ValueError(f"Unknown config keys: {unknown}")
    return data


def build_config(args: argparse.Namespace) -> TrainingConfig:
    """
    构建训练配置

    配置优先级：默认配置 -> TOML文件 -> 命令行参数

    Args:
        args: 解析后的命令行参数

    Returns:
        TrainingConfig对象
    """
    values = asdict(TrainingConfig())

    if args.config is not None:
        values.update(load_config_file(args.config))

    cli_overrides = {
        "model_name": args.model_name,
        "dataset_path": args.dataset_path,
        "output_dir": args.output_dir,
        "learning_rate": args.learning_rate,
        "batch_size": args.batch_size,
        "num_epochs": args.num_epochs,
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha,
        "lora_dropout": args.lora_dropout,
        "target_modules": tuple(args.target_modules)
        if args.target_modules is not None
        else None,
        "validation_split": args.validation_split,
        "early_stopping_patience": args.early_stopping_patience,
        "max_seq_length": args.max_seq_length,
        "gradient_accumulation_steps": args.gradient_accumulation_steps,
        "gradient_checkpointing": args.gradient_checkpointing,
        "load_in_4bit": args.load_in_4bit,
        "eval_steps": args.eval_steps,
        "metric_for_best_model": args.metric_for_best_model,
    }
    for key, value in cli_overrides.items():
        if value is not None:
            values[key] = value

    return TrainingConfig(
        **{
            **values,
            "target_modules": tuple(values["target_modules"]),
        }
    )


def main() -> int:
    """
    主入口函数

    验证数据集存在且非空，输出配置信息。
    训练后端尚未实现。
    """
    args = build_parser().parse_args()
    config = build_config(args)

    dataset_path = Path(config.dataset_path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")
    if not any(
        line.strip()
        for line in dataset_path.read_text(encoding="utf-8-sig").splitlines()
    ):
        raise ValueError(
            f"Dataset is empty: {dataset_path}. Generate validated records before starting training."
        )

    Path(config.output_dir).mkdir(parents=True, exist_ok=True)
    print(json.dumps(asdict(config), indent=2, ensure_ascii=False))
    raise SystemExit(
        "Training scaffold only: config parsing is wired, but the actual trainer backend is not implemented yet."
    )


if __name__ == "__main__":
    raise SystemExit(main())
