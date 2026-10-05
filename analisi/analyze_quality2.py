#!/usr/bin/env python3
"""Aggregate quality breakdown by DATASET (not per-run)."""
import os, re, json, collections
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/results/analisi"
recs = json.load(open(os.path.join(OUT, "results_parsed.json")))

def fam(base):
    b = re.sub(r"\.\.?csv$", "", base)
    b = re.sub(r"_remodulated_[\d.]+", "", b)
    b = re.sub(r"_[\d.]+$", "", b)
    return b

cov = []
for r in recs:
    if not r.get("known"): continue
    if r.get("imputed") in (None, "?", ""): continue
    r["fam"] = fam(r["base"])
    r["lhs"] = [tuple(x) for x in r["lhs"]]
    r["nlhs"] = len(r["lhs"])
    cov.append(r)

def table(rows, keyfn, order=None):
    g = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        k = keyfn(r); g[k][1] += 1; g[k][0] += 1 if r["correct"] else 0
    keys = order if order else sorted(g, key=lambda k: str(k))
    for k in keys:
        if k not in g: continue
        c, n = g[k]
        print(f"    {str(k):<28} n={n:>6}  corr={c:>6}  acc={100*c/n:>5.1f}%  {'#'*int(35*c/n)}")

print("="*104)
print("QUALITA' AGGREGATA PER DATASET")
print("="*104)
for f in sorted(set(r["fam"] for r in cov)):
    fr = [r for r in cov if r["fam"] == f]
    c = sum(1 for r in fr if r["correct"])
    print(f"\n########## {f}   imputazioni={len(fr)}  accuratezza={100*c/len(fr):.1f}% ##########")
    table(fr, lambda r: ("RHS_thr = 0" if r["rhs_thr"] == 0 else
                         "0 < RHS_thr <= 3" if r["rhs_thr"] <= 3 else
                         "3 < RHS_thr <= 6" if r["rhs_thr"] <= 6 else
                         "6 < RHS_thr <= 10" if r["rhs_thr"] <= 10 else "RHS_thr > 10"),
          ["RHS_thr = 0","0 < RHS_thr <= 3","3 < RHS_thr <= 6","6 < RHS_thr <= 10","RHS_thr > 10"])
    table(fr, lambda r: (f"|LHS| = {r['nlhs']}" if r["nlhs"] <= 5 else "|LHS| >= 6"),
          [f"|LHS| = {i}" for i in range(1, 6)] + ["|LHS| >= 6"])
    table(fr, lambda r: ("EXACT" if r["exact"] else "SIMILARITY"), ["EXACT","SIMILARITY"])
    def wb(r):
        w = r.get("wsim")
        if w is None: return "n/d"
        if w == 0: return "wsim = 0"
        if w <= 0.5: return "0 < wsim <= 0.5"
        if w <= 1: return "0.5 < wsim <= 1"
        if w <= 2: return "1 < wsim <= 2"
        if w <= 5: return "2 < wsim <= 5"
        return "wsim > 5"
    table([r for r in fr if not r["exact"]], wb,
          ["wsim = 0","0 < wsim <= 0.5","0.5 < wsim <= 1","1 < wsim <= 2","2 < wsim <= 5","wsim > 5"])

# ---------- how concentrated is the win? ----------
print("\n\n" + "="*104)
print("CONCENTRAZIONE: quante RFD servono per ottenere X% delle imputazioni CORRETTE?")
print("="*104)
for f in sorted(set(r["fam"] for r in cov)):
    fr = [r for r in cov if r["fam"] == f]
    st = collections.defaultdict(lambda: [0, 0])
    for r in fr:
        k = (r["rhs"], r["rhs_thr"], tuple(tuple(x) for x in r["lhs"]))
        st[k][1] += 1; st[k][0] += 1 if r["correct"] else 0
    total_c = sum(v[0] for v in st.values())
    # rank by number of CORRECT imputations, descending
    ranked = sorted(st.items(), key=lambda kv: -kv[1][0])
    print(f"\n--- {f}: {len(st)} RFD usate, {total_c} imputazioni corrette ---")
    cum = 0
    marks = [0.5, 0.8, 0.9, 0.95, 1.0]
    mi = 0
    for i, (k, v) in enumerate(ranked, 1):
        cum += v[0]
        while mi < len(marks) and cum >= marks[mi] * total_c:
            print(f"    {marks[mi]:>5.0%} delle corrette raggiunto con {i:>4} RFD "
                  f"({100*i/len(st):>5.1f}% del set usato)")
            mi += 1
    # and how many RFD contribute ZERO correct
    zero = [(k, v) for k, v in st.items() if v[0] == 0]
    print(f"    RFD con 0 imputazioni corrette: {len(zero)} ({100*len(zero)/len(st):.1f}%), "
          f"responsabili di {sum(v[1] for _, v in zero)} imputazioni sbagliate")
