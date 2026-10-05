#!/usr/bin/env bash
# =====================================================================================
# Campagna Physician (quarta famiglia) — risolve il dubbio lasciato aperto nella tesi.
#
# 1. Prepara i file TupleIniziali filtrati dalle righe con indice fuori intervallo (difetto D3):
#    le configurazioni 0.05 e 0.1 diventano eseguibili, con 121 e 168 celle valutabili invece di 0.
# 2. Esegue la campagna sulle quattro configurazioni remodulate, con tre bracci:
#    baseline (A), potatura garantita (veto-cover:protect) e potatura aggressiva (A5b).
#    Conserva Populated/ e Results/ per la verifica di equivalenza per impronta.
# 3. Sonda la configurazione piena (13 467 celle, 103 592 righe) con un limite di tempo, per
#    sostituire la stima "non trattabile" con una misura.
#
# Le esecuzioni sono sequenziali: la cartella di lavoro è condivisa e due run in parallelo
# sovrascriverebbero reciprocamente gli output senza segnalare errori.
# =====================================================================================
set -u
cd "$(dirname "$0")/../.." || exit 1
mkdir -p .scratch/f5

echo "=== 1. TupleIniziali filtrati (difetto D3) ==="
python3 pruning/prepare_physician_tuples.py || exit 1

echo
echo "=== 2. campagna sulle configurazioni remodulate ==="
python3 pruning/benchmark.py \
  --datasets "Physician_Compare_National_remodulated_0.005_13,Physician_Compare_National_remodulated_0.01_27,Physician_Compare_National_remodulated_0.05_135,Physician_Compare_National_remodulated_0.1_269" \
  --runs 1 --thresholds 3 \
  --variants "VC=veto-cover:protect,A5b=exact-priority+dom-sub-adaptive:allow" \
  --prune-extra "--adaptive-alpha 0.85" \
  --coltypes D \
  --tuple-dir .scratch/physician_ti \
  --text-thr 0.8 \
  --keep-populated-dir .scratch/physician_pop \
  --keep-results-dir .scratch/physician_res \
  --out results/results_physician_remodulated.json
rc_camp=$?
echo "campagna: rc=$rc_camp"

echo
echo "=== 3. sonda sulla configurazione piena (limite 20 minuti) ==="
python3 pruning/probe_physician_full.py --timeout 1200 --poll 30
echo "sonda: rc=$?"

echo
echo "=== fine ==="
