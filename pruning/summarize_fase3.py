#!/usr/bin/env python3
"""summarize_fase3.py — sintesi delle campagne della Fase 3.

Legge i JSON prodotti in `results/` e stampa, per ogni campagna, la tabella
variante × soglia con riduzione RFD, delta su corrette/errori/coverage/precision
rispetto al baseline, speedup e numero di configurazioni entro i 5 punti.

Uso:  python3 pruning/summarize_fase3.py [--json file1.json file2.json ...]
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import RESULTS, BENCH_JSON                       # noqa: E402


def m(vals):
    vals = [v for v in vals if v is not None and not (isinstance(v, float) and math.isnan(v))]
    return statistics.mean(vals) if vals else float("nan")


def load(paths):
    recs = []
    for p in paths:
        if os.path.exists(p):
            try:
                recs += json.load(open(p))
            except Exception as e:
                print(f"[avviso] {p}: {e}", file=sys.stderr)
    return recs


def index(recs):
    by = collections.defaultdict(dict)
    for r in recs:
        by[(r.get("family", "bridges"), r["threshold"], r["dataset"], r["run"])][r["variant"]] = r
    return by


def summarize(name, recs, base_json):
    """Confronta ogni variante con il baseline indicato, raggruppando per soglia."""
    base = index(json.load(open(base_json)))
    cur = index(recs)
    variants = sorted({r["variant"] for r in recs if r["variant"] != "A"})
    if not variants:
        return
    # baseline di riferimento: A dalla campagna stessa se presente, altrimenti quello esterno
    ref = {}
    for k, mm in cur.items():
        if "A" in mm:
            ref[k] = mm["A"]
    for k, mm in base.items():
        ref.setdefault(k, mm.get("A"))

    print("=" * 118)
    print(f"CAMPAGNA {name}")
    print("=" * 118)
    print(f"{'variante':<10}{'soglia':>7}{'n':>4}{'rid.%':>8}{'dCorr':>7}{'dCorr%':>8}"
          f"{'dErr':>7}{'dCov':>9}{'dPrec':>9}{'spPre':>7}{'spExec':>8}{'acc<5pt':>9}")
    print("-" * 118)
    for v in variants:
        for thr in sorted({k[1] for k in cur}):
            pairs = []
            for k, mm in cur.items():
                if k[1] != thr or v not in mm:
                    continue
                a = ref.get(k)
                if a is None or a.get("rc") != 0 or mm[v].get("rc") != 0:
                    continue
                pairs.append((a, mm[v]))
            if not pairs:
                continue
            tot = sum(a["correct"] for a, _ in pairs)
            dcor = sum(b["correct"] - a["correct"] for a, b in pairs)
            derr = sum(b["wrong"] - a["wrong"] for a, b in pairs)
            dacc = m([b["accuracy"] - a["accuracy"] for a, b in pairs])
            dcov = m([b["coverage"] - a["coverage"] for a, b in pairs])
            dprec = m([b["precision"] - a["precision"] for a, b in pairs
                       if a.get("precision") is not None and b.get("precision") is not None])
            red = m([b["rfd_reduction"] for _, b in pairs])
            spp = m([a.get("pre_ms") for a, _ in pairs]) / max(1e-9, m([b.get("pre_ms") for _, b in pairs]))
            spe = m([a.get("exec_ms") for a, _ in pairs]) / max(1e-9, m([b.get("exec_ms") for _, b in pairs]))
            oa = sum(1 for a, b in pairs if abs(b["accuracy"] - a["accuracy"]) <= 0.05)
            print(f"{v:<10}{thr:>7}{len(pairs):>4}{100*red:>7.1f}%{dcor:>+7d}"
                  f"{100*dcor/max(1,tot):>+7.1f}%{derr:>+7d}{dcov:>+9.4f}{dprec:>+9.4f}"
                  f"{spp:>6.2f}x{spe:>7.2f}x{oa:>6}/{len(pairs)}")
        print("-" * 118)

    # quante configurazioni fanno meglio o uguale del baseline
    for v in variants:
        n_ge = sum(1 for k, mm in cur.items()
                   if v in mm and k in ref and mm[v]["correct"] >= ref[k]["correct"])
        n_tot = sum(1 for k, mm in cur.items() if v in mm and k in ref)
        n_ident = sum(1 for k, mm in cur.items()
                      if v in mm and k in ref and mm[v]["correct"] == ref[k]["correct"]
                      and abs(mm[v]["coverage"] - ref[k]["coverage"]) < 1e-12)
        print(f"  {v}: corrette >= baseline in {n_ge}/{n_tot} configurazioni; "
              f"output identico in {n_ident}/{n_tot}")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", nargs="*", default=None)
    args = ap.parse_args()
    R = RESULTS
    if args.json:
        campaigns = [(os.path.basename(f).replace("results_benchmark_", "").replace(".json", ""), f)
                     for f in args.json]
    else:
        campaigns = [
        ("A1 score-argmin",              os.path.join(R, "results_benchmark_A1.json")),
        ("A1p score-argmin protect",     os.path.join(R, "results_benchmark_A1p.json")),
        ("A2 dom-sub-adaptive 0.85",     os.path.join(R, "results_benchmark_A2_0.85.json")),
        ("A2 dom-sub-adaptive 0.90",     os.path.join(R, "results_benchmark_A2_0.90.json")),
        ("A2u dom-sub-adaptive instab.", os.path.join(R, "results_benchmark_A2u.json")),
        ("A4 exact-priority",            os.path.join(R, "results_benchmark_A4.json")),
        ("A3 reorder null-count",        os.path.join(R, "results_benchmark_A3_null-count.json")),
        ("A3 reorder lhs-involvement",   os.path.join(R, "results_benchmark_A3_lhs-involvement.json")),
        ("B1 Glass (schema corretto)",   os.path.join(R, "results_benchmark_glass.json")),
        ("B2 Restaurant (testo)",        os.path.join(R, "results_benchmark_restaurant.json")),
        ]
    for name, path in campaigns:
        if not os.path.exists(path):
            print(f"[saltata] {name}: {os.path.basename(path)} non presente\n")
            continue
        recs = load([path])
        fams = {r.get("family", "bridges") for r in recs}
        if fams - {"bridges"}:
            # campagne su altri dataset: nessun baseline esterno
            summarize(name, recs, BENCH_JSON) if "bridges" in fams else _summarize_nobase(name, recs)
        else:
            summarize(name, recs, BENCH_JSON)


def _summarize_nobase(name, recs):
    by = index(recs)
    variants = sorted({r["variant"] for r in recs if r["variant"] != "A"})
    print("=" * 118)
    print(f"CAMPAGNA {name}  (baseline interno alla campagna)")
    print("=" * 118)
    print(f"{'variante':<10}{'soglia':>7}{'n':>4}{'rid.%':>8}{'coverage':>10}{'precision':>11}"
          f"{'accuracy':>10}{'dCorr':>7}{'identici':>10}")
    print("-" * 118)
    for v in variants:
        for thr in sorted({k[1] for k in by}):
            pairs = [(mm["A"], mm[v]) for k, mm in by.items()
                     if k[1] == thr and "A" in mm and v in mm
                     and mm["A"].get("rc") == 0 and mm[v].get("rc") == 0]
            if not pairs:
                continue
            ident = sum(1 for a, b in pairs if b["correct"] == a["correct"]
                        and abs(b["coverage"] - a["coverage"]) < 1e-12)
            print(f"{v:<10}{thr:>7}{len(pairs):>4}"
                  f"{100*m([b['rfd_reduction'] for _, b in pairs]):>7.1f}%"
                  f"{m([b['coverage'] for _, b in pairs]):>10.3f}"
                  f"{m([b['precision'] for _, b in pairs]):>11.3f}"
                  f"{m([b['accuracy'] for _, b in pairs]):>10.3f}"
                  f"{sum(b['correct']-a['correct'] for a, b in pairs):>+7d}"
                  f"{ident:>7}/{len(pairs)}")
        print("-" * 118)
    print()


if __name__ == "__main__":
    main()
