#!/usr/bin/env bash
# Rendere utile l'approccio anche su Glass e Restaurant.
#
# Due leve mai provate su questi dataset:
#   1. `exact-priority` da solo: non rimuove NULLA, quindi e' a rischio zero. Non era mai
#      stato eseguito su Glass/Restaurant (A4 esiste solo per Bridges).
#   2. `dom-sub-adaptive` in regime GENTILE. La riduzione e' una funzione a gradino di alpha:
#      su glass@9 va da 88,4% (alpha<=0,95) a 31,7% (0,99) a 6,3% (0,995). Il valore 0,85 usato
#      su Bridges e' troppo aggressivo per file piccoli; 0,99 e 0,995 non erano mai stati provati.
set -u
cd "$(dirname "$0")/../.."
B="python3 pruning/benchmark.py"
GL="glass_22,glass_43,glass_64"
RS="restaurant_52,restaurant_104"
GD="--dataset-dir .scratch/glass_fixed/Dataset --tuple-dir .scratch/glass_fixed/TupleIniziali"

echo "############ 1) exact-priority da solo (nessuna rimozione) ############"
PYTHONUNBUFFERED=1 $B --datasets "$GL" --runs 1 --thresholds 9 \
  --variants "EP=exact-priority:allow" --family glass $GD \
  --reuse-baseline results/results_benchmark_glass.json \
  --out results/results_ep_glass.json 2>&1 | tee .scratch/log_ep_glass.log
PYTHONUNBUFFERED=1 $B --datasets "$RS" --runs 1 --thresholds 6 \
  --variants "EP=exact-priority:allow" --family restaurant --text-thr 0.8 \
  --reuse-baseline results/results_benchmark_P1_restaurant.json \
  --out results/results_ep_restaurant.json 2>&1 | tee .scratch/log_ep_restaurant.log

echo
echo "############ 2) A5b in regime gentile: alpha = 0.99 ############"
PYTHONUNBUFFERED=1 $B --datasets "$GL" --runs 1 --thresholds 9 \
  --variants "A99=exact-priority+dom-sub-adaptive:allow" \
  --prune-extra "--adaptive-alpha 0.99" --family glass $GD \
  --reuse-baseline results/results_benchmark_glass.json \
  --out results/results_a99_glass.json 2>&1 | tee .scratch/log_a99_glass.log
PYTHONUNBUFFERED=1 $B --datasets "$RS" --runs 1 --thresholds 6 \
  --variants "A99=exact-priority+dom-sub-adaptive:allow" \
  --prune-extra "--adaptive-alpha 0.99" --family restaurant --text-thr 0.8 \
  --reuse-baseline results/results_benchmark_P1_restaurant.json \
  --out results/results_a99_restaurant.json 2>&1 | tee .scratch/log_a99_restaurant.log

echo
echo "############ 3) A5b in regime gentile: alpha = 0.995 ############"
PYTHONUNBUFFERED=1 $B --datasets "$GL" --runs 1 --thresholds 9 \
  --variants "A995=exact-priority+dom-sub-adaptive:allow" \
  --prune-extra "--adaptive-alpha 0.995" --family glass $GD \
  --reuse-baseline results/results_benchmark_glass.json \
  --out results/results_a995_glass.json 2>&1 | tee .scratch/log_a995_glass.log
PYTHONUNBUFFERED=1 $B --datasets "$RS" --runs 1 --thresholds 6 \
  --variants "A995=exact-priority+dom-sub-adaptive:allow" \
  --prune-extra "--adaptive-alpha 0.995" --family restaurant --text-thr 0.8 \
  --reuse-baseline results/results_benchmark_P1_restaurant.json \
  --out results/results_a995_restaurant.json 2>&1 | tee .scratch/log_a995_restaurant.log

echo
echo "############ FATTO ############"
