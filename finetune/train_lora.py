"""
正式 LoRA 微调训练入口。

默认对接仓库内已经落盘的 LLaMA-Factory YAML 配置，
让 `make train` 可以直接复现实验入口，而不是停在脚手架。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path


DEFAULT_CONFIG = Path("configs/train_config_20260327_143745.yaml")
DEFAULT_LAUNCHER = os.environ.get("LLAMAFACTORY_CLI", "llamafactory-cli")
REFERENCE_LOG = Path("logs/train_20260327_143745.log")


def build_parser() -> argparse.ArgumentParser:
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


def main() -> int:
    args = build_parser().parse_args()
    config_path = args.config

    if not config_path.exists():
        raise FileNotFoundError(f"训练配置不存在: {config_path}")
    if config_path.suffix.lower() not in {".yaml", ".yml"}:
        raise ValueError(
            f"训练入口要求使用 LLaMA-Factory YAML 配置，当前收到: {config_path}"
        )

    ensure_launcher_available(args.launcher)
    command = [args.launcher, "train", str(config_path)]

    print(f"启动训练命令: {' '.join(command)}")
    print("硬件要求: A100 40G GPU")
    print("预计训练时间: 约 37 分钟")
    if REFERENCE_LOG.exists():
        print(f"参考日志: {REFERENCE_LOG}")

    if args.dry_run:
        return 0

    completed = subprocess.run(command, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
