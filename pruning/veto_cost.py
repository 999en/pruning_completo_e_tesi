#!/usr/bin/env python3
"""
veto_cost.py — contabilità empirica del costo di ogni rimozione.

La politica `--veto-policy budget:F` ordina le RFD da rimuovere per `exposure` (somma del
profilo dei nulli sulle colonne del LHS), che è un PROXY della probabilità che un veto si
eserciti davvero. Questo script lo sostituisce con una MISURA.

Metodo
------
RENUVER valuta solo le celle elencate in `TupleIniziali` (formato `riga;attributo;valore`),
non tutti i nulli del dataset. Per ogni cella valutata si confronta l'esito nel baseline con
l'esito in un run potato, usando i `Populated/` ritenuti da `benchmark.py`
(`--keep-populated-dir`).

Una cella **persa** è una cella imputata nel baseline e non imputata nel run potato.

Attribuzione: una RFD rimossa `r` *poteva servire* la cella `(riga i, colonna C)` se
  * RHS(r) == C, e
  * esiste una riga candidata j != i con valore non nullo in C e, per ogni colonna c del LHS,
    |rows[j][c] − rows[i][c]| <= soglia_r(c)  (la stessa condizione che RENUVER valuta fra
    tupla nulla e tupla candidata).

Classificazione delle rimozioni: una RFD rimossa è **gratuita** se il suo veto è implicato da
una RFD sopravvissuta ([V2], `veto_covered_indices` con `alive` = insieme finale), **pagata**
altrimenti.

Uso:
    python3 pruning/veto_cost.py --json results/results_vetocost_bridges.json \
        --pop-dir .scratch/f5/veto/pop --dataset bridges_70_1 --threshold 9
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pruning as P                      # noqa: E402
from paths import RENUVER, PRUNED_DIR, SCRATCH   # noqa: E402


def read_pop(path):
    """-> {(riga, attributo): valore_imputato}"""
    out = {}
    if not os.path.exists(path):
        return out
    for i, line in enumerate(open(path, encoding="utf-8", errors="replace")):
        q = line.rstrip("\n").split(";")
        if i == 0 and q and q[0].lower().startswith("riga"):
            continue
        if len(q) >= 4:
            out[(q[0].strip(), q[1].strip())] = q[3].strip()
    return out


def lost_cells(base, var):
    """Celle imputate nel baseline e NON imputate nel run potato."""
    return sorted((k for k, v in base.items() if v not in ("?", "") and var.get(k, "?") in ("?", "")))


def gained_cells(base, var):
    return sorted((k for k, v in var.items() if v not in ("?", "") and base.get(k, "?") in ("?", "")))


def rfd_can_serve(rfd, i, col, rows, attrs):
    """Esiste una riga candidata j != i che soddisfa il LHS di rfd e ha `col` non nulla?"""
    lhs = rfd["lhs"]
    if rfd["rhs"] != col or not lhs:
        return False
    row_i = rows[i]
    for c in lhs:
        if P.is_null(row_i.get(c, "?")):
            return False                      # condizione non valutabile
    for j, rj in enumerate(rows):
        if j == i or P.is_null(rj.get(col, "?")):
            continue
        ok = True
        for c, thr in lhs.items():
            vj, vi = rj.get(c, "?"), row_i.get(c, "?")
            if P.is_null(vj) or P.is_null(vi):
                ok = False
                break
            try:
                if abs(float(vj) - float(vi)) > float(thr):
                    ok = False
                    break
            except ValueError:
                if vj != vi:
                    ok = False
                    break
        if ok:
            return True
    return False


def spearman(x, y):
    n = len(x)
    if n < 3:
        return None, n

    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        rk = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                rk[order[k]] = avg
            i = j + 1
        return rk
    rx, ry = rank(x), rank(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return (num / (dx * dy) if dx and dy else None), n


def rfd_lines(path, alive_mask=None):
    raw = P.read_lines(path)
    header = raw[0].split(";")
    out = []
    for k, line in enumerate(raw[1:]):
        p = P.parse_rfd_row(header, line)
        if p is not None:
            out.append((line, p))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", required=True, help="JSON della campagna (per la mappa variante→strategia)")
    ap.add_argument("--pop-dir", required=True)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--threshold", type=int, default=9)
    ap.add_argument("--rfd", required=True, help="file RFD ORIGINALE usato dalla campagna")
    ap.add_argument("--dataset-file", required=True, help="CSV del dataset")
    ap.add_argument("--max-extra", type=int, default=3)
    args = ap.parse_args()

    # RENUVER scrive `output_<file del dataset>_<soglia>H<euristica>.csv`, e il file del dataset
    # contiene gia' il numero della ripetizione: il nome atteso e' quindi
    # `output_<dataset>.csv_<soglia>H0.csv`. La seconda forma copre la convenzione usata quando
    # `--dataset` non include la ripetizione.
    candidati = [f"output_{args.dataset}.csv_{args.threshold}H0.csv",
                 f"output_{args.dataset}_{args.run}.csv_{args.threshold}H0.csv"]
    tag_base, base = candidati[0], {}
    for cand in candidati:
        p = os.path.join(args.pop_dir, f"A__{cand}")
        if os.path.exists(p):
            tag_base, base = cand, read_pop(p)
            break
    if not base:
        sys.exit(f"[errore] Populated del baseline assente in {args.pop_dir}:\n"
                 f"         cercato A__{candidati[0]} e A__{candidati[1]}\n"
                 f"         il file va prodotto con `benchmark.py --keep-populated-dir ...`")

    header, rows = P.read_dataset(args.dataset_file, sep=";")
    orig = rfd_lines(args.rfd)
    print("=" * 108)
    print(f"CONTABILITÀ DEI VETI — {args.dataset} run {args.run}, soglia {args.threshold}")
    print("=" * 108)
    print(f"celle valutate (TupleIniziali): {len(base)}   "
          f"imputate nel baseline: {sum(1 for v in base.values() if v not in ('?',''))}")

    variants = sorted({os.path.basename(p).split("__", 1)[0]
                       for p in glob.glob(os.path.join(args.pop_dir, "*__" + tag_base))})
    variants = [v for v in variants if v != "A"]
    print(f"varianti ritenute: {variants}\n")

    for v in variants:
        var = read_pop(os.path.join(args.pop_dir, f"{v}__{tag_base}"))
        if not var:
            print(f"--- {v}: Populated assente, salto")
            continue
        lost = lost_cells(base, var)
        gained = gained_cells(base, var)

        # file RFD potato di questa variante
        # stesso motivo del nome del Populated: `--dataset` contiene gia' la ripetizione,
        # quindi il file scritto da benchmark.py e' `{variante}_{dataset}_{soglia}.csv`.
        candidati_pr = [os.path.join(PRUNED_DIR, f"{v}_{args.dataset}_{args.threshold}.csv"),
                        os.path.join(PRUNED_DIR, f"{v}_{args.dataset}_{args.run}_{args.threshold}.csv")]
        pruned = next((p for p in candidati_pr if os.path.exists(p)), None)
        if pruned is None:
            print(f"--- {v}: file RFD potato assente (cercato {candidati_pr[0]}), salto l'attribuzione")
            continue
        pr = rfd_lines(pruned)
        orig_set = collections.Counter(l for l, _ in orig)
        pruned_set = collections.Counter(l for l, _ in pr)
        removed_lines = orig_set - pruned_set
        removed = [p for l, p in orig if removed_lines[l] > 0]

        # classificazione gratuito / pagato sull'insieme finale
        alive = [not (removed_lines[l] > 0) for l, _ in orig]
        covered = P.veto_covered_indices([p for _, p in orig], max_extra=args.max_extra, alive=alive)
        free = [p for i, (_, p) in enumerate(orig) if i in covered and alive[i] is False]

        print(f"--- {v} ---")
        print(f"  RFD: {len(orig)} -> {len(pr)}  (rimosse {len(removed)}, "
              f"di cui gratuite [V2] {len(free)}, pagate {len(removed)-len(free)})")
        print(f"  celle: perse {len(lost)}, guadagnate {len(gained)}  "
              f"(su {len(base)} valutate)")

        # attribuzione delle celle perse
        expo = P.exposure([p for _, p in orig], P.collect_null_columns([args.dataset_file])[1])
        per_rfd = collections.Counter()
        per_rfd_kind = {}
        unattributed = 0
        for (ri, col) in lost:
            try:
                i = int(ri)
            except ValueError:
                unattributed += 1
                continue
            if i >= len(rows):
                unattributed += 1
                continue
            hits = [p for p in removed if rfd_can_serve(p, i, col, rows, header)]
            if not hits:
                unattributed += 1
            for p in hits:
                k = P.signature(p)
                per_rfd[k] += 1
                per_rfd_kind[k] = "gratuita" if any(p is q for q in free) else "pagata"
        print(f"  celle perse attribuibili a RFD rimosse: {len(lost)-unattributed}/{len(lost)} "
              f"(non attribuibili: {unattributed})")
        kinds = collections.Counter(per_rfd_kind.values())
        print(f"  RFD che spiegano almeno una cella persa: {len(per_rfd)}  {dict(kinds)}")

        # ---- misura centrale: exposure ordina bene le RFD per valore di veto reale? ----
        # Per OGNI RFD rimossa si conta quante celle VALUTATE (TupleIniziali) poteva servire,
        # usando i valori reali del dataset. E' il "valore di veto empirico" e si confronta con
        # `exposure`, che invece usa il profilo globale dei nulli.
        evaluated = []
        for (ri, col) in base:
            try:
                i = int(ri)
            except ValueError:
                continue
            if i < len(rows):
                evaluated.append((i, col))
        idx_of_all = {P.signature(p): n for n, (_, p) in enumerate(orig)}
        xs_all, ys_all, kinds_all = [], [], []
        served_paid = served_free = 0
        n_paid = n_free = 0
        for p in removed:
            k = P.signature(p)
            if k not in idx_of_all:
                continue
            n_serv = sum(1 for (i, col) in evaluated if rfd_can_serve(p, i, col, rows, header))
            is_free = any(p is q for q in free)
            xs_all.append(expo[idx_of_all[k]])
            ys_all.append(n_serv)
            kinds_all.append(is_free)
            if is_free:
                n_free += 1; served_free += n_serv
            else:
                n_paid += 1; served_paid += n_serv
        if xs_all:
            rho_all, n_all = spearman(xs_all, ys_all)
            print(f"  valore di veto empirico su {n_all} RFD rimosse "
                  f"(celle valutate servibili per RFD):")
            print(f"    media {statistics.mean(ys_all):.3f}  mediana {statistics.median(ys_all):.1f}  "
                  f"max {max(ys_all)}  RFD che non servono nessuna cella: "
                  f"{sum(1 for v in ys_all if v == 0)}")
            print(f"    Spearman(exposure, celle servibili) = "
                  f"{'n/d' if rho_all is None else round(rho_all, 3)}   n={n_all}")
        if n_free or n_paid:
            print(f"    RFD gratuite: {n_free}, celle servibili totali {served_free}"
                  f"  ({served_free/max(1,n_free):.3f} per RFD)")
            print(f"    RFD pagate  : {n_paid}, celle servibili totali {served_paid}"
                  f"  ({served_paid/max(1,n_paid):.3f} per RFD)")
        print()

        # attribuzione delle celle EFFETTIVAMENTE perse (analisi secondaria)
        if per_rfd:
            idx_of = {P.signature(p): n for n, (_, p) in enumerate(orig)}
            xs = [expo[idx_of[k]] for k in per_rfd if k in idx_of]
            ys = [per_rfd[k] for k in per_rfd if k in idx_of]
            rho, n = spearman(xs, ys)
            print(f"  Spearman(exposure, celle perse spiegate): rho={rho if rho is None else round(rho,3)}"
                  f"  n={n}")
            # valore medio per classe
            for kind in ("gratuita", "pagata"):
                vals = [per_rfd[k] for k in per_rfd if per_rfd_kind[k] == kind]
                if vals:
                    print(f"    RFD {kind:<9} che spiegano celle perse: {len(vals)}, "
                          f"celle/RFD medio {statistics.mean(vals):.2f}")
        print()


if __name__ == "__main__":
    sys.exit(main())
