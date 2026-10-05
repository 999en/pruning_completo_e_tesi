#!/usr/bin/env bash
# Verifica empirica di [V2] su piu' configurazioni (H7).
# Gira a priorita' bassa per non disturbare le misure di tempo della campagna.
set -u
cd "$(dirname "$0")/.."
OUT=.scratch/verify_out
mkdir -p "$OUT"
CT="D,C,D,D,D,D,D,B,B,D,D,D,D"
LOG=.scratch/log_verify_veto.log
: > "$LOG"

run_case () {
  local DS="$1" THR="$2"
  local PR="$OUT/vc_${DS}_${THR}.csv"
  nice -n 19 python3 pruning/pruning.py \
      --rfd "RENUVER/RFD/output_false_${THR}_bridges.csv" \
      --dataset "RENUVER/Dataset/${DS}.csv" \
      --output "$PR" --strategy veto-cover --veto-policy allow > /dev/null 2>&1
  echo "######## $DS  soglia $THR ########" | tee -a "$LOG"
  nice -n 19 python3 pruning/verify_veto.py \
      --rfd-full "RENUVER/RFD/output_false_${THR}_bridges.csv" \
      --rfd-pruned "$PR" \
      --dataset "RENUVER/Dataset/${DS}.csv" \
      --coltypes "$CT" --maxthr "$THR" 2>&1 \
    | grep -E "RFD rimosse|senza copritrice|terne|discrepanze|ESITO|avviso" | tee -a "$LOG"
  echo | tee -a "$LOG"
}

for THR in 3 6 9 12 15; do run_case bridges_42_1 "$THR"; done
run_case bridges_14_1 15
run_case bridges_70_1 9
run_case bridges_70_1 15
run_case bridges_28_5 12
echo "VERIFICA COMPLETATA" | tee -a "$LOG"
