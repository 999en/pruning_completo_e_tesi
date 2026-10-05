#!/usr/bin/env python3
"""Exact, cheap structural facts about every RFD set — the numbers quoted in the report."""
import os, re, sys, json, collections, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prune import (SRC, OUT, read_rfd, parse_row, read_dataset, is_null,
                   mask_coverage, mask_dom_exact, mask_lhs_cap)

def ls(d): return sorted(f for f in os.listdir(os.path.join(SRC, d))
                         if not f.startswith("._") and f != ".DS_Store")

DS_FOR = {   # rfdfile -> dataset file used to evaluate applicability
    "bridges": "bridges_14_1.csv", "glass": "glass_22_1.csv", "restaurant": "restaurant_52_1.csv",
    "nursery": None, "Physician_Compare_National": "Physician_Compare_National_13467_1.csv",
}
def ds_of(f):
    for k, v in DS_FOR.items():
        if k in f: return v
    return None

rows = []
for f in [x for x in ls("RFD") if x.endswith(".csv")]:
    header, hline, raw = read_rfd(os.path.join(SRC, "RFD", f))
    parsed, keep = [], []
    for l in raw:
        p = parse_row(header, l)
        if p is not None: parsed.append(p); keep.append(l)
    n = len(parsed)
    if n == 0: continue
    rhs0   = sum(1 for p in parsed if p["rhs_thr"] == 0.0)
    lhsmed = statistics.median(len(p["lhs"]) for p in parsed)
    lhsmax = max(len(p["lhs"]) for p in parsed)
    sigdup = collections.Counter((p["rhs"], frozenset(p["lhs"])) for p in parsed)
    dup    = sum(v - 1 for v in sigdup.values() if v > 1)
    dom    = sum(1 for k in mask_dom_exact(parsed) if not k)
    cov = covn = None
    ds = ds_of(f)
    dsp = os.path.join(SRC, "Dataset", ds) if ds else None
    if dsp and os.path.exists(dsp):
        attrs, dsrows = read_dataset(dsp)
        nullcells = [(ri, a) for ri, r in enumerate(dsrows) for a in attrs if is_null(r[a])]
        m = mask_coverage(parsed, nullcells, attrs, dsrows)
        cov = sum(1 for x in m if x); covn = len(nullcells)
    rows.append(dict(file=f, n=n, rhs_thr0=rhs0, pct_rhs0=100*rhs0/n, lhs_med=lhsmed, lhs_max=lhsmax,
                     lhs_dupes=dup, dom_same=dom, pct_dom_same=100*dom/n,
                     applicable=cov, null_cells=covn,
                     pct_applicable=(100*cov/n if cov is not None else None)))

out = os.path.join(OUT, "rfd_facts.json")
json.dump(rows, open(out, "w"), indent=1)

W = 116
print("="*W)
print("FATTI STRUTTURALI ESATTI SU OGNI SET DI RFD")
print("="*W)
print(f"{'file':<50}{'RFD':>7}{'thrR=0%':>9}{'|LHS|med':>9}{'max':>4}"
      f"{'dupLHS':>7}{'dom(esatta)':>12}{'non appl.%':>11}{'celle nulle':>12}")
for r in sorted(rows, key=lambda r: (r["file"])):
    na = f"{100-r['pct_applicable']:.1f}" if r["pct_applicable"] is not None else "-"
    nc = r["null_cells"] if r["null_cells"] is not None else "-"
    print(f"{r['file']:<50}{r['n']:>7}{r['pct_rhs0']:>9.1f}{r['lhs_med']:>9.1f}{r['lhs_max']:>4}"
          f"{r['lhs_dupes']:>7}{r['pct_dom_same']:>12.1f}{na:>11}{str(nc):>12}")
print(f"\n[scritto {out}]")
