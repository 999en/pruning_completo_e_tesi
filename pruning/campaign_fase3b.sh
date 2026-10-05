#!/usr/bin/env bash
# Fase 3 — campagna di follow-up: combinazione del riordino (A4) con il pruning adattivo (A2),
# e sweep del budget di score-argmin per centrare il target del 50%.
set -u
cd "$(dirname "$0")/.."
B="python3 pruning/benchmark.py"
DS="bridges_14,bridges_28,bridges_42,bridges_56,bridges_70"

echo "############ A5 — exact-priority + dom-sub-adaptive (alpha 0.90) ############"
PYTHONUNBUFFERED=1 $B --datasets "$DS" --runs 1,2 --thresholds 9,15 \
  --variants "A5=exact-priority+dom-sub-adaptive:allow" \
  --prune-extra "--adaptive-alpha 0.90 --adaptive-side stable" \
  --reuse-baseline results/results_benchmark.json \
  --out results/results_benchmark_A5.json 2>&1 | tee .scratch/log_A5.log

echo "############ A5b — exact-priority + dom-sub-adaptive (alpha 0.85) ############"
PYTHONUNBUFFERED=1 $B --datasets "$DS" --runs 1,2 --thresholds 9,15 \
  --variants "A5b=exact-priority+dom-sub-adaptive:allow" \
  --prune-extra "--adaptive-alpha 0.85 --adaptive-side stable" \
  --reuse-baseline results/results_benchmark.json \
  --out results/results_benchmark_A5b.json 2>&1 | tee .scratch/log_A5b.log

echo "############ A1c — score-argmin budget 0.55 / 0.60 ############"
for F in 0.55 0.60; do
  PYTHONUNBUFFERED=1 $B --datasets "$DS" --runs 1,2,3 --thresholds 9,15 \
    --variants "A1c=score-argmin:budget:$F" \
    --prune-extra "--coltypes D,C,D,D,D,D,D,B,B,D,D,D,D" \
    --reuse-baseline results/results_benchmark.json \
    --out "results/results_benchmark_A1c_${F}.json" 2>&1 | tee ".scratch/log_A1c_${F}.log"
done

echo "FOLLOW-UP COMPLETATO"
