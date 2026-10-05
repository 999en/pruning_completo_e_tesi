#!/usr/bin/env python3
"""ESPERIMENTO DECISIVO — dove agisce davvero la leva d'ordine?

Il bytecode dice due cose opposte per i due rami di `treatNullTuple`:

  * ramo MONO-nullo  : scorre i cluster della colonna e si ferma al PRIMO che
                       produce un candidato  ->  vince il PRIMO cluster produttivo;
  * ramo MULTI-nullo : il blocco di imputazione sta DENTRO il ciclo `for i`, e
                       `populateFieldSingleAttribute` non verifica se la cella e' gia'
                       piena -> ogni round SOVRASCRIVE -> vince l'ULTIMO cluster produttivo.

Questo esperimento contrappone le due previsioni in modo pulito: il file RFD e' gia'
raggruppato in 13 blocchi di colonna contigui, con i cluster contigui dentro ciascuno.
Si permuta SOLO l'ordine dei cluster dentro ogni colonna:

  first-best : cluster ordinati per precisione DECRESCENTE (il migliore per primo)
  last-best  : cluster ordinati per precisione CRESCENTE  (il migliore per ultimo)
  random     : permutazione casuale (seme fisso) — CONTROLLO

Il braccio `random` serve a distinguere due spiegazioni del guadagno di `precision-priority`:
se anche una permutazione casuale guadagnasse come `first-best`, allora il guadagno non viene
dall'informazione di precisione ma dal semplice *mescolamento*; se `random` resta al baseline,
il guadagno e' specifico dell'ordinamento per precisione.

Se vince il PRIMO cluster -> `first-best` deve battere `last-best`.
Se vince l'ULTIMO cluster -> `last-best` deve battere `first-best`.

In tutti i casi il numero di RFD resta identico (8961): si misura l'ordine puro,
senza rimozioni. Nessuna modifica al JAR.

Uso (dalla radice della cartella):
    python3 pruning/exp_order.py [dataset,dataset,...] [soglie] [run] [famiglia] [--out file]
    python3 pruning/exp_order.py bridges_14,bridges_28,bridges_42 9 1 bridges

Scrive `results/analisi/exp_order.json` (percorso forzabile con `--out`); l'analisi dei tre
confronti appaiati e' in `pruning/analyze_order.py`.
"""
from __future__ import annotations

import collections
import json
import os
import random
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import benchmark as B          # noqa: E402
import pruning as P            # noqa: E402
from paths import RESULTS      # noqa: E402

OUT = os.path.join(RESULTS, "analisi", "exp_order.json")
MODES = ("orig", "first-best", "last-best", "random")


def build_order(thr, family, ds_name, mode, out_path):
    """Riscrive il file RFD permutando i cluster DENTRO ogni colonna."""
    rfd = os.path.join(B.REN, "RFD", B.rfd_file_for(family, thr))
    raw = P.read_lines(rfd)
    header = raw[0].split(";")
    stats = P.load_training_stats(os.path.join(B.REN, "Results"), os.path.join(B.REN, "Populated"),
                                  family, exclude=re.escape(ds_name))
    cprec = P.cluster_precision_from_stats(stats)

    blocks, idx = [], {}
    for i, line in enumerate(raw[1:]):
        p = P.parse_rfd_row(header, line)
        if p is None:
            continue
        k = (p["rhs"], round(float(p["rhs_thr"]), 9))
        if k not in idx:
            idx[k] = len(blocks)
            blocks.append({"col": p["rhs"], "thr": k[1], "first": i, "lines": []})
        blocks[idx[k]]["lines"].append(line)

    col_order = []
    for b in blocks:
        if b["col"] not in col_order:
            col_order.append(b["col"])

    def prec(b):
        return P.get_cluster_precision(b["col"], b["thr"], cprec, alpha=0.0)

    out = [raw[0]]
    for col in col_order:
        mine = [b for b in blocks if b["col"] == col]
        if mode == "first-best":
            mine.sort(key=lambda b: (-prec(b), b["first"]))
        elif mode == "last-best":
            mine.sort(key=lambda b: (prec(b), b["first"]))
        elif mode == "random":
            rng = random.Random(20260921)      # seme fisso: esperimento riproducibile
            rng.shuffle(mine)
        elif mode != "orig":
            raise ValueError(mode)
        for b in mine:
            out.extend(b["lines"])
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    return len(out) - 1


def run_one(ds_name, run_no, thr, rfd_path, family):
    ds_file = f"{ds_name}_{run_no}.csv"
    rfd_name = B.rfd_file_for(family, thr)
    shutil.copy(os.path.join(B.REN, "Dataset", ds_file), os.path.join(B.LAB, "Dataset", ds_file))
    ti = os.path.join(B.REN, "TupleIniziali", ds_file)
    if os.path.exists(ti):
        shutil.copy(ti, os.path.join(B.LAB, "TupleIniziali", ds_file))
    shutil.copy(rfd_path, os.path.join(B.LAB, "RFD", rfd_name))
    coltypes = B.coltypes_for(family, "B")
    r = B.run_renuver(ds_file, thr, rfd_name, coltypes)
    n_in = B.count_rfd_lines(rfd_path)
    m = B.metrics_from(r["pop_rows"], r["log"], r["results_path"], n_in, n_in, r["wall_s"])
    return m, r


def parse_args(argv):
    """Argomenti posizionali (dataset, soglie, run, famiglia) piu' l'opzione `--out`."""
    out, pos, i = OUT, [], 0
    while i < len(argv):
        if argv[i] == "--out":
            if i + 1 >= len(argv):
                sys.exit("[errore] --out richiede un percorso")
            out = argv[i + 1]
            i += 2
            continue
        pos.append(argv[i])
        i += 1
    return (pos[0].split(",") if len(pos) > 0 else ["bridges_14", "bridges_28", "bridges_42"],
            [int(t) for t in (pos[1].split(",") if len(pos) > 1 else ["9"])],
            [int(x) for x in (pos[2].split(",") if len(pos) > 2 else ["1"])],
            pos[3] if len(pos) > 3 else "bridges",
            out)


def main():
    global OUT
    B.ensure_dirs()
    B.ensure_lab()
    ds_list, thr_list, runs, family, OUT = parse_args(sys.argv[1:])
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)

    records = []
    for thr in thr_list:
        for ds_name in ds_list:
            for run_no in runs:
                paths = {}
                for mode in MODES:
                    p = os.path.join(B.PRUNED_DIR, f"ord_{mode}_{ds_name}_{run_no}_{thr}.csv")
                    n = build_order(thr, family, ds_name, mode, p)
                    paths[mode] = (p, n)
                digests = {m: B.file_digest(paths[m][0]) for m in paths}
                print(f"\n=== {ds_name}_{run_no} thr={thr} — RFD per variante: "
                      f"{ {m: paths[m][1] for m in paths} }")
                for m in MODES:
                    if m != "orig" and digests[m] == digests["orig"]:
                        print(f"  [avviso] '{m}' identico a 'orig' (permutazione vacua)")
                for mode in MODES:
                    met, r = run_one(ds_name, run_no, thr, paths[mode][0], family)
                    met.update(variant=f"ord:{mode}", dataset=ds_name, run=run_no,
                               threshold=thr, family=family, rfd=paths[mode][1],
                               rfd_md5=digests[mode][:12], rc=r["rc"])
                    records.append(met)
                    print(f"   {mode:<11} acc={met['accuracy']:.4f} prec="
                          f"{(met['precision'] or 0):.4f} cov={met['coverage']:.4f} "
                          f"corr={met['correct']:>3} err={met['wrong']:>3} "
                          f"t={r['wall_s']:>6.1f}s md5={digests[mode][:8]}")
                json.dump(records, open(OUT, "w"), indent=1)
    print(f"\nscritto {OUT}  ({len(records)} record)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
