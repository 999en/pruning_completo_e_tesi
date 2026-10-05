#!/usr/bin/env bash
# Conclusione della strada `--veto-order cells`: l'ordinamento del budget per celle nulle REALI
# batte il proxy `exposure` su TUTTE e tre le famiglie utilizzabili?
#
# A/B a pari budget e pari numero di rimozioni: cambia solo l'ORDINE con cui si sceglie quali
# RFD togliere. `dom-sub-adaptive` (non `score-argmin`, che su Glass e' 251x piu' lento).
# Baseline riusato dall'archivio; entrambi i bracci eseguiti freschi e con ritenzione.
set -u
cd "$(dirname "$0")/../.."
B="python3 pruning/benchmark.py"
CT_B="D,C,D,D,D,D,D,B,B,D,D,D,D"
CT_G="D,D,D,D,D,D,D,D,D,D,D"
CT_R="D,D,D,D,D,D"
KEEP="--keep-populated-dir .scratch/f5/veto/pop3 --keep-results-dir .scratch/f5/veto/res3"

echo "############ BRIDGES (5 dataset, run 1, soglia 9) ############"
for ORDER in exposure cells; do
  PYTHONUNBUFFERED=1 $B --datasets bridges_14,bridges_28,bridges_42,bridges_56,bridges_70 \
    --runs 1 --thresholds 9 --variants "B4=dom-sub-adaptive:budget:0.4" \
    --prune-extra "--coltypes $CT_B --veto-order $ORDER" $KEEP \
    --reuse-baseline results/results_benchmark.json \
    --out "results/results_final_${ORDER}_bridges.json" 2>&1 | tee ".scratch/log_final_${ORDER}_bridges.log"
done

echo "############ GLASS (5 dataset, run 1, soglia 9) ############"
for ORDER in exposure cells; do
  PYTHONUNBUFFERED=1 $B --datasets glass_22,glass_43,glass_64,glass_86,glass_107 \
    --runs 1 --thresholds 9 --variants "B4=dom-sub-adaptive:budget:0.4" \
    --prune-extra "--coltypes $CT_G --veto-order $ORDER" $KEEP \
    --family glass --dataset-dir .scratch/glass_fixed/Dataset \
    --tuple-dir .scratch/glass_fixed/TupleIniziali \
    --reuse-baseline results/results_benchmark_glass.json \
    --out "results/results_final_${ORDER}_glass.json" 2>&1 | tee ".scratch/log_final_${ORDER}_glass.log"
done

echo "############ RESTAURANT (3 dataset, run 1, soglia 6) ############"
for ORDER in exposure cells; do
  PYTHONUNBUFFERED=1 $B --datasets restaurant_52,restaurant_104,restaurant_206 \
    --runs 1 --thresholds 6 --variants "B4=dom-sub-adaptive:budget:0.4" \
    --prune-extra "--coltypes $CT_R --veto-order $ORDER" $KEEP \
    --family restaurant --text-thr 0.8 \
    --reuse-baseline results/results_benchmark_P1_restaurant.json \
    --out "results/results_final_${ORDER}_restaurant.json" 2>&1 | tee ".scratch/log_final_${ORDER}_restaurant.log"
done

echo "############ FATTO ############"
