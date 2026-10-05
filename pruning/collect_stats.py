#!/usr/bin/env python3
"""
collect_stats.py — raccoglie statistiche di training da run RENUVER gia' eseguiti.

Serve quando le statistiche d'archivio non sono utilizzabili. E' il caso di **Glass**:
l'archivio contiene i run fatti con lo schema rotto (§7 del report), e i file
`RENUVER/Populated/results_*_glass_*.csv` registrano `?` come valore imputato per tutte
le righe. Il risultato e' che `load_training_stats` calcola 419 usi e **0 corrette** per
Glass, cioe' un segnale di precisione degenere: `precision-priority` non ha nulla su cui
ordinare e la campagna di generalizzazione diventa non informativa.

Questo script riesegue RENUVER con lo **schema corretto** (`fix_glass_schema.py`) e
**conserva** i file `Populated/` e `Results/` prodotti, cosi' che `pruning.py` possa
leggerli con `--results-dir` / `--populated-dir`.

Uso (dopo `fix_glass_schema.py`):
    python3 pruning/collect_stats.py \\
        --datasets glass_22,glass_43,glass_64,glass_86,glass_107 --runs 1,2,3,4,5 \\
        --thresholds 3,9,15 \\
        --dataset-dir .scratch/glass_fixed/Dataset \\
        --tuple-dir   .scratch/glass_fixed/TupleIniziali \\
        --out-dir     .scratch/glass_fixed

Poi si usa la cartella prodotta come sorgente delle statistiche:
    pruning/benchmark.py ... --prune-extra "--results-dir .scratch/glass_fixed/Results \\
                                             --populated-dir .scratch/glass_fixed/Populated"

I file gia' presenti non vengono rifatti: lo script e' riavviabile.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import benchmark as B          # noqa: E402
from paths import RENUVER as REN, ensure_dirs   # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--family", default="glass")
    ap.add_argument("--datasets", default="glass_22,glass_43,glass_64,glass_86,glass_107")
    ap.add_argument("--runs", default="1,2,3,4,5")
    ap.add_argument("--thresholds", default="3,9,15")
    ap.add_argument("--dataset-dir", default=None)
    ap.add_argument("--tuple-dir", default=None)
    ap.add_argument("--out-dir", default=os.path.join(".scratch", "glass_fixed"))
    ap.add_argument("--coltypes", default="B", choices=["B", "D"])
    ap.add_argument("--force", action="store_true", help="rifai anche i file gia' presenti")
    args = ap.parse_args(argv)

    ensure_dirs()
    B.ensure_lab()
    ds_dir = args.dataset_dir or os.path.join(REN, "Dataset")
    ti_dir = args.tuple_dir or os.path.join(REN, "TupleIniziali")
    pop_dir = os.path.join(args.out_dir, "Populated")
    res_dir = os.path.join(args.out_dir, "Results")
    os.makedirs(pop_dir, exist_ok=True)
    os.makedirs(res_dir, exist_ok=True)

    datasets = [d.strip() for d in args.datasets.split(",") if d.strip()]
    runs = [int(r) for r in args.runs.split(",") if r.strip()]
    thresholds = [int(t) for t in args.thresholds.split(",") if t.strip()]
    coltypes = B.coltypes_for(args.family, args.coltypes)

    done = skipped = failed = 0
    t0 = time.time()
    total = len(datasets) * len(runs) * len(thresholds)
    for thr in thresholds:
        rfd_name = B.rfd_file_for(args.family, thr)
        src_rfd = os.path.join(REN, "RFD", rfd_name)
        if not os.path.exists(src_rfd):
            print(f"  !! RFD assente: {src_rfd}", flush=True)
            continue
        for ds_name in datasets:
            for run in runs:
                ds_file = f"{ds_name}_{run}.csv"
                pop_out = os.path.join(pop_dir, f"output_{ds_file}_{thr}H0.csv")
                res_out = os.path.join(res_dir, f"output_{ds_file}_{thr}H0.txt")
                if not args.force and os.path.exists(pop_out) and os.path.exists(res_out):
                    skipped += 1
                    continue
                src_ds = os.path.join(ds_dir, ds_file)
                if not os.path.exists(src_ds):
                    print(f"  !! dataset assente: {src_ds}", flush=True)
                    continue
                shutil.copy(src_ds, os.path.join(B.LAB, "Dataset", ds_file))
                ti = os.path.join(ti_dir, ds_file)
                if os.path.exists(ti):
                    shutil.copy(ti, os.path.join(B.LAB, "TupleIniziali", ds_file))
                shutil.copy(src_rfd, os.path.join(B.LAB, "RFD", rfd_name))
                r = B.run_renuver(ds_file, thr, rfd_name, coltypes)
                lab_pop = os.path.join(B.LAB, "Populated", f"output_{ds_file}_{thr}H0.csv")
                lab_res = os.path.join(B.LAB, "Results", f"output_{ds_file}_{thr}H0.txt")
                ok = os.path.exists(lab_pop) and os.path.exists(lab_res)
                if ok:
                    shutil.copy(lab_pop, pop_out)
                    shutil.copy(lab_res, res_out)
                    done += 1
                    n_lines = sum(1 for _ in open(res_out, encoding="utf-8", errors="replace"))
                    print(f"[{time.time()-t0:6.0f}s] {ds_file} thr={thr} "
                          f"rc={r['rc']} t={r['wall_s']}s righe Results={n_lines}", flush=True)
                else:
                    failed += 1
                    print(f"[{time.time()-t0:6.0f}s] {ds_file} thr={thr} FALLITO rc={r['rc']} "
                          f"{r['err'][:80]}", flush=True)

    print(f"\nfatti {done}, saltati {skipped}, falliti {failed} su {total} previsti")
    print(f"Populated -> {pop_dir}")
    print(f"Results   -> {res_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
