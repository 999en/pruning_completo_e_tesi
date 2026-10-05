#!/usr/bin/env bash
# Prompt 3 — contabilità dei veti: misurare il costo reale di ogni rimozione.
#
# La politica budget:F ordina le rimozioni per `exposure`, un proxy MAI VALIDATO.
# Qui si misura il costo empirico confrontando cella per cella il baseline con run potati:
#   VC   = veto-cover        -> TUTTE le rimozioni sono gratuite per [V2]  (atteso: 0 celle perse)
#   SB4  = score-argmin:budget:0.4 -> rimozioni quasi tutte PAGATE
#   DS   = dom-sub-adaptive  -> rimozioni tutte PAGATE (nessuna copertura [V2])
#
# Configurazioni scelte per il numero di CELLE VALUTATE (bridges_70: 70, glass_107: 107):
# RENUVER valuta solo le celle elencate in TupleIniziali, non tutti i nulli del dataset.
# Gli output sono ritenuti perche' la LAB e' condivisa e li sovrascrive a ogni run.
set -u
cd "$(dirname "$0")/../.."
B="python3 pruning/benchmark.py"
KEEP="--keep-populated-dir .scratch/f5/veto/pop --keep-results-dir .scratch/f5/veto/res"
V="VC=veto-cover:allow,SB4=score-argmin:budget:0.4,DS=dom-sub-adaptive:allow"
BRIDGES_CT="D,C,D,D,D,D,D,B,B,D,D,D,D"

echo "############ Bridges: bridges_70 run 1-3, soglia 9 ############"
PYTHONUNBUFFERED=1 $B --datasets bridges_70 --runs 1,2,3 --thresholds 9 \
  --variants "$V" --prune-extra "--coltypes $BRIDGES_CT" $KEEP \
  --out results/results_vetocost_bridges.json 2>&1 | tee .scratch/log_vetocost_bridges.log

echo
echo "############ Glass: glass_107 run 1-3, soglia 9 ############"
PYTHONUNBUFFERED=1 $B --datasets glass_107 --runs 1,2,3 --thresholds 9 \
  --variants "$V" --prune-extra "--coltypes D,D,D,D,D,D,D,D,D,D,D" \
  --family glass --dataset-dir .scratch/glass_fixed/Dataset \
  --tuple-dir .scratch/glass_fixed/TupleIniziali $KEEP \
  --out results/results_vetocost_glass.json 2>&1 | tee .scratch/log_vetocost_glass.log

echo
echo "############ FATTO ############"
