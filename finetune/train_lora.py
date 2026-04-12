"""
正式 LoRA 微调训练入口。

默认对接仓库内已经落盘的 LLaMA-Factory YAML 配置，
让 `make train` 可以直接复现实验入口，而不是停在脚手架。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import random
import shutil
import subprocess
from pathlib import Path

try:
    import yaml as _yaml
except ImportError:
    _yaml = None


DEFAULT_CONFIG = Path("configs/strict_clean_20260329.yaml")
DEFAULTS_CONFIG = Path("configs/config_defaults.yaml")
DEFAULT_LAUNCHER = os.environ.get("LLAMAFACTORY_CLI", "llamafactory-cli")
REFERENCE_LOG = Path("logs/strict_clean_20260329.train.log")
DATASET_INFO = Path("dataset_info.json")
DATA_DIR = Path("data")


# ---------------------------------------------------------------------------
# P2-17: Weighted sampling for Hard-case oversampling
# ---------------------------------------------------------------------------

DEFAULT_SAMPLING_WEIGHTS = {"easy": 0.2, "medium": 0.3, "hard": 0.5}


def weighted_sampling(
    dataset: list[dict[str, object]],
    weights: dict[str, float] | None = None,
    seed: int | None = None,
) -> list[dict[str, object]]:
    """
    对数据集进行加权采样，Hard样本获得更高权重。

    策略：
    1. 按difficulty字段将样本分类为 easy/medium/hard。
    2. 统计各类数量，按目标权重计算重采样倍数。
    3. 对Hard样本重复采样到目标比例，Easy/Medium样本相应缩减。
    4. 打乱最终顺序返回。

    Args:
        dataset: 原始数据集，每条记录需包含 "difficulty" 字段。
        weights: 目标分布权重，默认 {"easy": 0.2, "medium": 0.3, "hard": 0.5}。
        seed: 可选随机种子，保证可复现。

    Returns:
        重采样后的数据集列表。

    Raises:
        ValueError: 权重之和不等于1.0，或存在未知difficulty级别。

    Example:
        >>> data = [{"difficulty": "easy"}, {"difficulty": "hard"}, {"difficulty": "hard"}]
        >>> resampled = weighted_sampling(data, seed=42)
        >>> # Hard样本比例提升，Easy样本可能被缩减
    """
    if weights is None:
        weights = DEFAULT_SAMPLING_WEIGHTS.copy()

    total_weight = sum(weights.values())
    if not math.isclose(total_weight, 1.0, rel_tol=1e-9):
        raise ValueError(f"Sampling weights must sum to 1.0, got {weights}")

    known_levels = {"easy", "medium", "hard"}
    buckets: dict[str, list[dict[str, object]]] = {
        "easy": [],
        "medium": [],
        "hard": [],
    }
    unknown_items: list[dict[str, object]] = []

    for item in dataset:
        difficulty = str(item.get("difficulty", "")).lower()
        if difficulty in known_levels:
            buckets[difficulty].append(item)
        else:
            # 无difficulty字段的样本默认归为easy
            buckets["easy"].append(item)

    # 统计各类数量
    bucket_sizes = {level: len(buckets[level]) for level in known_levels}
    total_items = sum(bucket_sizes.values())

    if total_items == 0:
        return list(dataset)

    # 计算每类目标数量
    target_counts: dict[str, int] = {}
    for level in known_levels:
        target_counts[level] = max(1, round(weights[level] * total_items))

    # 过采样/欠采样
    rng = random.Random(seed)
    resampled: list[dict[str, object]] = []

    for level in known_levels:
        source = buckets[level]
        target = target_counts[level]
        if not source:
            continue
        if target <= len(source):
            # 欠采样：从source中随机选取target个
            chosen = rng.sample(source, target)
        else:
            # 过采样：先放回所有样本，再补充采样直到达到目标数量
            chosen = list(source)
            while len(chosen) < target:
                chosen.append(rng.choice(source))
        resampled.extend(chosen)

    rng.shuffle(resampled)
    return resampled
    parser = argparse.ArgumentParser(description="Launch the formal LoRA training run.")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="LLaMA-Factory YAML config path.",
    )
    parser.add_argument(
        "--launcher",
        default=DEFAULT_LAUNCHER,
        help="Training launcher command, defaults to llamafactory-cli.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved command without executing it.",
    )
    return parser


def ensure_launcher_available(launcher: str) -> None:
    launcher_path = Path(launcher)
    if launcher_path.parent != Path("."):
        if not launcher_path.exists():
            raise SystemExit(f"训练启动器不存在: {launcher}")
        return

    if shutil.which(launcher) is None:
        raise SystemExit(
            "未找到 `llamafactory-cli`。请先安装 LLaMA-Factory，"
            "或通过 `--launcher` / `LLAMAFACTORY_CLI` 指向可执行文件。"
        )


def parse_scalar(raw: str) -> object:
    value = raw.strip().strip("'\"")
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if any(ch in value for ch in [".", "e", "E"]):
            return float(value)
        return int(value)
    except ValueError:
        return value


def load_simple_yaml(path: Path) -> dict[str, object]:
    """Load YAML config using PyYAML with fallback to simple parser."""
    if _yaml is not None:
        return _yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    # Fallback to simple parser for basic key: value configs
    config: dict[str, object] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if not key or not raw_value:
            continue
        config[key] = parse_scalar(raw_value.split(" #", 1)[0])
    return config


def _apply_env_overrides(config: dict[str, object]) -> None:
    """Override config values from environment variables (in-place)."""
    env_mappings = {
        "ENV_OUTPUT_DIR": "output_dir",
        "ENV_MODEL_PATH": "model_name_or_path",
        "ENV_DATASET": "dataset",
        "ENV_DDP_TIMEOUT": "ddp_timeout",
    }
    for env_var, config_key in env_mappings.items():
        value = os.environ.get(env_var)
        if value is not None:
            config[config_key] = parse_scalar(value)


def load_layered_config(config_path: Path) -> dict[str, object]:
    """Load config with cascading defaults and environment overrides.

    Priority (highest to lowest):
        1. Environment variables (ENV_OUTPUT_DIR, ENV_MODEL_PATH, ...)
        2. User-specified YAML config
        3. configs/config_defaults.yaml
    """
    base: dict[str, object] = {}
    if DEFAULTS_CONFIG.exists():
        base = load_simple_yaml(DEFAULTS_CONFIG)

    layered = dict(base)
    if config_path.exists():
        user = load_simple_yaml(config_path)
        layered.update(user)

    _apply_env_overrides(layered)
    return layered


def count_rows(path: Path) -> int | None:
    if not path.exists():
        return None
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return len(payload)
    return None


def resolve_dataset_path(config: dict[str, object]) -> Path | None:
    dataset_name = config.get("dataset")
    if not isinstance(dataset_name, str) or not DATASET_INFO.exists():
        return None
    info = json.loads(DATASET_INFO.read_text(encoding="utf-8"))
    dataset_meta = info.get(dataset_name)
    if not isinstance(dataset_meta, dict):
        return None
    file_name = dataset_meta.get("file_name")
    if not isinstance(file_name, str):
        return None
    raw_path = Path(file_name)
    if raw_path.is_absolute():
        return raw_path

    candidates = (
        raw_path,
        DATASET_INFO.parent / raw_path,
        DATA_DIR / raw_path,
        DATASET_INFO.parent / DATA_DIR / raw_path,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return DATA_DIR / raw_path


def estimate_total_steps(config: dict[str, object]) -> tuple[int, int, int, int] | None:
    dataset_path = resolve_dataset_path(config)
    if dataset_path is None:
        return None
    total_rows = count_rows(dataset_path)
    if total_rows is None:
        return None

    val_size = float(config.get("val_size", 0.0) or 0.0)
    train_rows = max(1, total_rows - math.ceil(total_rows * val_size))
    batch_size = max(1, int(config.get("per_device_train_batch_size", 1) or 1))
    grad_accum = max(1, int(config.get("gradient_accumulation_steps", 1) or 1))
    epochs = max(1.0, float(config.get("num_train_epochs", 1.0) or 1.0))
    effective_batch = batch_size * grad_accum
    steps_per_epoch = max(1, math.ceil(train_rows / effective_batch))
    total_steps = max(1, math.ceil(steps_per_epoch * epochs))
    return total_rows, train_rows, effective_batch, total_steps


def print_preflight(config_path: Path, config: dict[str, object]) -> None:
    print(f"配置文件: {config_path}")
    output_dir = config.get("output_dir")
    if output_dir:
        print(f"输出目录: {output_dir}")
    dataset_name = config.get("dataset")
    if dataset_name:
        print(f"数据集别名: {dataset_name}")
    dataset_path = resolve_dataset_path(config)
    if dataset_path is not None:
        print(f"数据集路径: {dataset_path}")

    estimate = estimate_total_steps(config)
    if estimate is not None:
        total_rows, train_rows, effective_batch, total_steps = estimate
        print(
            "训练预估: "
            f"rows={total_rows}, train_rows={train_rows}, "
            f"effective_batch={effective_batch}, total_steps≈{total_steps}"
        )

        eval_strategy = config.get("eval_strategy")
        eval_steps = config.get("eval_steps")
        save_steps = config.get("save_steps")
        if eval_strategy == "steps" and isinstance(eval_steps, (int, float)) and int(eval_steps) >= total_steps:
            print(
                "[WARNING] eval_steps >= estimated total_steps，"
                "训练中将不会产生逐步 eval_loss 曲线。"
            )
        if isinstance(save_steps, (int, float)) and int(save_steps) >= total_steps:
            print(
                "[WARNING] save_steps >= estimated total_steps，"
                "训练中不会产生中间 checkpoint。"
            )

    if platform.system() == "Darwin":
        print("[WARNING] 当前机器是 macOS，本仓库正式 9B LoRA 口径默认按 NVIDIA GPU 环境设计。")
    if shutil.which("nvidia-smi") is None:
        print("[WARNING] 未检测到 nvidia-smi；若要复现正式 9B LoRA，请切到 A100 40G 级别 GPU 环境。")


def main() -> int:
    args = build_parser().parse_args()
    config_path = args.config

    if not config_path.exists():
        raise FileNotFoundError(f"训练配置不存在: {config_path}")
    if config_path.suffix.lower() not in {".yaml", ".yml"}:
        raise ValueError(
            f"训练入口要求使用 LLaMA-Factory YAML 配置，当前收到: {config_path}"
        )

    config = load_layered_config(config_path)
    command = [args.launcher, "train", str(config_path)]

    print(f"启动训练命令: {' '.join(command)}")
    print("硬件要求: A100 40G GPU")
    print("预计训练时间: 约 37 分钟")
    print_preflight(config_path, config)
    if REFERENCE_LOG.exists():
        print(f"参考日志: {REFERENCE_LOG}")

    if args.dry_run:
        return 0

    ensure_launcher_available(args.launcher)
    completed = subprocess.run(command, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
