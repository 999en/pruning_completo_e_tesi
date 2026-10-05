#!/usr/bin/env bash
# Validazione della correzione della politica sui veti.
#
# Dopo il fix:
#   * `veto-cover` da solo deve restare IDENTICO (nessuna regressione);
#   * `veto-cover:protect` non deve piu' collassare a ~0 (prima ripristinava anche le
#     rimozioni che [V2] aveva dimostrato gratuite);
#   * l'output deve restare identico al baseline, perche' [V2] e' un teorema.
set -u
cd "$(dirname "$0")/../.."
B="python3 pruning/benchmark.py"

echo "############ Bridges: veto-cover con protect e allow ############"
PYTHONUNBUFFERED=1 $B --datasets bridges_14,bridges_28,bridges_42 --runs 1 --thresholds 9 \
  --variants "VCp=veto-cover:protect,VCa=veto-cover:allow" \
  --reuse-baseline results/results_benchmark.json \
  --out results/results_vetofix_bridges.json 2>&1 | tee .scratch/log_vetofix_bridges.log

echo
echo "############ Glass (sparso) ############"
PYTHONUNBUFFERED=1 $B --datasets glass_22,glass_43 --runs 1 --thresholds 9 \
  --variants "VCp=veto-cover:protect" --family glass \
  --dataset-dir .scratch/glass_fixed/Dataset --tuple-dir .scratch/glass_fixed/TupleIniziali \
  --reuse-baseline results/results_benchmark_glass.json \
  --out results/results_vetofix_glass.json 2>&1 | tee .scratch/log_vetofix_glass.log

echo
echo "############ FATTO ############"
