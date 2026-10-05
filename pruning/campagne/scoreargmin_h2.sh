#!/usr/bin/env bash
# H2 — `score-argmin` su Glass e Restaurant: l'esatto lato generazione dove l'euristica fallisce.
#
# Ipotesi: su Glass/Restaurant `score-argmin` NON perde copertura (la preserva per costruzione,
# perche' rimuove solo RFD mai argmin del punteggio) e la perdita si concentra lato veto.
# Se regge, e' la riduzione "sicura" che oggi su Glass e' solo 5,9-8,6% (veto-cover).
#
# `--maxthr` viene ora passato da benchmark.py (fix): la decisione di pruning e l'esecuzione
# RENUVER avvengono allo stesso punto di funzionamento.
set -u
cd "$(dirname "$0")/../.."
B="python3 pruning/benchmark.py"
GL="glass_22,glass_43,glass_64,glass_86,glass_107"
RS="restaurant_52,restaurant_104,restaurant_206"
GD="--dataset-dir .scratch/glass_fixed/Dataset --tuple-dir .scratch/glass_fixed/TupleIniziali"
V="SAa=score-argmin:allow,SAb=score-argmin:budget:0.5"

echo "############ 1) Glass (5 dataset x run 1-2 x soglie 3/9/15) ############"
PYTHONUNBUFFERED=1 $B --datasets "$GL" --runs 1,2 --thresholds 3,9,15 \
  --variants "$V" --prune-extra "--coltypes D,D,D,D,D,D,D,D,D,D,D" \
  --family glass $GD \
  --reuse-baseline results/results_benchmark_glass.json \
  --out results/results_scoreargmin_glass.json 2>&1 | tee .scratch/log_sa_glass.log

echo
echo "############ 2) Restaurant (3 dataset x run 1-2 x soglie 3/6) ############"
PYTHONUNBUFFERED=1 $B --datasets "$RS" --runs 1,2 --thresholds 3,6 \
  --variants "$V" --prune-extra "--coltypes D,D,D,D,D,D" \
  --family restaurant --text-thr 0.8 \
  --reuse-baseline results/results_benchmark_P1_restaurant.json \
  --out results/results_scoreargmin_restaurant.json 2>&1 | tee .scratch/log_sa_restaurant.log

echo
echo "############ 3) Controllo di sanita' su Bridges (numeri noti: 98% / 49,1%) ############"
PYTHONUNBUFFERED=1 $B --datasets bridges_14,bridges_28,bridges_42,bridges_56,bridges_70 \
  --runs 1 --thresholds 9,15 \
  --variants "$V" --prune-extra "--coltypes D,C,D,D,D,D,D,B,B,D,D,D,D" \
  --reuse-baseline results/results_benchmark.json \
  --out results/results_scoreargmin_bridges.json 2>&1 | tee .scratch/log_sa_bridges.log

echo
echo "############ FATTO ############"
