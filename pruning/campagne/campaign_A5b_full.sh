#!/usr/bin/env bash
# A5b — estensione a griglia completa e validazione multi-dataset.
#
# A5b = exact-priority + dom-sub-adaptive (alpha = 0.85).  Nessuna modifica al JAR.
#
# NOTA SUI FLAG: `--adaptive-alpha`, `--results-dir` e `--populated-dir` sono opzioni di
# pruning.py, non di benchmark.py: vanno passate tramite `--prune-extra`.  La soglia
# testuale di benchmark.py si chiama `--text-thr` (non `--text-similarity`).
set -u
cd "$(dirname "$0")/../.."
B="python3 pruning/benchmark.py"
PRUNE_EXTRA="--adaptive-alpha 0.85"

echo "############ A — Bridges, run 3-5, soglie 9 e 15 ############"
PYTHONUNBUFFERED=1 $B --datasets bridges_14,bridges_28,bridges_42,bridges_56,bridges_70 \
  --runs 3,4,5 --thresholds 9,15 \
  --variants "A5b=exact-priority+dom-sub-adaptive:allow" \
  --prune-extra "$PRUNE_EXTRA" \
  --reuse-baseline results/results_benchmark.json \
  --out results/results_A5b_bridges_r345.json 2>&1 | tee .scratch/log_A5b_r345.log

echo
echo "############ B — Glass (schema corretto), run 1-3, soglie 3/9/15 ############"
PYTHONUNBUFFERED=1 $B --datasets glass_22,glass_43,glass_64,glass_86,glass_107 \
  --runs 1,2,3 --thresholds 3,9,15 \
  --variants "A5b=exact-priority+dom-sub-adaptive:allow" \
  --prune-extra "$PRUNE_EXTRA" \
  --family glass \
  --dataset-dir .scratch/glass_fixed/Dataset --tuple-dir .scratch/glass_fixed/TupleIniziali \
  --reuse-baseline results/results_benchmark_glass.json \
  --out results/results_A5b_glass.json 2>&1 | tee .scratch/log_A5b_glass.log

echo
echo "############ C — Restaurant (metrica testuale), run 1-3, soglie 3/6 ############"
PYTHONUNBUFFERED=1 $B --datasets restaurant_52,restaurant_104,restaurant_206 \
  --runs 1,2,3 --thresholds 3,6 \
  --variants "A5b=exact-priority+dom-sub-adaptive:allow" \
  --prune-extra "$PRUNE_EXTRA" \
  --family restaurant --text-thr 0.8 \
  --reuse-baseline results/results_benchmark_P1_restaurant.json \
  --out results/results_A5b_restaurant.json 2>&1 | tee .scratch/log_A5b_restaurant.log

echo
echo "############ D — esperimento d'ordine Fase 5 (da rieseguire: job interrotto) ############"
PYTHONUNBUFFERED=1 python3 pruning/exp_order.py bridges_14,bridges_28,bridges_42 9 1 bridges \
  2>&1 | tee .scratch/log_exp_order.log

echo
echo "############ FATTO ############"
