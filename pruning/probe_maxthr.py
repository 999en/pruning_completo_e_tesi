#!/usr/bin/env python3
"""
probe_maxthr.py — Diagnostica di appaiamento di `--maxthr` per la strategia `score-argmin`.

`mask_score_argmin` usa `maxthr` in due punti: il peso delle colonne `B` (irrilevante qui, tutte
le famiglie in esame sono `D`) e la porta di accettazione `best < maxthr`. Se non si passa
`--maxthr`, il default e' `int(max(rhs_thr))` del file RFD, che **non sempre coincide** con la
soglia passata a RENUVER come args[4] (il baseline usa args[4] = soglia).

Poiche' il confronto A/B e' appaiato solo se i due `maxthr` coincidono, questo script misura se la
scelta cambia l'insieme conservato. Non esegue RENUVER: solo il pruner, e usa numpy (strategia
`score-argmin`).

I casi Glass richiedono i dataset con lo **schema corretto** (`.scratch/glass_fixed/Dataset`),
che non fa parte di questo pacchetto: se la cartella manca, quei casi vengono saltati con un
avviso e lo script prosegue con Bridges e Restaurant, che stanno nell'archivio.

    python3 pruning/probe_maxthr.py                      # stampa una tabella
    python3 pruning/probe_maxthr.py --quick              # un solo dataset per famiglia
    python3 pruning/probe_maxthr.py --only bridges       # solo una famiglia
    python3 pruning/probe_maxthr.py --glass-dir .scratch/glass_fixed/Dataset

La griglia completa richiede parecchi minuti: la strategia costruisce una matrice di distanza
n x n per ogni colonna, e le colonne testuali usano la distanza di Levenshtein scritta in Python.
Per questo `--quick` limita la griglia al primo dataset di ogni famiglia.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pruning as P
from paths import ROOT, RENUVER as REN

CASES = [
    # (family, threshold, datasets, dataset_dir, coltypes)
    ("glass", 15, ["glass_22", "glass_43", "glass_64", "glass_86", "glass_107"],
     os.path.join(ROOT, ".scratch", "glass_fixed", "Dataset"), "D,D,D,D,D,D,D,D,D,D,D"),
    ("glass", 3, ["glass_22"], os.path.join(ROOT, ".scratch", "glass_fixed", "Dataset"),
     "D,D,D,D,D,D,D,D,D,D,D"),
    ("glass", 9, ["glass_22"], os.path.join(ROOT, ".scratch", "glass_fixed", "Dataset"),
     "D,D,D,D,D,D,D,D,D,D,D"),
    ("restaurant", 3, ["restaurant_52", "restaurant_104", "restaurant_206"],
     os.path.join(REN, "Dataset"), "D,D,D,D,D,D"),
    ("bridges", 9, ["bridges_14", "bridges_28"], os.path.join(REN, "Dataset"),
     "D,C,D,D,D,D,D,B,B,D,D,D,D"),
    ("bridges", 15, ["bridges_14", "bridges_28"], os.path.join(REN, "Dataset"),
     "D,C,D,D,D,D,D,B,B,D,D,D,D"),
]

RUN = 1

GLASS_HINT = ("python3 pruning/fix_glass_schema.py --output-dir .scratch/glass_fixed/Dataset "
              "--tuple-dir RENUVER/TupleIniziali --tuple-output-dir .scratch/glass_fixed/TupleIniziali")


def load(family, thr, ds_name, ds_dir, ct):
    rfd_path = os.path.join(REN, "RFD", f"output_false_{thr}_{family}.csv")
    lines = P.read_lines(rfd_path)
    header = lines[0].split(";")
    parsed = [p for p in (P.parse_rfd_row(header, l) for l in lines[1:]) if p]
    attrs, dsrows = P.read_dataset(os.path.join(ds_dir, f"{ds_name}_{RUN}.csv"))
    types = {a: (ct.split(",")[i] if i < len(ct.split(",")) else "D") for i, a in enumerate(attrs)}
    return parsed, dsrows, attrs, types


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Diagnostica di appaiamento di --maxthr per `score-argmin` (solo pruner).")
    ap.add_argument("--glass-dir", default=os.path.join(ROOT, ".scratch", "glass_fixed", "Dataset"),
                    help="dataset Glass con lo schema corretto (creati da fix_glass_schema.py)")
    ap.add_argument("--only", default=None,
                    help="esegue solo le famiglie indicate, separate da virgola (es. bridges)")
    ap.add_argument("--quick", action="store_true",
                    help="un solo dataset per famiglia (verifica rapida della strumentazione)")
    ap.add_argument("--out", default=os.path.join(ROOT, ".scratch", "probe_maxthr.json"))
    args = ap.parse_args(argv)
    only = {f.strip() for f in args.only.split(",")} if args.only else None

    out, skipped = [], 0
    for family, thr, datasets, ds_dir, ct in CASES:
        if only and family not in only:
            continue
        if family == "glass":
            ds_dir = args.glass_dir
        for ds_name in (datasets[:1] if args.quick else datasets):
            ds_path = os.path.join(ds_dir, f"{ds_name}_{RUN}.csv")
            if not os.path.exists(ds_path):
                print(f"[salto] {family:11s} {ds_name:15s} manca {os.path.relpath(ds_path, ROOT)}; "
                      f"per ricrearlo: {GLASS_HINT}", flush=True) if family == "glass" else \
                    print(f"[salto] {family:11s} {ds_name:15s} manca {os.path.relpath(ds_path, ROOT)}",
                          flush=True)
                skipped += 1
                continue
            parsed, dsrows, attrs, types = load(family, thr, ds_name, ds_dir, ct)
            default_mt = int(max(p["rhs_thr"] for p in parsed))
            t0 = time.time()
            keep_paired = P.mask_score_argmin(parsed, dsrows, attrs, types, thr)
            t1 = time.time()
            keep_default = (P.mask_score_argmin(parsed, dsrows, attrs, types, default_mt)
                            if default_mt != thr else list(keep_paired))
            t2 = time.time()
            n = len(parsed)
            kp, kd = sum(keep_paired), sum(keep_default)
            diff = sum(1 for a, b in zip(keep_paired, keep_default) if a != b)
            rhs0 = [i for i, p in enumerate(parsed) if p["rhs_thr"] == 0.0]
            rhs0_kept = sum(1 for i in rhs0 if keep_paired[i])
            extra = [i for i in range(n) if keep_default[i] and not keep_paired[i]]
            rec = dict(family=family, threshold=thr, dataset=ds_name, run=RUN,
                       n_rfd=n, maxthr_default=default_mt, maxthr_paired=thr,
                       kept_paired=kp, kept_default=kd, kept_diff=diff,
                       paired_subset_of_default=all(keep_paired[i] or not keep_default[i]
                                                    for i in range(n)),
                       rhs_thr0_total=len(rhs0), rhs_thr0_kept=rhs0_kept,
                       n_only_default=len(extra),
                       t_paired_s=round(t1 - t0, 1), t_default_s=round(t2 - t1, 1))
            out.append(rec)
            print(f"{family:11s} thr={thr:<3d} {ds_name:15s} n={n:<6d} "
                  f"maxthr def={default_mt:<4d} paired={thr:<4d} kept {kp} vs {kd} "
                  f"(diff={diff}, solo-default={len(extra)}) "
                  f"rhs0 {rhs0_kept}/{len(rhs0)}  [{rec['t_paired_s']}s]",
                  flush=True)
    dest = args.out
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(f"\nscritto: {os.path.relpath(dest, ROOT)}  ({len(out)} configurazioni, "
          f"{skipped} saltate)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
