#!/usr/bin/env python3
"""Caratterizza le RFD rimosse da ciascuna strategia rispetto alla loro accuratezza baseline.

Usa results_parsed.json (archivio) per attribuire a ogni RFD usata: numero di usi, corrette, errate.
Serve a spiegare PERCHE' una direzione di dominanza funziona e l'altra no.
"""
import os, sys, json, re, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prune import read_rfd, parse_row, read_dataset, is_null, mask_coverage, mask_dom_super, mask_dom_sub

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/results/analisi"
REN = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/RENUVER"

recs = json.load(open(os.path.join(OUT, "results_parsed.json")))

# ---- accuratezza baseline per RFD (chiave: rhs|rhs_thr|lhs ordinato) ----
def key_of(rhs, rhs_thr, lhs_items):
    return (rhs, round(float(rhs_thr), 6), tuple(sorted((c, round(float(t), 6)) for c, t in lhs_items)))

per_rfd = collections.defaultdict(lambda: [0, 0])      # key -> [correct, total]
for r in recs:
    if not r.get("known"): continue
    if r.get("imputed") in (None, "?", ""): continue
    if not str(r["base"]).startswith("bridges"): continue
    k = key_of(r["rhs"], r["rhs_thr"], [tuple(x) for x in r["lhs"]])
    per_rfd[k][1] += 1
    per_rfd[k][0] += 1 if r["correct"] else 0

print(f"RFD bridges con statistiche baseline: {len(per_rfd)}")

def stats_for(parsed, mask, name):
    """Aggrega accuratezza baseline delle RFD tenute vs rimosse."""
    kept = [p for p, k in zip(parsed, mask) if k]
    rem = [p for p, k in zip(parsed, mask) if not k]
    def agg(group):
        sc = st = used = 0
        for p in group:
            k = key_of(p["rhs"], p["rhs_thr"], p["lhs"].items())
            c, t = per_rfd.get(k, (0, 0))
            if t: used += 1; sc += c; st += t
        return used, sc, st
    ku, kc, kt = agg(kept)
    ru, rc, rt = agg(rem)
    print(f"\n  {name}")
    print(f"    tenute  : {len(kept):>6} RFD | usate in baseline: {ku:>4} | imputazioni {kt:>5} | corrette {kc:>5} "
          f"| acc {100*kc/max(1,kt):>5.1f}%")
    print(f"    rimosse : {len(rem):>6} RFD | usate in baseline: {ru:>4} | imputazioni {rt:>5} | corrette {rc:>5} "
          f"| acc {100*rc/max(1,rt):>5.1f}%")
    # |LHS| medio e soglia RHS media
    ml = lambda g: sum(len(p["lhs"]) for p in g) / max(1, len(g))
    mr = lambda g: sum(p["rhs_thr"] for p in g) / max(1, len(g))
    print(f"    |LHS| medio: tenute {ml(kept):.2f} vs rimosse {ml(rem):.2f}   "
          f"soglia RHS media: tenute {mr(kept):.2f} vs rimosse {mr(rem):.2f}")

for thr in (3, 15):
    rfdf = f"output_false_{thr}_bridges.csv"
    header, hline, raw = read_rfd(os.path.join(REN, "RFD", rfdf))
    parsed = [p for p in (parse_row(header, l) for l in raw) if p]
    # union of null columns across the 25 bridges datasets
    nullcols = set()
    for miss in (14, 28, 42, 56, 70):
        for run in range(1, 6):
            dh, rows = read_dataset(os.path.join(REN, "Dataset", f"bridges_{miss}_{run}.csv"))
            for r in rows:
                for a in dh:
                    if is_null(r[a]): nullcols.add(a)
    print("\n" + "=" * 100)
    print(f"BRIDGES · soglia {thr} · {len(parsed)} RFD · colonne mai nulle: {sorted(set(header[1:]) - nullcols)}")
    print("=" * 100)
    stats_for(parsed, mask_dom_sub(parsed, 1), "P3 LHS-sottoinsieme (max_extra=1)  [quello che ha funzionato]")
    stats_for(parsed, mask_dom_super(parsed, 1), "P3 LHS-sovrainsieme (max_extra=1)  [direzione veto-safe]")
