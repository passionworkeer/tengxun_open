#!/bin/bash
# Run Qwen3.5 evaluation

# Default values
API_URL="http://localhost:8000/v1"
MODEL="qwen3.5"
MAX_CASES=50

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --api-url)
            API_URL="$2"
            shift 2
            ;;
        --model)
            MODEL="$2"
            shift 2
            ;;
        --max-cases)
            MAX_CASES="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "Qwen3.5 Evaluation"
echo "=========================================="
echo "API URL:  $API_URL"
echo "Model:    $MODEL"
echo "Max Cases: $MAX_CASES"
echo "=========================================="

python3 -m evaluation.run_qwen_eval \
    --base-url "$API_URL" \
    --model "$MODEL" \
    --max-cases $MAX_CASES \
    --output results/qwen3_eval_results.json

echo ""
echo "Running analysis..."
python3 scripts/analyze_qwen_results.py results/qwen3_eval_results.json