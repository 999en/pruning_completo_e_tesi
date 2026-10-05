#!/usr/bin/env python3
"""
ablation_a5b.py — ablazione di A5b, merge della griglia completa e Wilcoxon.

A5b = `exact-priority` + `dom-sub-adaptive` (α = 0,85). Questo script non esegue RENUVER:
legge soltanto i JSON prodotti da `benchmark.py` e stampa le tre tabelle del §10.5.

  1. ABLAZIONE   — contributo isolato di ciascun componente, sulle stesse 10 configurazioni
                   (Bridges, run 1-2, soglie 9 e 15) su cui erano stati misurati A2 e A4.
  2. MERGE       — unisce A5b run 1-2 (Fase 3) con i run 3-5 e ricalcola il Wilcoxon su n = 25.
  3. MULTI-DATASET — A5b su Bridges / Glass / Restaurant con la stessa metrica.

Il test di Wilcoxon e' quello di `benchmark.py` (esatto per n <= 25 senza ranghi medi):
**scipy non e' installato in questo ambiente**, quindi non si usa `scipy.stats.wilcoxon`.

Uso:
    python3 pruning/ablation_a5b.py
    python3 pruning/ablation_a5b.py --json        # output anche in .scratch/f5/ablation.json
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

from benchmark import wilcoxon_signed_rank, fmt_p            # noqa: E402
from paths import RESULTS, SCRATCH                           # noqa: E402

CANON = os.path.join(RESULTS, "results_benchmark.json")


def load(name):
    path = name if os.path.isabs(name) else os.path.join(RESULTS, name)
    if not os.path.exists(path):
        return []
    return json.load(open(path, encoding="utf-8"))


def index_variant(recs, variant):
    """{(dataset, run, soglia): record} per la variante richiesta."""
    return {(r["dataset"], r["run"], r["threshold"]): r
            for r in recs if r.get("variant") == variant}


def canon_baseline():
    return index_variant(load(CANON), "A")


def speedup(base, var):
    """Mediana di exec_ms(baseline)/exec_ms(variante) sulle coppie con entrambi i valori."""
    rs = [b["exec_ms"] / v["exec_ms"] for b, v in zip(base, var)
          if b.get("exec_ms") and v.get("exec_ms")]
    return (statistics.median(rs), len(rs)) if rs else (None, 0)


def pair_stats(base, var):
    n = len(base)
    return dict(
        n=n,
        d_corr=sum(v["correct"] - b["correct"] for b, v in zip(base, var)),
        d_err=sum(v["wrong"] - b["wrong"] for b, v in zip(base, var)),
        d_prec=sum((v.get("precision") or 0) - (b.get("precision") or 0) for b, v in zip(base, var)) / n,
        d_cov=sum(v["coverage"] - b["coverage"] for b, v in zip(base, var)) / n,
        red=100 * sum(v["rfd_reduction"] for v in var) / n,
        base_corr=sum(b["correct"] for b in base),
        var_corr=sum(v["correct"] for v in var),
        base_err=sum(b["wrong"] for b in base),
        var_err=sum(v["wrong"] for v in var),
    )


# =====================================================================================
def tabella_ablazione():
    print("=" * 112)
    print("§10.5.1  ABLAZIONE DI A5b — Bridges, run 1-2, n = 10 per soglia")
    print("=" * 112)
    canon = canon_baseline()
    specs = [("baseline", None, None),
             ("dom-sub-adaptive α=0,85 (solo)", "results_benchmark_A2_0.85.json", "A2"),
             ("exact-priority (solo)", "results_benchmark_A4.json", "A4"),
             ("A5b (combinazione)", "results_benchmark_A5b.json", "A5b")]
    out = {}
    print(f"{'componente':<32}{'thr':>4}{'n':>3}{'rid.RFD':>9}{'Δcorr':>7}{'Δerr':>6}"
          f"{'Δprec':>9}{'Δcov':>9}{'speedup':>10}{'n_sp':>5}")
    print("-" * 112)
    for label, fn, var in specs:
        if fn is None:
            # la riga di riferimento usa le STESSE configurazioni dell'ablazione
            # (Bridges, run 1-2, soglie 9 e 15), non l'intero baseline
            for thr in (9, 15):
                ks = sorted(k for k in canon if k[2] == thr and k[1] in (1, 2))
                n = len(ks)
                print(f"{label:<32}{thr:>4}{n:>3}{0.0:>8.1%}{0:>+7d}{0:>+6d}{0.0:>+9.3f}{0.0:>+9.3f}{'1,0×':>10}{n:>5}")
            continue
        recs = load(fn)
        if not recs:
            print(f"{label:<32}  [file assente: {fn}]")
            continue
        ix = index_variant(recs, var)
        for thr in (9, 15):
            ks = sorted(k for k in ix if k[2] == thr and k in canon)
            if not ks:
                continue
            base = [canon[k] for k in ks]
            vari = [ix[k] for k in ks]
            st = pair_stats(base, vari)
            sp, nsp = speedup(base, vari)
            out[f"{label}|{thr}"] = {**st, "speedup": sp, "n_speedup": nsp}
            print(f"{label:<32}{thr:>4}{st['n']:>3}{st['red']:>8.1f}%{st['d_corr']:>+7d}"
                  f"{st['d_err']:>+6d}{st['d_prec']:>+9.3f}{st['d_cov']:>+9.3f}"
                  f"{(f'{sp:.1f}×' if sp else 'n/d'):>10}{nsp:>5}")
    print("-" * 112)
    print("Valori assoluti (corrette/errori), per leggere le percentuali della tabella del report:")
    for label, fn, var in specs:
        if fn is None:
            continue
        ix = index_variant(load(fn), var)
        for thr in (9, 15):
            ks = sorted(k for k in ix if k[2] == thr and k in canon)
            if not ks:
                continue
            st = pair_stats([canon[k] for k in ks], [ix[k] for k in ks])
            print(f"   {label:<32} thr={thr}: {st['base_corr']} → {st['var_corr']} corrette, "
                  f"{st['base_err']} → {st['var_err']} errori")
    return out


# =====================================================================================
def merge_e_wilcoxon():
    print()
    print("=" * 112)
    print("MERGE DELLA GRIGLIA COMPLETA (Bridges) E TEST DI WILCOXON")
    print("=" * 112)
    canon = canon_baseline()
    old = load("results_benchmark_A5b.json")
    new = load("results_A5b_bridges_r345.json")
    a5b_old = [r for r in old if r.get("variant") == "A5b"]
    a5b_new = [r for r in new if r.get("variant") == "A5b"]
    print(f"results_benchmark_A5b.json      : {len(a5b_old)} record A5b (run 1-2)")
    print(f"results_A5b_bridges_r345.json   : {len(a5b_new)} record A5b (run 3-5)")

    # il file merged conserva le baseline gia' presenti in results_benchmark_A5b.json
    merged = old + a5b_new
    out_path = os.path.join(RESULTS, "results_A5b_bridges_full.json")
    json.dump(merged, open(out_path, "w", encoding="utf-8"), indent=1)
    print(f"scritto {out_path}: {len(merged)} record "
          f"({len([r for r in merged if r.get('variant')=='A5b'])} A5b + "
          f"{len([r for r in merged if r.get('variant')=='A'])} baseline A)")

    ix = index_variant(a5b_old + a5b_new, "A5b")
    keys = sorted(k for k in ix if k in canon)
    print(f"configurazioni A5b appaiabili con il baseline: {len(keys)}")
    missing = sorted(set(canon) - set(ix))
    print(f"configurazioni del baseline senza A5b        : {len(missing)}"
          + (f"  (es. {missing[:4]})" if missing else ""))
    print()
    print(f"{'soglia':>7}{'n':>4}{'Δcorr':>8}{'Δerr':>7}{'Δprec':>10}{'Δcov':>10}{'rid.RFD':>10}"
          f"{'speedup':>10}{'Wilcoxon n':>12}{'p':>12}")
    print("-" * 112)
    for thr in (9, 15):
        ks = [k for k in keys if k[2] == thr]
        if not ks:
            continue
        base = [canon[k] for k in ks]
        vari = [ix[k] for k in ks]
        st = pair_stats(base, vari)
        sp, nsp = speedup(base, vari)
        w = wilcoxon_signed_rank([v["correct"] for v in vari], [b["correct"] for b in base])
        print(f"{thr:>7}{st['n']:>4}{st['d_corr']:>+8d}{st['d_err']:>+7d}{st['d_prec']:>+10.3f}"
              f"{st['d_cov']:>+10.3f}{st['red']:>9.1f}%{(f'{sp:.1f}×' if sp else 'n/d'):>10}"
              f"{w['n']:>12}{fmt_p(w['p']):>12}")
    # complessivo
    base = [canon[k] for k in keys]
    vari = [ix[k] for k in keys]
    st = pair_stats(base, vari)
    sp, nsp = speedup(base, vari)
    w = wilcoxon_signed_rank([v["correct"] for v in vari], [b["correct"] for b in base])
    we = wilcoxon_signed_rank([-v["wrong"] for v in vari], [-b["wrong"] for b in base])
    print("-" * 112)
    print(f"{'TOTALE':>7}{st['n']:>4}{st['d_corr']:>+8d}{st['d_err']:>+7d}{st['d_prec']:>+10.3f}"
          f"{st['d_cov']:>+10.3f}{st['red']:>9.1f}%{(f'{sp:.1f}×' if sp else 'n/d'):>10}"
          f"{w['n']:>12}{fmt_p(w['p']):>12}")
    print(f"   Wilcoxon corrette : n={w['n']} W+={w['W+']:.1f} W-={w['W-']:.1f} p={fmt_p(w['p'])} ({w['method']})")
    print(f"   Wilcoxon errori   : n={we['n']} W+={we['W+']:.1f} W-={we['W-']:.1f} p={fmt_p(we['p'])} ({we['method']})")
    return st, w, len(keys)


# =====================================================================================
def tabella_multidataset():
    print()
    print("=" * 112)
    print("§10.5.2  A5b SU BRIDGES / GLASS / RESTAURANT")
    print("=" * 112)
    full = os.path.join(RESULTS, "results_A5b_bridges_full.json")
    specs = [
        ("Bridges", full, "A5b", CANON, "A"),
        ("Glass", "results_A5b_glass.json", "A5b", "results_A5b_glass.json", "A"),
        ("Restaurant", "results_A5b_restaurant.json", "A5b", "results_A5b_restaurant.json", "A"),
    ]
    print(f"{'dataset':<16}{'thr':>5}{'n':>4}{'rid.RFD':>9}{'Δcorr':>8}{'Δerr':>7}"
          f"{'Δprec':>10}{'Δcov':>10}{'corrette':>18}")
    print("-" * 112)
    for label, fn, var, bfn, bvar in specs:
        recs = load(fn)
        if not recs:
            print(f"{label:<16}  [file assente: {os.path.basename(fn)}]")
            continue
        ix = index_variant(recs, var)
        # baseline: canonica per Bridges, interna al file per Glass/Restaurant
        bix = canon_baseline() if os.path.basename(bfn) == os.path.basename(CANON) else index_variant(load(bfn), bvar)
        for thr in ([9, 15] if label.startswith("Bridges") else sorted({k[2] for k in ix})):
            ks = sorted(k for k in ix if k[2] == thr and k in bix)
            if not ks:
                continue
            st = pair_stats([bix[k] for k in ks], [ix[k] for k in ks])
            print(f"{label:<16}{thr:>5}{st['n']:>4}{st['red']:>8.1f}%{st['d_corr']:>+8d}"
                  f"{st['d_err']:>+7d}{st['d_prec']:>+10.3f}{st['d_cov']:>+10.3f}"
                  f"{str(st['base_corr'])+' → '+str(st['var_corr']):>18}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="salva anche .scratch/f5/ablation.json")
    args = ap.parse_args()
    abl = tabella_ablazione()
    merge_e_wilcoxon()
    tabella_multidataset()
    if args.json:
        os.makedirs(SCRATCH, exist_ok=True)
        p = os.path.join(SCRATCH, "f5", "ablation.json")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(abl, open(p, "w", encoding="utf-8"), indent=1)
        print(f"\nablazione salvata in {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
