#!/usr/bin/env python3
"""
strategie v2 — da integrare in pruning.py al termine del benchmark in corso.

Contiene:
  * mask_veto_cover      : versione CORRETTA della copertura del veto (direzione giusta +
                           punto fisso, per non rimuovere due RFD che si coprono a vicenda)
  * mask_dom_sub_strict  : dom-sub che richiede soglie STRETTAMENTE piu' piccole su tutte le
                           colonne condivise (piu' conservativa, meno rimozioni)
  * mask_used_acc        : tiene le RFD usate nel training E con accuratezza sufficiente
"""
import os
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prune import read_rfd, parse_row


# ---------------------------------------------------------------------------------------
def mask_veto_cover(parsed, max_extra=3):
    """[V2] r rimossa se esiste r'' con:
             stesso RHS;
             LHS(r'') SUBSET di LHS(r)  (al piu' max_extra colonne in meno, non vuoto);
             soglia_{r''}(c) >= soglia_r(c) per ogni c in LHS(r'');
             soglia_RHS(r'') <= soglia_RHS(r).
       In tal caso ogni veto di r e' implicato da un veto di r''.
       Punto fisso: si rimuove r solo se almeno un copritore sopravvive."""
    buckets = collections.defaultdict(list)
    for i, p in enumerate(parsed):
        buckets[(p["rhs"], frozenset(p["lhs"]))].append(i)
    by_rhs = collections.defaultdict(set)
    for rhs, s in buckets:
        by_rhs[rhs].add(s)

    cover = {}
    for i, r in enumerate(parsed):
        S = frozenset(r["lhs"])
        cov = []
        for T in by_rhs[r["rhs"]]:
            if T == S or not (T <= S) or len(S) - len(T) > max_extra or len(T) == 0:
                continue
            for j in buckets[(r["rhs"], T)]:
                q = parsed[j]
                if any(q["lhs"][c] < r["lhs"][c] for c in T):
                    continue
                if q["rhs_thr"] > r["rhs_thr"]:
                    continue
                cov.append(j)
        if cov:
            cover[i] = cov

    R = set(cover)
    changed = True
    while changed:
        changed = False
        for r in list(R):
            if all(c in R for c in cover[r]):
                R.discard(r)
                changed = True
    return [i not in R for i in range(len(parsed))], len(R)


# ---------------------------------------------------------------------------------------
def mask_dom_sub_strict(parsed):
    """dom-sub potenziata: il dominatore deve avere LHS sottoinsieme stretto E soglie
    STRETTAMENTE piu' piccole su tutte le colonne condivise E soglia RHS <=.
    Nessun limite alla differenza di dimensione del LHS."""
    buckets = collections.defaultdict(list)
    for i, p in enumerate(parsed):
        buckets[(p["rhs"], frozenset(p["lhs"]))].append(i)
    by_rhs = collections.defaultdict(set)
    for rhs, s in buckets:
        by_rhs[rhs].add(s)
    keep = [True] * len(parsed)
    for i, r in enumerate(parsed):
        S = frozenset(r["lhs"])
        for T in by_rhs[r["rhs"]]:
            if T == S or not (T <= S) or len(T) == 0:
                continue
            for j in buckets[(r["rhs"], T)]:
                q = parsed[j]
                if any(q["lhs"][c] >= r["lhs"][c] for c in T):   # STRETTAMENTE minore
                    continue
                if q["rhs_thr"] > r["rhs_thr"]:
                    continue
                keep[i] = False
                break
            if not keep[i]:
                break
    return keep, sum(1 for k in keep if not k)


# ---------------------------------------------------------------------------------------
def mask_used_acc(parsed, train_stats, min_acc=0.5):
    """Tiene la RFD se e' stata usata nel training e la sua accuratezza e' >= min_acc
    (le RFD con pochissimi usi sono tenute per prudenza: soglia minima 2 usi)."""
    if not train_stats:
        return [True] * len(parsed), 0
    keep = []
    for p in parsed:
        k = (p["rhs"], round(float(p["rhs_thr"]), 9),
             tuple(sorted((c, round(float(t), 9)) for c, t in p["lhs"].items())))
        st = train_stats.get(k)
        if not st or st["uses"] == 0:
            keep.append(False)
            continue
        if st["uses"] < 2:
            keep.append(True)
            continue
        keep.append(st["correct"] / st["uses"] >= min_acc)
    return keep, sum(1 for k in keep if not k)


# ---------------------------------------------------------------------------------------
if __name__ == "__main__":
    REN = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/RENUVER"

    def load(thr):
        h, hl, L = read_rfd(os.path.join(REN, "RFD", f"output_false_{thr}_bridges.csv"))
        return [p for p in (parse_row(h, l) for l in L) if p]

    print("=" * 104)
    print("RIDUZIONE DELLE STRATEGIE v2 (Bridges)")
    print("=" * 104)
    print(f"{'soglia':>7}{'RFD':>9}{'veto-cover':>22}{'dom-sub-strict':>22}")
    for thr in (3, 6, 9, 12, 15):
        p = load(thr)
        _, n_vc = mask_veto_cover(p, 3)
        _, n_ds = mask_dom_sub_strict(p)
        print(f"{thr:>7}{len(p):>9}"
              f"{f'{n_vc} ({100*n_vc/len(p):.1f}%)':>22}"
              f"{f'{n_ds} ({100*n_ds/len(p):.1f}%)':>22}")
