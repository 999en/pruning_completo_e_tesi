#!/usr/bin/env bash
# Fase 4 — campagne per `precision-priority`.
# P1/P2 riordinano soltanto (nessuna rimozione): costano quanto il baseline.
# P3/P4 aggiungono il pruning adattivo e sono molto piu' veloci.
set -u
cd "$(dirname "$0")/.."
B="python3 pruning/benchmark.py"
DS="bridges_14,bridges_28,bridges_42,bridges_56,bridges_70"

echo "############ P1/P2 — riordino puro (nessuna RFD rimossa) ############"
PYTHONUNBUFFERED=1 $B --datasets "$DS" --runs 1,2,3 --thresholds 9,15 \
  --variants "P1=precision-priority:allow,P2=exact-priority+precision-priority:allow" \
  --reuse-baseline results/results_benchmark.json \
  --out results/results_benchmark_P1P2.json 2>&1 | tee .scratch/log_P1P2.log

echo "############ P3/P4 — riordino + pruning adattivo (alpha 0.85) ############"
PYTHONUNBUFFERED=1 $B --datasets "$DS" --runs 1,2,3,4,5 --thresholds 9,15 \
  --variants "P3=precision-priority+dom-sub-adaptive:allow,P4=exact-priority+precision-priority+dom-sub-adaptive:allow" \
  --prune-extra "--adaptive-alpha 0.85 --adaptive-side stable" \
  --reuse-baseline results/results_benchmark.json \
  --out results/results_benchmark_P3P4.json 2>&1 | tee .scratch/log_P3P4.log

echo "FASE 4 COMPLETATA"
