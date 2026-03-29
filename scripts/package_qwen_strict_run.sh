#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_NAME="${RUN_NAME:-}"
RUN_ROOT="${RUN_ROOT:-}"
OUTPUT_DIR="${OUTPUT_DIR:-}"
TRAIN_LOG="${TRAIN_LOG:-}"
TMP_CONFIG="${TMP_CONFIG:-}"
INCLUDE_ADAPTER="${INCLUDE_ADAPTER:-0}"
PACKAGE_DIR="${PACKAGE_DIR:-artifacts/handoff}"

usage() {
  cat <<EOF
Usage:
  RUN_NAME=strict_clean_20260329 ./scripts/package_qwen_strict_run.sh

Optional env vars:
  RUN_NAME        Run identifier. Preferred input.
  RUN_ROOT        Override run result directory.
  OUTPUT_DIR      Override adapter directory.
  TRAIN_LOG       Override train log path.
  TMP_CONFIG      Override materialized config path.
  INCLUDE_ADAPTER 0 or 1. Default: 0.
  PACKAGE_DIR     Output package directory. Default: artifacts/handoff

Example:
  RUN_NAME=strict_clean_20260329 INCLUDE_ADAPTER=0 ./scripts/package_qwen_strict_run.sh
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ -z "$RUN_NAME" && -z "$RUN_ROOT" ]]; then
  echo "ERROR: RUN_NAME or RUN_ROOT is required." >&2
  usage
  exit 1
fi

if [[ -z "$RUN_ROOT" ]]; then
  RUN_ROOT="results/qwen_strict_runs/${RUN_NAME}"
fi
if [[ -z "$RUN_NAME" ]]; then
  RUN_NAME="$(basename "$RUN_ROOT")"
fi
if [[ -z "$OUTPUT_DIR" ]]; then
  OUTPUT_DIR="artifacts/lora/qwen3.5-9b/${RUN_NAME}"
fi
if [[ -z "$TRAIN_LOG" ]]; then
  TRAIN_LOG="logs/${RUN_NAME}.train.log"
fi
if [[ -z "$TMP_CONFIG" ]]; then
  TMP_CONFIG="configs/${RUN_NAME}.yaml"
fi

mkdir -p "$PACKAGE_DIR"

if [[ ! -d "$RUN_ROOT" ]]; then
  echo "ERROR: run root not found: $RUN_ROOT" >&2
  exit 1
fi

STAGING_DIR="$(mktemp -d "${TMPDIR:-/tmp}/qwen-strict-package.XXXXXX")"
trap 'rm -rf "$STAGING_DIR"' EXIT

mkdir -p "$STAGING_DIR/$RUN_NAME"

cp -R "$RUN_ROOT" "$STAGING_DIR/$RUN_NAME/results"

if [[ -f "$TRAIN_LOG" ]]; then
  mkdir -p "$STAGING_DIR/$RUN_NAME/logs"
  cp "$TRAIN_LOG" "$STAGING_DIR/$RUN_NAME/logs/"
fi

if [[ -f "$TMP_CONFIG" ]]; then
  mkdir -p "$STAGING_DIR/$RUN_NAME/configs"
  cp "$TMP_CONFIG" "$STAGING_DIR/$RUN_NAME/configs/"
fi

for optional_file in \
  results/strict_replay_train_env_20260329.json \
  results/formal_train_env_20260329.json \
  results/training_log_summary_20260329.json \
  reports/strict_ft_execution_status_20260329.md \
  reports/training_evidence_audit_20260329.md \
  reports/qwen_strict_closeout_20260329.md
do
  if [[ -f "$optional_file" ]]; then
    target_dir="$STAGING_DIR/$RUN_NAME/$(dirname "$optional_file")"
    mkdir -p "$target_dir"
    cp "$optional_file" "$target_dir/"
  fi
done

if [[ "$INCLUDE_ADAPTER" == "1" && -d "$OUTPUT_DIR" ]]; then
  mkdir -p "$STAGING_DIR/$RUN_NAME/artifacts/lora/qwen3.5-9b"
  cp -R "$OUTPUT_DIR" "$STAGING_DIR/$RUN_NAME/artifacts/lora/qwen3.5-9b/"
fi

PACKAGE_PATH="$PACKAGE_DIR/${RUN_NAME}.tar.gz"
tar -czf "$PACKAGE_PATH" -C "$STAGING_DIR" "$RUN_NAME"

echo "Packaged strict run to: $PACKAGE_PATH"
