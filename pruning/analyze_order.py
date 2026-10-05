#!/usr/bin/env python3
"""
analyze_order.py — l'ordinamento per precisione batte una permutazione casuale?

Legge il JSON dell'esperimento d'ordine (`pruning/exp_order.py`), depositato in
`results/analisi/results_order_control.json`: sono i 12 record del controllo che la Fase 4
non aveva separato in tre domande distinte:

  D1. `first-best` batte il file **originale**?          (replica il guadagno di precision-priority)
  D2. una permutazione **casuale** batte l'originale?    (il guadagno e' solo "rimescolare"?)
  D3. `first-best` batte la permutazione **casuale**?    (il segnale di precisione serve davvero?)

Se D2 e' vera e D3 e' falsa, il guadagno della Fase 4 non e' attribuibile alla precisione:
qualunque rimescolamento dei cluster dentro le colonne lo produce.

Tutti i confronti sono appaiati per (dataset, run, soglia). Il test di Wilcoxon e' quello di
`benchmark.py` (scipy non e' installato).

Uso:
    python3 pruning/analyze_order.py
    python3 pruning/analyze_order.py --json results/analisi/results_order_control.json --correct
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from benchmark import wilcoxon_signed_rank, fmt_p       # noqa: E402
from paths import RESULTS                               # noqa: E402

DEFAULT = os.path.join(RESULTS, "analisi", "results_order_control.json")


def load(path):
    if not os.path.exists(path):
        sys.exit(f"[errore] file assente: {path}")
    return json.load(open(path, encoding="utf-8"))


def pivot(records, metric="correct"):
    """{(ds, run, thr): {modo: valore}}"""
    out = collections.defaultdict(dict)
    for r in records:
        mode = r["variant"].split(":", 1)[1] if r["variant"].startswith("ord:") else r["variant"]
        out[(r["dataset"], r["run"], r["threshold"])][mode] = r[metric]
    return out


def randoms(modes):
    return sorted(m for m in modes if m.startswith("random"))


def paired(by, mode_a, mode_b, agg=None):
    """Differenze appaiate a - b sulle configurazioni in cui entrambi esistono."""
    d = []
    for k, mm in sorted(by.items()):
        if mode_a not in mm or mode_b not in mm:
            continue
        d.append(mm[mode_a] - mm[mode_b])
    return d


def report(title, d, higher_is_better=True):
    if not d:
        print(f"  {title}: [nessun dato]")
        return None
    nz = [x for x in d if abs(x) > 1e-12]
    w = wilcoxon_signed_rank(d, [0] * len(d)) if nz else {"n": 0, "p": 1.0, "W+": 0, "W-": 0,
                                                          "method": "nessuna differenza"}
    tot = sum(d)
    wins = sum(1 for x in d if (x > 0) == higher_is_better and abs(x) > 1e-12)
    loss = sum(1 for x in d if (x < 0) == higher_is_better and abs(x) > 1e-12)
    tie = len(d) - wins - loss
    print(f"  {title}")
    print(f"      n={len(d)}  Δtot={tot:+g}  mediana={statistics.median(d):+g}  "
          f"migliori={wins} peggiori={loss} pari={tie}")
    print(f"      Wilcoxon: n={w['n']} W+={w['W+']:.1f} W-={w['W-']:.1f} "
          f"p={fmt_p(w['p'])} ({w.get('method','')})")
    return dict(n=len(d), d_tot=tot, wins=wins, loss=loss, tie=tie, p=w["p"], wilcoxon_n=w["n"])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", default=DEFAULT)
    ap.add_argument("--metric", default="correct", choices=["correct", "wrong", "accuracy"])
    ap.add_argument("--correct", action="store_true",
                    help="per la metrica 'wrong' il segno va letto al contrario")
    args = ap.parse_args()

    recs = load(args.json)
    by = pivot(recs, args.metric)
    modes = sorted({m for mm in by.values() for m in mm})
    rs = randoms(modes)
    print("=" * 100)
    print(f"ANALISI DELL'ESPERIMENTO D'ORDINE — metrica: {args.metric}")
    print("=" * 100)
    print(f"file     : {args.json}")
    print(f"config   : {len(by)}   ({sorted({k[0] for k in by})} × run {sorted({k[1] for k in by})} "
          f"× soglie {sorted({k[2] for k in by})})")
    print(f"modalita': {modes}")
    print()

    # ---- totali per modalita' ----
    print("--- totali per modalita' ---")
    print(f"{'modalita':<18}{'n':>4}{'corrette':>10}{'errori':>8}{'acc. media':>12}")
    for m in modes:
        sel = [r for r in recs
               if (r["variant"].split(":", 1)[1] if r["variant"].startswith("ord:") else r["variant"]) == m]
        if not sel:
            continue
        print(f"{m:<18}{len(sel):>4}{sum(r['correct'] for r in sel):>10}"
              f"{sum(r['wrong'] for r in sel):>8}"
              f"{statistics.mean(r['accuracy'] for r in sel):>12.4f}")
    print()

    # ---- le tre domande ----
    print("--- D1: first-best batte l'originale? ---")
    d1 = paired(by, "first-best", "orig")
    r1 = report("first-best − orig", d1)
    print()
    print("--- D2: una permutazione casuale batte l'originale? ---")
    for s in rs:
        report(f"{s} − orig", paired(by, s, "orig"))
    # media dei semi per configurazione
    if rs:
        d2 = []
        for k, mm in sorted(by.items()):
            if "orig" in mm and all(s in mm for s in rs):
                d2.append(sum(mm[s] for s in rs) / len(rs) - mm["orig"])
        r2 = report(f"media({len(rs)} semi) − orig", d2)
    print()
    print("--- D3: first-best batte la permutazione casuale? ---")
    for s in rs:
        report(f"first-best − {s}", paired(by, "first-best", s))
    if rs:
        d3 = []
        for k, mm in sorted(by.items()):
            if "first-best" in mm and all(s in mm for s in rs):
                d3.append(mm["first-best"] - sum(mm[s] for s in rs) / len(rs))
        r3 = report(f"first-best − media({len(rs)} semi)", d3)
    print()
    print("--- controllo: last-best batte l'originale? ---")
    if "last-best" in modes:
        report("last-best − orig", paired(by, "last-best", "orig"))

    # ---- verdetto ----
    print()
    print("=" * 100)
    if r1 and r2 and r3:
        print("VERDETTO")
        print(f"  D1 first-best > orig          : Δ={r1['d_tot']:+g}  p={fmt_p(r1['p'])}  "
              f"→ {'SI' if r1['d_tot'] > 0 and r1['p'] < 0.05 else 'non dimostrato'}")
        print(f"  D2 casuale    > orig          : Δ={r2['d_tot']:+g}  p={fmt_p(r2['p'])}  "
              f"→ {'SI' if r2['d_tot'] > 0 and r2['p'] < 0.05 else 'non dimostrato'}")
        print(f"  D3 first-best > casuale       : Δ={r3['d_tot']:+g}  p={fmt_p(r3['p'])}  "
              f"→ {'SI' if r3['d_tot'] > 0 and r3['p'] < 0.05 else 'NO'}")
        if r2["d_tot"] > 0 and not (r3["d_tot"] > 0 and r3["p"] < 0.05):
            print()
            print("  ATTENZIONE: il guadagno non e' attribuibile al segnale di precisione.")
            print("  Qualunque rimescolamento dei cluster dentro le colonne produce lo stesso")
            print("  effetto: l'ordine del file originale e' patologico, non l'ordine di")
            print("  precisione e' buono. La conclusione della Fase 4 va riformulata.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
