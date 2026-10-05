#!/usr/bin/env python3
"""
Riderivazione della condizione di COPERTURA DEL VETO.

`isFaultless` rifiuta un'imputazione se esiste una tupla s che CONCORDA con la tupla completata
su TUTTO LHS(r) (entro le soglie di r) e VIOLA il RHS (|delta| > soglia_RHS(r)).

Vogliamo rimuovere r lasciando r'' tale che:  (r farebbe veto) => (r'' fa veto).
  * r'' deve trovare lo stesso s  -> LHS(r'') SUBSET di LHS(r)   [meno richieste, piu' facile]
  * e deve concordare            -> soglia_{r''}(c) >= soglia_r(c) sulle colonne di LHS(r'')
  * e deve violare               -> soglia_RHS(r'') <= soglia_RHS(r)   [piu' facile violare]

Direzione: LHS SOTTOINSIEME, soglie LHS PIU' LARGHE, soglia RHS PIU' STRETTA.
(La prima implementazione usava LHS sovrainsieme + soglie piu' strette: implicazione invertita.)
"""
import os, sys, collections, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prune import read_rfd, parse_row

REN = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/RENUVER"


def load(thr):
    h, hl, L = read_rfd(os.path.join(REN, "RFD", f"output_false_{thr}_bridges.csv"))
    return h, [p for p in (parse_row(h, l) for l in L) if p]


def cover_map(parsed, max_extra=2):
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
                if any(q["lhs"][c] < r["lhs"][c] for c in T):      # servono soglie PIU' LARGHE
                    continue
                if q["rhs_thr"] > r["rhs_thr"]:                     # serve RHS PIU' STRETTO
                    continue
                cov.append(j)
        if cov:
            cover[i] = cov
    return cover


def removable_set(cover):
    """Punto fisso massimo: si rimuove r solo se almeno un copritore SOPRAVVIVE."""
    R = set(cover)
    changed = True
    while changed:
        changed = False
        for r in list(R):
            if all(c in R for c in cover[r]):
                R.discard(r)
                changed = True
    return R


if __name__ == "__main__":
    print("=" * 96)
    print("COPERTURA DEL VETO — quantita' rimovibile preservando il potere di veto")
    print("=" * 96)
    print(f"{'soglia':>7}{'max_extra':>10}{'RFD':>9}{'rimosse':>9}{'rid%':>8}{'restano':>9}")
    for thr in (3, 6, 9, 12, 15):
        h, parsed = load(thr)
        for me in (1, 2, 3):
            cov = cover_map(parsed, me)
            R = removable_set(cov)
            print(f"{thr:>7}{me:>10}{len(parsed):>9}{len(R):>9}{100*len(R)/len(parsed):>7.1f}%{len(parsed)-len(R):>9}")
        print()
