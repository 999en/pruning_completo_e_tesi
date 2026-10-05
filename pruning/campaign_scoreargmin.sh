#!/usr/bin/env bash
# Fase 6 — H2: `score-argmin` su Glass e Restaurant (e controllo di sanita' su Bridges).
#
# `score-argmin` e' l'unica strategia dimostrata ESATTA LATO GENERAZIONE (Fase 3, A1): conserva
# le RFD che sono argmin del punteggio per almeno una coppia (cella nulla, candidato). Su Bridges
# con `--veto-policy protect` l'output e' identico al baseline in 20/20 configurazioni.
# Non era mai stata provata su Glass e Restaurant, dove l'euristica A5b perde copertura.
#
# NOTA SU --maxthr. `mask_score_argmin` accetta un candidato solo se `best < maxthr`, con
# maxthr = args[4] di RENUVER; il default del pruner e' `int(max(rhs_thr))` del file RFD, che non
# sempre coincide con la soglia del run (glass@15: 12 vs 15; restaurant@3: 2 vs 3; bridges: 90/130
# vs 9/15). Per non lasciare il confronto A/B disappaiato, ogni soglia gira in una invocazione
# separata con `--maxthr <soglia>`. `pruning/probe_maxthr.py` misura che la scelta e' comunque
# ininfluente (stesso insieme conservato in tutte le 14 configurazioni provate), quindi il
# controllo di sanita' su Bridges puo' riprodurre la campagna A1 alla lettera.
#
# Ogni campagna e' sequenziale: nessun'altra campagna RENUVER deve girare in parallelo.
set -u
cd "$(dirname "$0")/.."
B="python3 pruning/benchmark.py"
GDS="glass_22,glass_43,glass_64,glass_86,glass_107"
RDS="restaurant_52,restaurant_104,restaurant_206"
GCT="--coltypes D,D,D,D,D,D,D,D,D,D,D"     # args0 di RENUVER per Glass
RCT="--coltypes D,D,D,D,D,D"               # args0 di RENUVER per Restaurant
VAR="SAa=score-argmin:allow,SAb=score-argmin:budget:0.5"

# ---------------------------------------------------------------- Glass (5 ds x run 1-2 x 3/9/15)
for T in 3 9 15; do
  echo "############ Glass — score-argmin, soglia $T (maxthr=$T) ############"
  PYTHONUNBUFFERED=1 $B --datasets "$GDS" --runs 1,2 --thresholds "$T" \
    --variants "$VAR" \
    --prune-extra "$GCT --maxthr $T" \
    --family glass --dataset-dir .scratch/glass_fixed/Dataset \
    --tuple-dir .scratch/glass_fixed/TupleIniziali \
    --reuse-baseline results/results_benchmark_glass.json \
    --out "results/results_scoreargmin_glass_t$T.json" 2>&1 | tee ".scratch/log_scoreargmin_glass_t$T.log"
done

# ------------------------------------------------------- Restaurant (3 ds x run 1-2 x 3/6, testo)
for T in 3 6; do
  echo "############ Restaurant — score-argmin, soglia $T (maxthr=$T) ############"
  PYTHONUNBUFFERED=1 $B --datasets "$RDS" --runs 1,2 --thresholds "$T" \
    --variants "$VAR" \
    --prune-extra "$RCT --maxthr $T" \
    --family restaurant --text-thr 0.8 \
    --reuse-baseline results/results_benchmark_P1_restaurant.json \
    --out "results/results_scoreargmin_restaurant_t$T.json" 2>&1 | tee ".scratch/log_scoreargmin_restaurant_t$T.log"
done

# ------------------------------------------- Bridges: riproduzione letterale della campagna A1
echo "############ Bridges — controllo di sanita' (riproduzione A1) ############"
PYTHONUNBUFFERED=1 $B --datasets "bridges_14,bridges_28,bridges_42,bridges_56,bridges_70" \
  --runs 1,2,3 --thresholds 9,15 \
  --variants "B1a=score-argmin:allow,B1b=score-argmin:budget:0.5" \
  --prune-extra "--coltypes D,C,D,D,D,D,D,B,B,D,D,D,D" \
  --reuse-baseline results/results_benchmark.json \
  --out results/results_scoreargmin_bridges_sanity.json 2>&1 | tee .scratch/log_scoreargmin_bridges.log

# ---------------------------------------------------------------------------------- ricomposizione
python3 pruning/merge_results.py --out results/results_scoreargmin_glass.json \
  results/results_scoreargmin_glass_t3.json results/results_scoreargmin_glass_t9.json \
  results/results_scoreargmin_glass_t15.json
python3 pruning/merge_results.py --out results/results_scoreargmin_restaurant.json \
  results/results_scoreargmin_restaurant_t3.json results/results_scoreargmin_restaurant_t6.json

echo "TUTTE LE CAMPAGNE DELLA FASE 6 COMPLETATE"
