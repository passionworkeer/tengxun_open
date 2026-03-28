#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_NAME="${RUN_NAME:-strict_clean_$(date +%Y%m%d_%H%M%S)}"
BASE_CONFIG="${BASE_CONFIG:-configs/train_config_strict_replay_20260329.yaml}"
REPO_ROOT="${REPO_ROOT:-external/celery}"
RUN_ROOT="${RUN_ROOT:-results/qwen_strict_runs/${RUN_NAME}}"
OUTPUT_DIR="${OUTPUT_DIR:-artifacts/lora/qwen3.5-9b/${RUN_NAME}}"
TMP_CONFIG="${TMP_CONFIG:-configs/${RUN_NAME}.yaml}"
TRAIN_LOG="${TRAIN_LOG:-logs/${RUN_NAME}.train.log}"
WITH_RAG="${WITH_RAG:-auto}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

usage() {
  cat <<EOF
Usage:
  RUN_NAME=strict_clean_20260329 ./scripts/run_qwen_strict_full.sh

Optional env vars:
  RUN_NAME       Run identifier. Default: strict_clean_<timestamp>
  BASE_CONFIG    Base YAML config. Default: configs/train_config_strict_replay_20260329.yaml
  REPO_ROOT      Celery repo root for RAG eval. Default: external/celery
  RUN_ROOT       Result directory. Default: results/qwen_strict_runs/<RUN_NAME>
  OUTPUT_DIR     Training output directory. Default: artifacts/lora/qwen3.5-9b/<RUN_NAME>
  TRAIN_LOG      Training log path. Default: logs/<RUN_NAME>.train.log
  WITH_RAG       auto / 0 / 1. Default: auto
  PYTHON_BIN     Python executable. Default: python3

Notes:
  - Requires CUDA GPU and llamafactory-cli in PATH.
  - If WITH_RAG=auto, PE+RAG+FT runs only when GOOGLE_API_KEY is set and REPO_ROOT exists.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_cmd "$PYTHON_BIN"
require_cmd llamafactory-cli
require_cmd nvidia-smi
require_cmd tee

mkdir -p "$(dirname "$TMP_CONFIG")" "$(dirname "$TRAIN_LOG")" "$RUN_ROOT"

echo "=== Qwen strict-clean rerun ==="
echo "Run name:   $RUN_NAME"
echo "Config:     $BASE_CONFIG"
echo "Output dir: $OUTPUT_DIR"
echo "Run root:   $RUN_ROOT"
echo "Train log:  $TRAIN_LOG"

if [[ ! -f "$BASE_CONFIG" ]]; then
  echo "Base config not found: $BASE_CONFIG" >&2
  exit 1
fi

if [[ ! -f "data/finetune_dataset_500_strict.jsonl" ]]; then
  echo "Strict finetune dataset missing: data/finetune_dataset_500_strict.jsonl" >&2
  exit 1
fi

echo
echo "[1/7] Environment check"
PYTHONPATH=. "$PYTHON_BIN" scripts/check_train_env.py \
  --config "$BASE_CONFIG" \
  --require-cuda \
  --json-out "$RUN_ROOT/train_env.json"
nvidia-smi

echo
echo "[2/7] Data guard"
PYTHONPATH=. "$PYTHON_BIN" -m finetune.data_guard data/finetune_dataset_500_strict.jsonl

echo
echo "[3/7] Materialize run config: $TMP_CONFIG"
"$PYTHON_BIN" - "$BASE_CONFIG" "$TMP_CONFIG" "$OUTPUT_DIR" <<'PY'
from pathlib import Path
import sys
import yaml

base_config = Path(sys.argv[1])
tmp_config = Path(sys.argv[2])
output_dir = sys.argv[3]

payload = yaml.safe_load(base_config.read_text(encoding="utf-8"))
payload["output_dir"] = f"./{output_dir}".replace("//", "/")

tmp_config.write_text(
    yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
    encoding="utf-8",
)
print(f"Wrote config to {tmp_config}")
PY

echo
echo "[4/7] Train strict-clean adapter"
PYTHONPATH=. "$PYTHON_BIN" finetune/train_lora.py --config "$TMP_CONFIG" 2>&1 | tee "$TRAIN_LOG"

ADAPTER_PATH="$OUTPUT_DIR"
if [[ ! -d "$ADAPTER_PATH" ]]; then
  echo "Adapter output directory not found after training: $ADAPTER_PATH" >&2
  exit 1
fi

echo
echo "[5/7] FT only eval"
PYTHONPATH=. "$PYTHON_BIN" run_ft_eval.py \
  --cases data/eval_cases.json \
  --adapter-path "$ADAPTER_PATH" \
  --output "$RUN_ROOT/qwen_ft_strict.json"

"$PYTHON_BIN" scripts/rescore_result_file.py \
  --path "$RUN_ROOT/qwen_ft_strict.json" \
  --output "$RUN_ROOT/qwen_ft_strict_metrics.json"

echo
echo "[6/7] PE + FT eval"
FEWSHOT_DATA_PATH=data/fewshot_examples_20_strict.json \
PYTHONPATH=. "$PYTHON_BIN" run_pe_ft_eval.py \
  --cases data/eval_cases.json \
  --adapter-path "$ADAPTER_PATH" \
  --output "$RUN_ROOT/qwen_pe_ft_strict.json"

"$PYTHON_BIN" scripts/rescore_result_file.py \
  --path "$RUN_ROOT/qwen_pe_ft_strict.json" \
  --output "$RUN_ROOT/qwen_pe_ft_strict_metrics.json"

run_rag=0
if [[ "$WITH_RAG" == "1" ]]; then
  run_rag=1
elif [[ "$WITH_RAG" == "auto" && -n "${GOOGLE_API_KEY:-}" && -d "$REPO_ROOT" ]]; then
  run_rag=1
fi

if [[ "$run_rag" == "1" ]]; then
  echo
  echo "[7/7] PE + RAG + FT eval"
  FEWSHOT_DATA_PATH=data/fewshot_examples_20_strict.json \
  PYTHONPATH=. "$PYTHON_BIN" run_pe_rag_ft_eval.py \
    --cases data/eval_cases.json \
    --repo-root "$REPO_ROOT" \
    --adapter-path "$ADAPTER_PATH" \
    --output "$RUN_ROOT/qwen_pe_rag_ft_strict.json"

  "$PYTHON_BIN" scripts/rescore_result_file.py \
    --path "$RUN_ROOT/qwen_pe_rag_ft_strict.json" \
    --output "$RUN_ROOT/qwen_pe_rag_ft_strict_metrics.json"
else
  echo
  echo "[7/7] Skip PE + RAG + FT eval"
  echo "Reason: WITH_RAG=$WITH_RAG, GOOGLE_API_KEY present=${GOOGLE_API_KEY:+yes}${GOOGLE_API_KEY:-no}, repo_root_exists=$([[ -d "$REPO_ROOT" ]] && echo yes || echo no)"
fi

echo
echo "Strict-clean Qwen rerun finished."
echo "Adapter dir: $ADAPTER_PATH"
echo "Run root:    $RUN_ROOT"
echo "Train log:   $TRAIN_LOG"
