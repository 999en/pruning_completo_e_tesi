#!/usr/bin/env bash
# Round 2 e 3 del benchmark — da eseguire DOPO il completamento del benchmark principale.
# Le strategie veto-cover e dom-sub-strict sono ora in pruning.py (patch additiva:
# il benchmark principale, che usa dom-sub / used / hybrid, non e' stato perturbato).
set -e
cd "$(dirname "$0")/.."

echo "=== ROUND 2a: veto-cover (preserva ESATTAMENTE il potere di veto) ==="
PYTHONUNBUFFERED=1 python3 -u benchmark.py \
  --datasets bridges_14,bridges_28,bridges_42,bridges_56,bridges_70 \
  --runs 1,2 \
  --thresholds 3,9 \
  --variants "S4=veto-cover:allow" \
  --reuse-baseline results_benchmark.json \
  --out results_benchmark_r2.json 2>&1 | tee .scratch/benchmark_r2.log

echo
echo "=== ROUND 3: dom-sub-strict (soglie strettamente migliori su tutte le condivise) ==="
PYTHONUNBUFFERED=1 python3 -u benchmark.py \
  --datasets bridges_14,bridges_28,bridges_42,bridges_56,bridges_70 \
  --runs 1,2,3 \
  --thresholds 6,9 \
  --variants "S5=dom-sub-strict:allow" \
  --reuse-baseline results_benchmark.json \
  --out results_benchmark_r3.json 2>&1 | tee .scratch/benchmark_r3.log

echo
echo "=== ROUND 2b: fix del tipo B (coltypes D) a soglia 9, tutte le 25 configurazioni ==="
PYTHONUNBUFFERED=1 python3 -u benchmark.py \
  --datasets bridges_14,bridges_28,bridges_42,bridges_56,bridges_70 \
  --runs 1,2,3,4,5 \
  --thresholds 9 \
  --coltypes D \
  --variants "S1D=dom-sub:allow" \
  --out results_benchmark_D.json 2>&1 | tee .scratch/benchmark_D.log

echo "ROUND 2+3 COMPLETATI"
