#!/usr/bin/env python3
"""Genera le tabelle markdown del report a partire da results_benchmark.json."""
import json, os, sys, math, collections, statistics, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import BENCH_JSON
from benchmark import wilcoxon_signed_rank, fmt_p


def mean(vals):
    vals = [v for v in vals if v is not None and not (isinstance(v, float) and math.isnan(v))]
    return statistics.mean(vals) if vals else float("nan")


def med(vals):
    vals = [v for v in vals if v is not None and not (isinstance(v, float) and math.isnan(v))]
    return statistics.median(vals) if vals else float("nan")


def fnum(v, nd=3):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return f"{v:.{nd}f}"


def load(path):
    return json.load(open(path))


def index(records):
    by = collections.defaultdict(dict)
    for r in records:
        by[(r["threshold"], r["dataset"], r["run"])][r["variant"]] = r
    return by


def table_aggregate(by, names, thresholds=None):
    thr_list = thresholds or sorted({k[0] for k in by})
    out = []
    out.append("| soglia | variante | RFD | rid. % | coverage | precision | accuracy | F1 | RFD usate | preproc (ms) | esecuzione (ms) | RMSE | MAE |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for thr in thr_list:
        for name in ["A"] + names:
            sub = [m[name] for k, m in by.items() if k[0] == thr and name in m and m[name].get("rc") == 0]
            if not sub:
                continue
            g = lambda k: mean([s.get(k) for s in sub])
            out.append(f"| {thr} | {'**A (baseline)**' if name == 'A' else name} "
                       f"| {g('rfd_out'):.0f} | {100*g('rfd_reduction'):.1f}% "
                       f"| {fnum(g('coverage'))} | {fnum(g('precision'))} | {fnum(g('accuracy'))} "
                       f"| {fnum(g('f1'))} | {g('n_rfd_used'):.1f} "
                       f"| {g('pre_ms'):.0f} | {g('exec_ms'):.0f} "
                       f"| {fnum(g('rmse'))} | {fnum(g('mae'))} |")
    return "\n".join(out)


def table_speedup(by, names):
    out = ["| soglia | variante | riduzione RFD | speedup preprocessing | speedup esecuzione | speedup totale |",
           "|---|---|---|---|---|---|"]
    for thr in sorted({k[0] for k in by}):
        base = [m["A"] for k, m in by.items() if k[0] == thr and "A" in m and m["A"].get("rc") == 0]
        if not base:
            continue
        b_pre, b_exec = mean([b.get("pre_ms") for b in base]), mean([b.get("exec_ms") for b in base])
        for name in names:
            sub = [m[name] for k, m in by.items() if k[0] == thr and name in m and m[name].get("rc") == 0]
            if not sub:
                continue
            p, e = mean([s.get("pre_ms") for s in sub]), mean([s.get("exec_ms") for s in sub])
            tp, te = mean([s.get("total_ms") for s in sub]), mean([b.get("total_ms") for b in base])
            red = mean([s.get("rfd_reduction") for s in sub])
            out.append(f"| {thr} | {name} | {100*red:.1f}% | {b_pre/p:.1f}× | {b_exec/e:.1f}× | {te/tp:.1f}× |")
    return "\n".join(out)


def table_wilcoxon(by, names, metrics=("accuracy", "coverage", "precision", "f1", "correct", "wrong",
                                        "n_rfd_used", "pre_ms", "exec_ms", "rmse", "mae")):
    out = ["| variante | metrica | n coppie | mediana Δ (B−A) | W+ | W− | p-value | significativo | metodo |",
           "|---|---|---|---|---|---|---|---|---|"]
    for name in names:
        for metric in metrics:
            xs, ys = [], []
            for k, m in by.items():
                if "A" in m and name in m and m["A"].get("rc") == 0 and m[name].get("rc") == 0:
                    a, b = m["A"].get(metric), m[name].get(metric)
                    if a is None or b is None:
                        continue
                    if isinstance(a, float) and math.isnan(a):
                        continue
                    if isinstance(b, float) and math.isnan(b):
                        continue
                    xs.append(b); ys.append(a)
            if len(xs) < 3:
                continue
            r = wilcoxon_signed_rank(xs, ys)
            sig = "**sì**" if r["p"] < 0.05 else "no"
            md = r.get("median_diff")
            mds = f"{md:+.4f}" if md is not None else "—"
            out.append(f"| {name} | {metric} | {r['n']} | {mds} | {r['W+']:.1f} | {r['W-']:.1f} "
                       f"| {fmt_p(r['p'])} | {sig} | {r.get('method','')} |")
    return "\n".join(out)


def table_tolerance(by, names, tol=0.05):
    """Per quante configurazioni la variante resta entro tol (assoluto e relativo) su coverage/accuracy."""
    out = ["| variante | soglia | config entro 5% (accuracy) | config entro 5% (coverage) "
           "| config senza perdita di corrette | Δ corrette totale |", "|---|---|---|---|---|---|"]
    for name in names:
        for thr in sorted({k[0] for k in by}):
            pairs = [(m["A"], m[name]) for k, m in by.items()
                     if k[0] == thr and "A" in m and name in m and m["A"].get("rc") == 0 and m[name].get("rc") == 0]
            if not pairs:
                continue
            n = len(pairs)
            ok_acc = sum(1 for a, b in pairs if abs(b["accuracy"] - a["accuracy"]) <= tol)
            ok_cov = sum(1 for a, b in pairs if abs(b["coverage"] - a["coverage"]) <= tol)
            ok_cor = sum(1 for a, b in pairs if b["correct"] >= a["correct"])
            dcor = sum(b["correct"] - a["correct"] for a, b in pairs)
            out.append(f"| {name} | {thr} | {ok_acc}/{n} | {ok_cov}/{n} | {ok_cor}/{n} | {dcor:+d} |")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=BENCH_JSON)
    ap.add_argument("--extra", default=None, help="JSON aggiuntivo da unire (es. varianti round 2)")
    ap.add_argument("--section", default="all",
                    choices=["all", "aggregate", "speedup", "wilcoxon", "tolerance"])
    args = ap.parse_args()

    records = load(args.json)
    if args.extra and os.path.exists(args.extra):
        records += load(args.extra)
    by = index(records)
    names = sorted({r["variant"] for r in records if r["variant"] != "A"})
    print(f"<!-- {len(records)} record, varianti: {names} -->\n")
    if args.section in ("all", "aggregate"):
        print("### Tabella comparativa aggregata\n")
        print(table_aggregate(by, names)); print()
    if args.section in ("all", "speedup"):
        print("### Speedup\n")
        print(table_speedup(by, names)); print()
    if args.section in ("all", "tolerance"):
        print("### Tolleranza del 5%\n")
        print(table_tolerance(by, names)); print()
    if args.section in ("all", "wilcoxon"):
        print("### Test di Wilcoxon signed-rank\n")
        print(table_wilcoxon(by, names)); print()


if __name__ == "__main__":
    main()
