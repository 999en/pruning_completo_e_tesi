#!/usr/bin/env python3
"""
verify_hypotheses_fase4.py — verifica delle ipotesi H8 e H9 della Fase 4.

H8: `precision-priority` da solo produce Δ precision ≥ +2 punti rispetto al baseline,
    con Δ corrette ≥ 0 su almeno 8/10 configurazioni.
H9: la combinazione P4 supera A5b su almeno una metrica di qualità (coverage, corrette,
    precision) mantenendo le altre entro 2 punti.

Uso:
    python3 pruning/verify_hypotheses_fase4.py
"""
from __future__ import annotations

import collections
import json
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import RESULTS, BENCH_JSON                       # noqa: E402
from benchmark import wilcoxon_signed_rank, fmt_p           # noqa: E402

P1P2 = os.path.join(RESULTS, "results_benchmark_P1P2.json")
P3P4 = os.path.join(RESULTS, "results_benchmark_P3P4.json")
A5B = os.path.join(RESULTS, "results_benchmark_A5b.json")
GLASS = os.path.join(RESULTS, "results_benchmark_glass.json")


def load(path):
    return json.load(open(path)) if os.path.exists(path) else []


def index(recs):
    by = collections.defaultdict(dict)
    for r in recs:
        if r.get("rc") == 0:
            by[(r["threshold"], r["dataset"], r["run"])][r["variant"]] = r
    return by


def mean(v):
    v = [x for x in v if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return statistics.mean(v) if v else float("nan")


def delta_rows(by, ref, variant, label):
    rows = []
    for thr in sorted({k[0] for k in by}):
        pairs = [(ref[k], mm[variant]) for k, mm in by.items()
                 if k[0] == thr and variant in mm and k in ref]
        if not pairs:
            continue
        rows.append(dict(
            thr=thr, n=len(pairs),
            d_correct=sum(b["correct"] - a["correct"] for a, b in pairs),
            d_wrong=sum(b["wrong"] - a["wrong"] for a, b in pairs),
            d_cov=mean([b["coverage"] - a["coverage"] for a, b in pairs]),
            d_prec=mean([b["precision"] - a["precision"] for a, b in pairs
                         if a.get("precision") is not None and b.get("precision") is not None]),
            d_acc=mean([b["accuracy"] - a["accuracy"] for a, b in pairs]),
            n_ge_correct=sum(1 for a, b in pairs if b["correct"] >= a["correct"]),
            n_ge_cov=sum(1 for a, b in pairs if b["coverage"] >= a["coverage"] - 1e-12),
            n_ge_prec=sum(1 for a, b in pairs if (b["precision"] or 0) >= (a["precision"] or 0) - 1e-12),
            n_ident=sum(1 for a, b in pairs if b["correct"] == a["correct"]
                        and abs(b["coverage"] - a["coverage"]) < 1e-12),
            d_rfd=mean([b["rfd_reduction"] for _, b in pairs])))
    return rows


def print_rows(rows, label):
    print(f"\n--- {label} ---")
    print(f"{'soglia':>7}{'n':>4}{'dCorr':>7}{'dErr':>7}{'dCov':>9}{'dPrec':>9}{'dAcc':>9}"
          f"{'corr>=':>9}{'cov>=':>8}{'prec>=':>9}{'identici':>10}{'rid%':>7}")
    for r in rows:
        print(f"{r['thr']:>7}{r['n']:>4}{r['d_correct']:>+7d}{r['d_wrong']:>+7d}"
              f"{r['d_cov']:>+9.4f}{r['d_prec']:>+9.4f}{r['d_acc']:>+9.4f}"
              f"{r['n_ge_correct']:>6}/{r['n']}{r['n_ge_cov']:>5}/{r['n']}"
              f"{r['n_ge_prec']:>6}/{r['n']}{r['n_ident']:>7}/{r['n']}"
              f"{100*r['d_rfd']:>6.1f}%")


def main():
    base = index(load(BENCH_JSON))
    ref = {k: mm["A"] for k, mm in base.items() if "A" in mm}

    print("=" * 112)
    print("FASE 4 — VERIFICA DELLE IPOTESI H8 e H9")
    print("=" * 112)

    # ---------------- H8 ----------------
    print("\n### H8 — `precision-priority` da solo (P1) e con exact-first (P2)")
    p1p2 = index(load(P1P2))
    if not p1p2:
        print("  [dati non ancora disponibili]")
    else:
        for v in ("P1", "P2"):
            rows = delta_rows(p1p2, ref, v, v)
            if rows:
                print_rows(rows, f"{v} vs baseline")
        # verdetto
        rows = delta_rows(p1p2, ref, "P1", "P1")
        if rows:
            dprec = mean([r["d_prec"] for r in rows])
            tot_n = sum(r["n"] for r in rows)
            ge = sum(r["n_ge_correct"] for r in rows)
            ident = sum(r["n_ident"] for r in rows)
            print(f"\n  Δ precision medio (P1): {dprec:+.4f} punti "
                  f"({'>=' if dprec >= 0.02 else '<'} +0,02 richiesto)")
            print(f"  config con corrette >= baseline: {ge}/{tot_n} "
                  f"({'>=' if ge >= 0.8*tot_n else '<'} 8/10 richiesto)")
            print(f"  config con output identico al baseline: {ident}/{tot_n} "
                  f"(se alto, il riordino non ha avuto effetto)")
            print(f"  => H8 {'CONFERMATA' if (dprec >= 0.02 and ge >= 0.8*tot_n) else 'FALSIFICATA'}")

            # Wilcoxon
            print("\n  Test di Wilcoxon signed-rank (P1 vs baseline):")
            for metric in ("correct", "coverage", "precision", "wrong", "accuracy"):
                xs, ys = [], []
                for k, mm in p1p2.items():
                    if "P1" in mm and k in ref:
                        xs.append(mm["P1"][metric]); ys.append(ref[k][metric])
                if len(xs) < 3:
                    continue
                w = wilcoxon_signed_rank(xs, ys)
                md = w.get("median_diff")
                print(f"    {metric:<10} n={w['n']:<4} mediana Δ={md if md is None else f'{md:+.4f}':>9} "
                      f"p={fmt_p(w['p']):>9} {'significativo' if w['p'] < 0.05 else 'non significativo'}")

    # ---------------- H9 ----------------
    print("\n\n### H9 — P4 vs A5b (stessa α=0,85)")
    p3p4 = index(load(P3P4))
    a5b = index(load(A5B))
    if not p3p4 or not a5b:
        print("  [dati non ancora disponibili]")
    else:
        print_rows(delta_rows(p3p4, ref, "P3", "P3"), "P3 vs baseline")
        print_rows(delta_rows(p3p4, ref, "P4", "P4"), "P4 vs baseline")

        common = sorted(set(p3p4) & set(a5b))
        pairs = [(a5b[k]["A5b"], p3p4[k]["P4"]) for k in common
                 if "A5b" in a5b[k] and "P4" in p3p4[k]]
        if pairs:
            print(f"\n  confronto diretto P4 vs A5b su {len(pairs)} configurazioni comuni:")
            print(f"{'metrica':<12}{'A5b':>12}{'P4':>12}{'Δ':>10}{'p (Wilcoxon)':>14}")
            verdict = {}
            for metric in ("correct", "coverage", "precision", "wrong", "accuracy"):
                va = mean([a[metric] for a, _ in pairs])
                vb = mean([b[metric] for _, b in pairs])
                xs = [b[metric] for _, b in pairs]; ys = [a[metric] for a, _ in pairs]
                w = wilcoxon_signed_rank(xs, ys)
                verdict[metric] = (vb - va, w["p"])
                print(f"{metric:<12}{va:>12.4f}{vb:>12.4f}{vb-va:>+10.4f}{fmt_p(w['p']):>14}")
            # H9: P4 supera A5b su >=1 metrica mantenendo le altre entro 2 punti
            better = [m for m in ("correct", "coverage", "precision") if verdict[m][0] > 0]
            within = all(verdict[m][0] >= -0.02 for m in ("correct", "coverage", "precision"))
            print(f"\n  metriche in cui P4 supera A5b: {better if better else 'nessuna'}")
            print(f"  tutte le metriche di qualita' entro -2 punti: {'si' if within else 'no'}")
            print(f"  => H9 {'CONFERMATA' if (better and within) else 'FALSIFICATA'}")


if __name__ == "__main__":
    main()
