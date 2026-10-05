#!/usr/bin/env python3
"""
order_analysis.py — dove agisce davvero il riordino dei cluster?

Serve a rendere riproducibile l'analisi del §12.5 del report. Genera il file RFD potato
con `precision-priority` per diversi valori di α, poi **rilegge i file prodotti** e mostra,
colonna per colonna, l'ordine dei cluster mettendo in evidenza la PRIMA e l'ULTIMA posizione.

Perche' contano primo e ultimo: `treatNullTuple` ha due rami con posizione decisiva opposta.

  * mono-cella  (`nullFields.size() == 1`): `break` al primo cluster che riesce  -> vince il PRIMO;
  * multi-cella (`nullFields.size() > 1`): il blocco di imputazione e' dentro il ciclo sui round
    `for (int i = 0; i < maxNumberOfClusters; i++)` e `populateFieldSingleAttribute` non verifica
    se la cella e' gia' piena -> ogni round sovrascrive -> vince l'ULTIMO cluster produttivo.

Uso:
    python3 pruning/order_analysis.py                          # bridges_14_1, soglia 9, alpha 0/1/3/10
    python3 pruning/order_analysis.py --threshold 15 --dataset bridges_28_1
    python3 pruning/order_analysis.py --alphas 0,0.5,0.85,1,3,10
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pruning as P                      # noqa: E402
from paths import ROOT, RENUVER, RESULTS, SCRATCH, ensure_dirs   # noqa: E402

FAMILIES = {
    "bridges": "bridges", "restaurant": "restaurant", "glass": "glass",
    "nursery": "nursery", "Physician_Compare_National": "Physician_Compare_National",
}


def order_of(path):
    """Ordine dei cluster per colonna RHS, letto da un file RFD."""
    raw = P.read_lines(path)
    header = raw[0].split(";")
    out = collections.defaultdict(list)
    for line in raw[1:]:
        p = P.parse_rfd_row(header, line)
        if not p:
            continue
        thr = round(float(p["rhs_thr"]), 9)
        if thr not in out[p["rhs"]]:
            out[p["rhs"]].append(thr)
    return out


def generate(alpha, family, threshold, dataset, out_dir):
    rfd_name = FAMILIES.get(family, family)
    out = os.path.join(out_dir, f"ord_a{alpha:g}.csv")
    cmd = [sys.executable, os.path.join(HERE, "pruning.py"),
           "--rfd", os.path.join(RENUVER, "RFD", f"output_false_{threshold}_{rfd_name}.csv"),
           "--dataset", os.path.join(RENUVER, "Dataset", f"{dataset}.csv"),
           "--output", out, "--strategy", "precision-priority", "--veto-policy", "allow",
           "--precision-alpha", str(alpha),
           "--results-dir", os.path.join(RENUVER, "Results"),
           "--populated-dir", os.path.join(RENUVER, "Populated"),
           "--family", family, "--exclude", re.escape(dataset)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"[errore] pruning.py: {r.stderr[:400]}")
    return out


def fmt(v):
    return format(v, "g")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--family", default="bridges")
    ap.add_argument("--threshold", type=int, default=9)
    ap.add_argument("--dataset", default="bridges_14_1")
    ap.add_argument("--alphas", default="0,1,3,10")
    ap.add_argument("--out-dir", default=os.path.join(SCRATCH, "order_analysis"))
    args = ap.parse_args()

    ensure_dirs()
    os.makedirs(args.out_dir, exist_ok=True)
    alphas = [float(a) for a in args.alphas.split(",")]
    files = {a: generate(a, args.family, args.threshold, args.dataset, args.out_dir) for a in alphas}
    orders = {a: order_of(f) for a, f in files.items()}

    base_a = alphas[0]
    base = orders[base_a]
    cols = sorted(base, key=lambda c: -len(base[c]))

    print("=" * 108)
    print(f"ORDINE DEI CLUSTER — {args.dataset}, famiglia {args.family}, soglia RFD {args.threshold}")
    print(f"strategia: precision-priority; esclusione dal training: {args.dataset}")
    print("=" * 108)
    n_multi = sum(1 for c in cols if len(base[c]) > 1)
    print(f"colonne RHS: {len(cols)}   cluster totali: {sum(len(base[c]) for c in cols)}   "
          f"colonne con >=2 cluster (dove l'ordine puo' contare): {n_multi}\n")

    for c in cols:
        if len(base[c]) < 2:
            continue
        print(f"{c}  ({len(base[c])} cluster)")
        for a in alphas:
            seq = orders[a][c]
            first = "PRIMO" if True else ""
            mark = "  " if (a == base_a or seq == base[c]) else " *"
            print(f"   a={fmt(a):<6}{' > '.join(fmt(x) for x in seq):<44}"
                  f"  primo={fmt(seq[0]):<5} ultimo={fmt(seq[-1]):<5}{mark}")
        print()

    print("-" * 108)
    print("SINTESI: quali posizioni cambiano rispetto ad α = %s" % fmt(base_a))
    print(f"{'alpha':>8}{'primo cambia in':>34}{'ultimo cambia in':>34}")
    for a in alphas[1:]:
        pr = [c for c in cols if orders[a][c][0] != base[c][0]]
        ul = [c for c in cols if orders[a][c][-1] != base[c][-1]]
        print(f"{fmt(a):>8}{len(pr):>3} colonne  {str(pr):<40}{len(ul):>3} colonne  {str(ul):<30}")
    print("-" * 108)
    print("Se nei tuple multi-cella decidesse il PRIMO cluster, ogni riga con 'primo' non vuoto")
    print("dovrebbe cambiare l'esito. Se decide l'ULTIMO, contano solo le righe con 'ultimo' non vuoto.")

    json.dump({fmt(a): {c: [fmt(x) for x in orders[a][c]] for c in orders[a]} for a in alphas},
              open(os.path.join(args.out_dir, "orders.json"), "w"), indent=1)
    print(f"\nordini salvati in {os.path.join(args.out_dir, 'orders.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
