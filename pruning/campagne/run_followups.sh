#!/usr/bin/env bash
# Seguiti della Fase 5, in sequenza: un solo processo RENUVER alla volta (la cartella
# .scratch/bench_lab e' condivisa: due run in parallelo si sovrascriverebbero i file).
set -u
cd "$(dirname "$0")/../.."
GL="glass_22,glass_43,glass_64,glass_86,glass_107"

echo "############ 1) raccolta statistiche Glass con lo SCHEMA CORRETTO ############"
PYTHONUNBUFFERED=1 python3 pruning/collect_stats.py \
  --datasets "$GL" --runs 1,2,3,4,5 --thresholds 3,9,15 \
  --dataset-dir .scratch/glass_fixed/Dataset --tuple-dir .scratch/glass_fixed/TupleIniziali \
  --out-dir .scratch/glass_fixed 2>&1 | tee .scratch/log_collect_glass.log

echo
echo "############ 2) P1g con le statistiche CORRETTE ############"
PYTHONUNBUFFERED=1 python3 pruning/benchmark.py --datasets "$GL" --runs 1,2,3 --thresholds 3,9,15 \
  --variants "P1gs=precision-priority:allow" \
  --dataset-dir .scratch/glass_fixed/Dataset --tuple-dir .scratch/glass_fixed/TupleIniziali \
  --prune-extra "--precision-alpha 0.0 --results-dir .scratch/glass_fixed/Results --populated-dir .scratch/glass_fixed/Populated" \
  --reuse-baseline results/results_benchmark_glass.json \
  --out results/results_benchmark_P1_glass_stats.json 2>&1 | tee .scratch/log_P1_glass_stats.log

echo
echo "############ 3) esperimento d'ordine: first-best vs last-best vs random ############"
PYTHONUNBUFFERED=1 python3 pruning/exp_order.py bridges_14,bridges_28,bridges_42 9 1 bridges \
  2>&1 | tee .scratch/log_exp_order.log

echo
echo "############ FATTO ############"
