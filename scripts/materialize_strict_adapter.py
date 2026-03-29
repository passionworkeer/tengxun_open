#!/usr/bin/env python3
"""
把 strict-clean handoff 包中的 LoRA adapter 提取到默认本地目录。
"""

from __future__ import annotations

import argparse
import tarfile
from pathlib import Path

REQUIRED_FILES = ("adapter_config.json", "adapter_model.safetensors")


def has_required_adapter_files(output_dir: Path) -> bool:
    return all((output_dir / filename).exists() for filename in REQUIRED_FILES)


def materialize_adapter(*, tarball: Path, output_dir: Path) -> None:
    if not tarball.exists():
        raise FileNotFoundError(f"handoff tarball not found: {tarball}")

    output_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tarball, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            filename = Path(member.name).name
            if not filename:
                continue
            target = output_dir / filename
            if target.exists():
                continue
            extracted = archive.extractfile(member)
            if extracted is None:
                continue
            target.write_bytes(extracted.read())

    if not has_required_adapter_files(output_dir):
        missing = [name for name in REQUIRED_FILES if not (output_dir / name).exists()]
        raise RuntimeError(
            f"adapter materialization incomplete: missing {', '.join(missing)} in {output_dir}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize strict-clean LoRA adapter.")
    parser.add_argument(
        "--tarball",
        type=Path,
        default=Path("artifacts/handoff/strict_clean_20260329_minimal.tar.gz"),
        help="Path to strict-clean handoff tarball.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/lora/qwen3.5-9b/strict_clean_20260329"),
        help="Directory to materialize the adapter into.",
    )
    args = parser.parse_args()

    materialize_adapter(tarball=args.tarball, output_dir=args.output_dir)
    print(f"Strict adapter ready at {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
