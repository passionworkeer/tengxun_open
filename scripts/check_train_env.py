#!/usr/bin/env python3
"""
训练前置检查脚本。

目标：
1. 在启动正式 / strict LoRA 训练前给出明确的环境结论；
2. 让“为什么这台机器不能直接重训”变成可复验事实，而不是口头说明；
3. 为外部 GPU 执行提供最短 checklist。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover - dependency should exist in repo env
        raise SystemExit("缺少 PyYAML，无法读取训练配置。") from exc

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SystemExit(f"训练配置格式异常：{path}")
    return raw


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str


def _check_python() -> CheckResult:
    version = ".".join(str(part) for part in sys.version_info[:3])
    return CheckResult("python", "pass", f"Python {version}")


def _check_torch(require_cuda: bool) -> list[CheckResult]:
    try:
        import torch
    except Exception as exc:  # pragma: no cover - torch is expected in env
        return [CheckResult("torch", "fail", f"PyTorch 不可用: {exc}")]

    results = [
        CheckResult("torch", "pass", f"torch {getattr(torch, '__version__', 'unknown')}")
    ]
    cuda_available = bool(torch.cuda.is_available())
    mps_backend = getattr(torch.backends, "mps", None)
    mps_available = bool(mps_backend and mps_backend.is_available())

    if require_cuda:
        if cuda_available:
            detail = f"CUDA 可用，device_count={torch.cuda.device_count()}"
            results.append(CheckResult("cuda", "pass", detail))
        else:
            detail = "CUDA 不可用；当前仅适合 orchestration / 文档整理，不适合正式 9B LoRA 训练。"
            results.append(CheckResult("cuda", "fail", detail))
    else:
        detail = "CUDA 可用" if cuda_available else "CUDA 不可用"
        results.append(CheckResult("cuda", "warn" if not cuda_available else "pass", detail))

    if mps_available:
        results.append(CheckResult("mps", "pass", "Apple MPS 可用"))
    else:
        results.append(CheckResult("mps", "warn", "Apple MPS 不可用"))
    return results


def _check_launcher(launcher: str) -> CheckResult:
    if Path(launcher).exists():
        return CheckResult("launcher", "pass", f"找到训练启动器: {launcher}")
    if shutil.which(launcher):
        return CheckResult("launcher", "pass", f"PATH 中找到训练启动器: {launcher}")
    return CheckResult(
        "launcher",
        "fail",
        f"未找到训练启动器 `{launcher}`；需安装 LLaMA-Factory 或通过 LLAMAFACTORY_CLI 指向可执行文件。",
    )


def _check_path(name: str, path: Path, kind: str = "file") -> CheckResult:
    exists = path.is_file() if kind == "file" else path.is_dir()
    if exists:
        return CheckResult(name, "pass", f"存在: {path}")
    return CheckResult(name, "fail", f"缺失: {path}")


def _check_dataset_mapping(dataset_info_path: Path, dataset_name: str) -> CheckResult:
    try:
        payload = json.loads(dataset_info_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return CheckResult("dataset_mapping", "fail", f"无法读取 dataset_info.json: {exc}")

    if dataset_name in payload:
        return CheckResult("dataset_mapping", "pass", f"dataset_info.json 已注册 `{dataset_name}`")
    return CheckResult("dataset_mapping", "fail", f"dataset_info.json 未注册 `{dataset_name}`")


def _count_dataset_rows(path: Path) -> int | None:
    if not path.exists():
        return None
    if path.suffix.lower() == ".jsonl":
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return len(payload)
    return None


def build_report(config_path: Path, launcher: str, require_cuda: bool) -> dict[str, Any]:
    config = _load_yaml(config_path)
    model_name = str(config.get("model_name_or_path", ""))
    dataset_name = str(config.get("dataset", ""))
    output_dir = Path(str(config.get("output_dir", "")))

    root = Path.cwd()
    dataset_info_path = root / "dataset_info.json"

    dataset_payload = json.loads(dataset_info_path.read_text(encoding="utf-8"))
    dataset_meta = dataset_payload.get(dataset_name, {})
    dataset_file = root / "data" / str(dataset_meta.get("file_name", ""))
    dataset_rows = _count_dataset_rows(dataset_file)
    train_rows = None
    effective_batch = None
    estimated_total_steps = None

    checks: list[CheckResult] = []
    checks.append(_check_python())
    checks.extend(_check_torch(require_cuda=require_cuda))
    checks.append(_check_launcher(launcher))
    checks.append(_check_path("config", config_path))
    checks.append(_check_path("dataset_info", dataset_info_path))
    checks.append(_check_dataset_mapping(dataset_info_path, dataset_name))
    checks.append(_check_path("dataset_file", dataset_file))
    checks.append(_check_path("repo_root", root / "external" / "celery", kind="dir"))

    if dataset_rows is not None:
        val_size = float(config.get("val_size", 0.0) or 0.0)
        train_rows = max(1, dataset_rows - math.ceil(dataset_rows * val_size))
        batch_size = max(1, int(config.get("per_device_train_batch_size", 1) or 1))
        grad_accum = max(1, int(config.get("gradient_accumulation_steps", 1) or 1))
        epochs = max(1.0, float(config.get("num_train_epochs", 1.0) or 1.0))
        effective_batch = batch_size * grad_accum
        steps_per_epoch = max(1, math.ceil(train_rows / effective_batch))
        estimated_total_steps = max(1, math.ceil(steps_per_epoch * epochs))

        checks.append(
            CheckResult(
                "training_shape",
                "pass",
                (
                    f"rows={dataset_rows}, train_rows={train_rows}, "
                    f"effective_batch={effective_batch}, total_steps≈{estimated_total_steps}"
                ),
            )
        )

        eval_strategy = str(config.get("eval_strategy", ""))
        eval_steps = config.get("eval_steps")
        save_steps = config.get("save_steps")
        if eval_strategy == "steps" and isinstance(eval_steps, (int, float)):
            status = "pass" if int(eval_steps) < estimated_total_steps else "warn"
            detail = (
                f"eval_steps={int(eval_steps)}，总步数≈{estimated_total_steps}"
                if status == "pass"
                else f"eval_steps={int(eval_steps)} >= 总步数≈{estimated_total_steps}，不会生成逐步 eval_loss"
            )
            checks.append(CheckResult("eval_schedule", status, detail))
        if isinstance(save_steps, (int, float)):
            status = "pass" if int(save_steps) < estimated_total_steps else "warn"
            detail = (
                f"save_steps={int(save_steps)}，总步数≈{estimated_total_steps}"
                if status == "pass"
                else f"save_steps={int(save_steps)} >= 总步数≈{estimated_total_steps}，不会生成中间 checkpoint"
            )
            checks.append(CheckResult("save_schedule", status, detail))

    output_parent = (root / output_dir).parent
    if output_parent.exists():
        checks.append(CheckResult("output_parent", "pass", f"输出目录父路径存在: {output_parent}"))
    else:
        checks.append(CheckResult("output_parent", "warn", f"输出目录父路径将被创建: {output_parent}"))

    hard_fail = any(item.status == "fail" for item in checks)
    summary = {
        "config_path": str(config_path),
        "launcher": launcher,
        "require_cuda": require_cuda,
        "model_name_or_path": model_name,
        "dataset_name": dataset_name,
        "dataset_file": str(dataset_file),
        "dataset_rows": dataset_rows,
        "train_rows": train_rows,
        "effective_batch": effective_batch,
        "estimated_total_steps": estimated_total_steps,
        "output_dir": str(root / output_dir),
        "hard_fail": hard_fail,
        "checks": [asdict(item) for item in checks],
    }
    return summary


def render_console(summary: dict[str, Any]) -> str:
    lines = [
        f"config: {summary['config_path']}",
        f"model: {summary['model_name_or_path']}",
        f"dataset: {summary['dataset_name']} -> {summary['dataset_file']}",
        f"output: {summary['output_dir']}",
        "",
    ]
    for item in summary["checks"]:
        lines.append(f"[{item['status'].upper():4}] {item['name']}: {item['detail']}")
    lines.append("")
    verdict = "FAIL" if summary["hard_fail"] else "PASS"
    lines.append(f"overall: {verdict}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check LoRA training environment readiness.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/train_config_20260327_143745.yaml"),
        help="LLaMA-Factory YAML config path.",
    )
    parser.add_argument(
        "--launcher",
        default=os.environ.get("LLAMAFACTORY_CLI", "llamafactory-cli"),
        help="Training launcher command.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional JSON output path.",
    )
    parser.add_argument(
        "--require-cuda",
        action="store_true",
        help="Fail when CUDA is not available.",
    )
    args = parser.parse_args()

    summary = build_report(args.config, args.launcher, require_cuda=args.require_cuda)
    print(render_console(summary))

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    return 1 if summary["hard_fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
