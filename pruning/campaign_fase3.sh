#!/usr/bin/env bash
# Fase 3 — campagne di benchmark. Va eseguito dalla radice del progetto.
# Ogni campagna e' sequenziale per non falsare le misure di tempo.
set -u
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
B="python3 pruning/benchmark.py"
DS="bridges_14,bridges_28,bridges_42,bridges_56,bridges_70"

echo "############ A1 — score-argmin ############"
PYTHONUNBUFFERED=1 $B --datasets "$DS" --runs 1,2,3 --thresholds 9,15 \
  --variants "A1a=score-argmin:allow,A1b=score-argmin:budget:0.5" \
  --prune-extra "--coltypes D,C,D,D,D,D,D,B,B,D,D,D,D" \
  --reuse-baseline results/results_benchmark.json \
  --out results/results_benchmark_A1.json 2>&1 | tee .scratch/log_A1.log

echo "############ A1p — score-argmin con veto protetti (test H1) ############"
PYTHONUNBUFFERED=1 $B --datasets "$DS" --runs 1,2 --thresholds 9,15 \
  --variants "A1p=score-argmin:protect" \
  --prune-extra "--coltypes D,C,D,D,D,D,D,B,B,D,D,D,D" \
  --reuse-baseline results/results_benchmark.json \
  --out results/results_benchmark_A1p.json 2>&1 | tee .scratch/log_A1p.log

echo "############ A2 — dom-sub-adaptive (alpha 0.85 e 0.90) ############"
for A in 0.85 0.90; do
  PYTHONUNBUFFERED=1 $B --datasets "$DS" --runs 1,2 --thresholds 6,9,15 \
    --variants "A2=dom-sub-adaptive:allow" \
    --prune-extra "--adaptive-alpha $A --adaptive-side stable" \
    --reuse-baseline results/results_benchmark.json \
    --out "results/results_benchmark_A2_${A}.json" 2>&1 | tee ".scratch/log_A2_${A}.log"
done

echo "############ A2u — dom-sub-adaptive lato instabile ############"
PYTHONUNBUFFERED=1 $B --datasets "$DS" --runs 1,2 --thresholds 6,9,15 \
  --variants "A2u=dom-sub-adaptive:allow" \
  --prune-extra "--adaptive-alpha 0.85 --adaptive-side unstable" \
  --reuse-baseline results/results_benchmark.json \
  --out results/results_benchmark_A2u.json 2>&1 | tee .scratch/log_A2u.log

echo "############ A4 — exact-priority (riordino del file RFD) ############"
PYTHONUNBUFFERED=1 $B --datasets "$DS" --runs 1,2 --thresholds 9,15 \
  --variants "A4=exact-priority:allow" \
  --reuse-baseline results/results_benchmark.json \
  --out results/results_benchmark_A4.json 2>&1 | tee .scratch/log_A4.log

echo "############ B1 — Glass con schema corretto ############"
PYTHONUNBUFFERED=1 $B --datasets glass_22,glass_43,glass_64,glass_86,glass_107 --runs 1,2,3,4,5 \
  --thresholds 3,9,15 \
  --variants "S4=veto-cover:allow" \
  --dataset-dir .scratch/glass_fixed/Dataset --tuple-dir .scratch/glass_fixed/TupleIniziali \
  --out results/results_benchmark_glass.json 2>&1 | tee .scratch/log_glass.log

echo "############ B2 — Restaurant (metrica testuale) ############"
PYTHONUNBUFFERED=1 $B --datasets restaurant_52,restaurant_104,restaurant_206,restaurant_259 --runs 1,2 \
  --thresholds 3,6 \
  --variants "S4=veto-cover:allow" --text-thr 0.8 \
  --out results/results_benchmark_restaurant.json 2>&1 | tee .scratch/log_restaurant.log

echo "############ A3 — riordino delle righe del dataset ############"
for HEUR in null-count lhs-involvement; do
  D=".scratch/reorder/$HEUR"
  mkdir -p "$D/Dataset" "$D/TupleIniziali"
  for LVL in 14 28 42 56 70; do
    for RUN in 1 2; do
      python3 pruning/reorder_dataset.py \
        --dataset "RENUVER/Dataset/bridges_${LVL}_${RUN}.csv" \
        --rfd "RENUVER/RFD/output_false_9_bridges.csv" \
        --heuristic "$HEUR" \
        --output "$D/Dataset/bridges_${LVL}_${RUN}.csv" \
        --tuple-out "$D/TupleIniziali/bridges_${LVL}_${RUN}.csv" >/dev/null
    done
  done
  PYTHONUNBUFFERED=1 $B --datasets "$DS" --runs 1,2 --thresholds 9,15 \
    --variants "A3=duplicates:allow" \
    --dataset-dir "$D/Dataset" --tuple-dir "$D/TupleIniziali" \
    --out "results/results_benchmark_A3_${HEUR}.json" 2>&1 | tee ".scratch/log_A3_${HEUR}.log"
done

echo "TUTTE LE CAMPAGNE COMPLETATE"
