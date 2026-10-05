#!/usr/bin/env bash
# Consolidamento multi-dataset del regime gentile (alpha = 0,99).
#
# Obiettivo: portare l'unico risultato non-Bridges da 16 a ~97 configurazioni, così che
# "riduzione senza perdita rilevata" non poggi più su un campione esiguo.
#
#   Glass      : 5 dataset x run 1-5 x soglie 3/9/15 = 75 configurazioni (baseline riusato, 75 disponibili)
#   Restaurant : 4 dataset x run 1-3 (259 solo 1-2) x soglie 3/6 = 22 configurazioni
#
# Il contrasto con alpha = 0,85 e' gia' disponibile su Glass da results_A5b_glass.json (45 config).
set -u
cd "$(dirname "$0")/../.."
B="python3 pruning/benchmark.py"
GL="glass_22,glass_43,glass_64,glass_86,glass_107"
RS="restaurant_52,restaurant_104,restaurant_206"

echo "############ GLASS — griglia completa (75 configurazioni) ############"
PYTHONUNBUFFERED=1 $B --datasets "$GL" --runs 1,2,3,4,5 --thresholds 3,9,15 \
  --variants "A99=exact-priority+dom-sub-adaptive:allow" \
  --prune-extra "--adaptive-alpha 0.99 --coltypes D,D,D,D,D,D,D,D,D,D,D" \
  --family glass --dataset-dir .scratch/glass_fixed/Dataset \
  --tuple-dir .scratch/glass_fixed/TupleIniziali \
  --reuse-baseline results/results_benchmark_glass.json \
  --out results/results_a99_glass_grid.json 2>&1 | tee .scratch/log_a99_grid_glass.log

echo
echo "############ RESTAURANT — 3 dataset x run 1-3 x soglie 3/6 (18 configurazioni) ############"
PYTHONUNBUFFERED=1 $B --datasets "$RS" --runs 1,2,3 --thresholds 3,6 \
  --variants "A99=exact-priority+dom-sub-adaptive:allow" \
  --prune-extra "--adaptive-alpha 0.99 --coltypes D,D,D,D,D,D" \
  --family restaurant --text-thr 0.8 \
  --reuse-baseline results/results_benchmark_P1_restaurant.json \
  --out results/results_a99_restaurant_grid.json 2>&1 | tee .scratch/log_a99_grid_restaurant.log

echo
echo "############ RESTAURANT 259 — run 1-2 x soglie 3/6 (4 configurazioni) ############"
PYTHONUNBUFFERED=1 $B --datasets restaurant_259 --runs 1,2 --thresholds 3,6 \
  --variants "A99=exact-priority+dom-sub-adaptive:allow" \
  --prune-extra "--adaptive-alpha 0.99 --coltypes D,D,D,D,D,D" \
  --family restaurant --text-thr 0.8 \
  --reuse-baseline results/results_benchmark_restaurant.json \
  --out results/results_a99_restaurant259_grid.json 2>&1 | tee .scratch/log_a99_grid_restaurant259.log

echo
echo "############ FATTO ############"
