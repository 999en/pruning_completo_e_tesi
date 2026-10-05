#!/usr/bin/env bash
# A/B dell'ordinamento del budget: `exposure` (proxy, default) contro `cells` (celle reali).
# Stesse configurazioni, stesso budget F, stesso set di rimozioni candidate: cambia solo
# l'ORDINE con cui si sceglie quali rimuovere.
set -u
cd "$(dirname "$0")/../.."
B="python3 pruning/benchmark.py"
KEEP="--keep-populated-dir .scratch/f5/veto/pop2 --keep-results-dir .scratch/f5/veto/res2"
CT="D,C,D,D,D,D,D,B,B,D,D,D,D"
for ORDER in exposure cells; do
  echo "############ ordinamento: $ORDER ############"
  PYTHONUNBUFFERED=1 $B --datasets bridges_70,bridges_56 --runs 1,2 --thresholds 9 \
    --variants "B4=dom-sub-adaptive:budget:0.4" \
    --prune-extra "--coltypes $CT --veto-order $ORDER" $KEEP \
    --out "results/results_vetoorder_${ORDER}.json" 2>&1 | tee ".scratch/log_vetoorder_${ORDER}.log"
done
echo "############ FATTO ############"
