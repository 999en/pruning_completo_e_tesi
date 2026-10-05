#!/usr/bin/env bash
# Fase 5 — campagne per regolarizzazione (A), generalizzazione (B) e riordino intra-cluster (C).
set -u
cd "$(dirname "$0")/.."
B="python3 pruning/benchmark.py"
DS="bridges_14,bridges_28,bridges_42,bridges_56,bridges_70"
GL="glass_22,glass_43,glass_64,glass_86,glass_107"

echo "############ A — sweep di alpha (shrinkage bayesiano), Bridges ############"
for A in 1.0 3.0 10.0; do
  PYTHONUNBUFFERED=1 $B --datasets "$DS" --runs 1,2 --thresholds 9,15 \
    --variants "R=precision-priority:allow" \
    --prune-extra "--precision-alpha $A" \
    --reuse-baseline results/results_benchmark.json \
    --out "results/results_benchmark_alpha_${A}.json" 2>&1 | tee ".scratch/log_alpha_${A}.log"
done

echo "############ C — riordino intra-cluster (falsificazione di H13) ############"
PYTHONUNBUFFERED=1 $B --datasets "$DS" --runs 1,2,3 --thresholds 9 \
  --variants "C1=intra-cluster-priority:allow,C2=precision-priority+intra-cluster-priority:allow" \
  --prune-extra "--precision-alpha 3.0" \
  --reuse-baseline results/results_benchmark.json \
  --out results/results_benchmark_C1C2.json 2>&1 | tee .scratch/log_C1C2.log

echo "############ B1 — generalizzazione su Glass ############"
PYTHONUNBUFFERED=1 $B --datasets "$GL" --runs 1,2,3 --thresholds 3,9,15 \
  --variants "P1g=precision-priority:allow" \
  --prune-extra "--precision-alpha 0.0" \
  --dataset-dir .scratch/glass_fixed/Dataset --tuple-dir .scratch/glass_fixed/TupleIniziali \
  --reuse-baseline results/results_benchmark_glass.json \
  --out results/results_benchmark_P1_glass.json 2>&1 | tee .scratch/log_P1_glass.log

echo "############ B1r — generalizzazione su Glass, con regolarizzazione ############"
PYTHONUNBUFFERED=1 $B --datasets "$GL" --runs 1,2,3 --thresholds 3,9,15 \
  --variants "P1g_reg=precision-priority:allow" \
  --prune-extra "--precision-alpha 3.0" \
  --dataset-dir .scratch/glass_fixed/Dataset --tuple-dir .scratch/glass_fixed/TupleIniziali \
  --reuse-baseline results/results_benchmark_glass.json \
  --out results/results_benchmark_P1reg_glass.json 2>&1 | tee .scratch/log_P1reg_glass.log

echo "############ B2 — generalizzazione su Restaurant ############"
PYTHONUNBUFFERED=1 $B --datasets restaurant_52,restaurant_104,restaurant_206 --runs 1,2,3 \
  --thresholds 3,6 \
  --variants "P1r=precision-priority:allow" --text-thr 0.8 \
  --prune-extra "--precision-alpha 0.0" \
  --out results/results_benchmark_P1_restaurant.json 2>&1 | tee .scratch/log_P1_restaurant.log

echo "FASE 5 COMPLETATA"
