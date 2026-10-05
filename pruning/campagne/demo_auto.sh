#!/usr/bin/env bash
# Compito C — dimostrazione della strategia `auto`.
#
# `auto` deve comportarsi da A5b sui dataset densi (Bridges) e da veto-cover su quelli
# sparsi (Restaurant, Glass). Il caso decisivo e' Glass a soglia 9 e 15: li' N = 11 648 e
# 27 445, cioe' SOPRA la soglia N=2500 proposta, ma il regime e' sparso — una regola basata
# su N sceglierebbe A5b e danneggerebbe il risultato.
#
# NOTA SUI FLAG: `--results-dir`, `--populated-dir` e `--adaptive-alpha` sono opzioni di
# pruning.py (vanno in `--prune-extra`); la soglia testuale di benchmark.py e' `--text-thr`.
set -u
cd "$(dirname "$0")/../.."

echo "############ 1) Bridges (denso: atteso A5b) ############"
PYTHONUNBUFFERED=1 python3 pruning/benchmark.py --datasets bridges_14 --runs 1 --thresholds 9 \
  --variants "Auto=auto:allow" \
  --reuse-baseline results/results_benchmark.json \
  --out results/results_auto_bridges.json 2>&1 | tee .scratch/log_auto_bridges.log

echo
echo "############ 2) Restaurant (sparso: atteso veto-cover) ############"
PYTHONUNBUFFERED=1 python3 pruning/benchmark.py --datasets restaurant_104 --runs 1 --thresholds 6 \
  --variants "Auto=auto:allow" --family restaurant --text-thr 0.8 \
  --reuse-baseline results/results_benchmark_P1_restaurant.json \
  --out results/results_auto_restaurant.json 2>&1 | tee .scratch/log_auto_restaurant.log

echo
echo "############ 3) Glass @9 e @15 (sparso con N grande: il caso che N sbaglierebbe) ############"
PYTHONUNBUFFERED=1 python3 pruning/benchmark.py --datasets glass_22 --runs 1 --thresholds 9,15 \
  --variants "Auto=auto:allow" --family glass \
  --dataset-dir .scratch/glass_fixed/Dataset --tuple-dir .scratch/glass_fixed/TupleIniziali \
  --reuse-baseline results/results_benchmark_glass.json \
  --out results/results_auto_glass.json 2>&1 | tee .scratch/log_auto_glass.log

echo
echo "############ FATTO ############"
