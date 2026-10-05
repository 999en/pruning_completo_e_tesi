#!/usr/bin/env python3
"""Break down imputation quality by RFD properties, from the archived Results+Populated."""
import os, re, json, collections, statistics

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/results/analisi"
recs = json.load(open(os.path.join(OUT, "results_parsed.json")))
print(f"record totali: {len(recs)}")
cov = [r for r in recs if r.get("known") and r.get("imputed") not in (None, "?", "")]
print(f"con ground truth e valore imputato: {len(cov)}")
for r in cov:
    r["lhs"] = [tuple(x) for x in r["lhs"]]
    r["nlhs"] = len(r["lhs"])
    r["correct"] = bool(r["correct"])

def table(rows, keyfn, title, order=None):
    g = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        k = keyfn(r)
        g[k][1] += 1
        g[k][0] += 1 if r["correct"] else 0
    print(f"\n--- {title} ---")
    keys = order if order else sorted(g, key=lambda k: (str(type(k)), k))
    for k in keys:
        if k not in g: continue
        c, n = g[k]
        bar = "#" * int(40 * c / max(1, n))
        print(f"  {str(k):<26} n={n:>6}  corr={c:>6}  acc={100*c/n:>5.1f}%  {bar}")

print("\n" + "="*100)
print("QUALITA' PER PROPRIETA' DELLA RFD")
print("="*100)

for fam in sorted(set(r["family"] for r in cov)):
    fr = [r for r in cov if r["family"] == fam]
    c = sum(1 for r in fr if r["correct"])
    print(f"\n\n########## FAMIGLIA {fam}  (imputazioni={len(fr)}, accuratezza={100*c/max(1,len(fr)):.1f}%) ##########")
    table(fr, lambda r: "RHS_thr = 0" if r["rhs_thr"] == 0 else ("0 < RHS_thr <= 5" if r["rhs_thr"] <= 5 else
          ("5 < RHS_thr <= 10" if r["rhs_thr"] <= 10 else "RHS_thr > 10")),
          "accuratezza per soglia RHS",
          ["RHS_thr = 0","0 < RHS_thr <= 5","5 < RHS_thr <= 10","RHS_thr > 10"])
    table(fr, lambda r: f"|LHS| = {r['nlhs']}" if r["nlhs"] <= 6 else "|LHS| >= 7",
          "accuratezza per dimensione del LHS",
          [f"|LHS| = {i}" for i in range(1, 7)] + ["|LHS| >= 7"])
    table(fr, lambda r: "percorso EXACT" if r["exact"] else "percorso SIMILARITY",
          "accuratezza per percorso di imputazione", ["percorso EXACT","percorso SIMILARITY"])
    table(fr, lambda r: r["rhs"], "accuratezza per attributo RHS")
    # wsim buckets
    sim = [r for r in fr if r.get("wsim") is not None]
    def wb(r):
        w = r["wsim"]
        if w == 0: return "wsim = 0"
        if w <= 0.5: return "0 < wsim <= 0.5"
        if w <= 1: return "0.5 < wsim <= 1"
        if w <= 2: return "1 < wsim <= 2"
        if w <= 5: return "2 < wsim <= 5"
        return "wsim > 5"
    table(sim, wb, "accuratezza per weightedSimilarity (solo percorso similarity)",
          ["wsim = 0","0 < wsim <= 0.5","0.5 < wsim <= 1","1 < wsim <= 2","2 < wsim <= 5","wsim > 5"])

# ---------------------------------------------------------------- pruning curve from the archive
print("\n\n" + "="*100)
print("SIMULAZIONE 'ARCHIVE-BASED' DEL PRUNING DATA-DRIVEN (P6)")
print("="*100)
print("Ipotesi semplificata: se una RFD viene rimossa, le sue imputazioni spariscono (nessun ri-routing).")
print("E' un limite INFERIORE del beneficio: il valore reale va misurato ri-eseguendo (vedi esperimento).")
for fam in sorted(set(r["family"] for r in cov)):
    fr = [r for r in cov if r["family"] == fam]
    st = collections.defaultdict(lambda: [0, 0])
    for r in fr:
        k = (r["rhs"], r["rhs_thr"], tuple(tuple(x) for x in r["lhs"]))
        st[k][1] += 1; st[k][0] += 1 if r["correct"] else 0
    print(f"\n--- {fam}: {len(st)} RFD distinte, {len(fr)} imputazioni ---")
    print(f"{'soglia':<34}{'RFD tenute':>11}{'imput.':>9}{'corrette':>10}{'err':>7}{'prec%':>8}{'cover%':>8}")
    base_n = len(fr)
    for minacc, minuse in [(0.0,1),(0.5,3),(0.7,3),(0.8,3),(0.9,3),(1.0,3),(0.8,1),(1.0,1)]:
        kept = {k: v for k, v in st.items() if v[1] >= minuse and v[0]/v[1] >= minacc}
        n = sum(v[1] for v in kept.values()); c = sum(v[0] for v in kept.values())
        # imputazioni "perse" = quelle prodotte da RFD scartate
        print(f"acc>={minacc:.0%} & usi>={minuse:<3}       {len(kept):>11}{n:>9}{c:>10}{n-c:>7}"
              f"{100*c/max(1,n):>8.1f}{100*n/max(1,base_n):>8.1f}")
