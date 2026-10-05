#!/usr/bin/env python3
"""fill_report.py — riempie i marker di report.md con le tabelle generate dai JSON del benchmark."""
import os, sys, json, math, statistics, collections, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import REPORT, RESULTS
from make_report import index, table_aggregate, table_speedup, table_wilcoxon, table_tolerance, load
from benchmark import wilcoxon_signed_rank, fmt_p


def m(vals):
    vals = [v for v in vals if v is not None and not (isinstance(v, float) and math.isnan(v))]
    return statistics.mean(vals) if vals else float("nan")


def summary_stats(by, names, thresholds):
    """Righe di sintesi: riduzione, Δcorrette relativo, Δacc, Δcov, configurazioni entro 5pt."""
    out = []
    for name in names:
        for thr in thresholds:
            pairs = [(k, mm["A"], mm[name]) for k, mm in by.items()
                     if k[0] == thr and "A" in mm and name in mm
                     and mm["A"].get("rc") == 0 and mm[name].get("rc") == 0]
            if not pairs:
                continue
            tot_corr = sum(a["correct"] for _, a, _ in pairs)
            dcor = sum(b["correct"] - a["correct"] for _, a, b in pairs)
            dacc = m([b["accuracy"] - a["accuracy"] for _, a, b in pairs])
            dcov = m([b["coverage"] - a["coverage"] for _, a, b in pairs])
            dpres = m([b["precision"] - a["precision"] for _, a, b in pairs
                       if a["precision"] is not None and b["precision"] is not None])
            derr = sum(b["wrong"] - a["wrong"] for _, a, b in pairs)
            red = m([b["rfd_reduction"] for _, _, b in pairs])
            sp_pre = m([a["pre_ms"] for _, a, _ in pairs]) / max(1e-9, m([b["pre_ms"] for _, _, b in pairs]))
            sp_ex = m([a["exec_ms"] for _, a, _ in pairs]) / max(1e-9, m([b["exec_ms"] for _, _, b in pairs]))
            n = len(pairs)
            ok_a = sum(1 for _, a, b in pairs if abs(b["accuracy"] - a["accuracy"]) <= 0.05)
            ok_c = sum(1 for _, a, b in pairs if abs(b["coverage"] - a["coverage"]) <= 0.05)
            out.append(dict(variant=name, threshold=thr, n=n, reduction=red,
                            d_correct=dcor, d_correct_rel=100 * dcor / max(1, tot_corr),
                            d_acc=dacc, d_cov=dcov, d_prec=dpres, d_err=derr,
                            sp_pre=sp_pre, sp_ex=sp_ex, ok_acc=ok_a, ok_cov=ok_c))
    return out


def table_summary(rows, variants=None):
    out = ["| variante | soglia | n | rid. RFD | Δ corrette | Δ corrette % | Δ accuracy | Δ coverage "
           "| Δ precision | Δ errori | speedup preproc | speedup esec. | acc entro 5pt | cov entro 5pt |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if variants and r["variant"] not in variants:
            continue
        out.append(f"| {r['variant']} | {r['threshold']} | {r['n']} | {100*r['reduction']:.1f}% "
                   f"| {r['d_correct']:+d} | {r['d_correct_rel']:+.1f}% | {r['d_acc']:+.4f} "
                   f"| {r['d_cov']:+.4f} | {r['d_prec']:+.4f} | {r['d_err']:+d} "
                   f"| {r['sp_pre']:.1f}× | {r['sp_ex']:.1f}× | {r['ok_acc']}/{r['n']} | {r['ok_cov']}/{r['n']} |")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=REPORT)
    ap.add_argument("--bench", default=os.path.join(RESULTS, "results_benchmark.json"))
    ap.add_argument("--r2", default=os.path.join(RESULTS, "results_benchmark_r2.json"))
    ap.add_argument("--r3", default=os.path.join(RESULTS, "results_benchmark_r3.json"))
    ap.add_argument("--d", default=os.path.join(RESULTS, "results_benchmark_D.json"))
    ap.add_argument("--fill-main", action="store_true", help="riempi anche RISPOSTA_GUIDA e TIPO_B")
    args = ap.parse_args()

    if not os.path.exists(args.report):
        print(f"[nota] file di relazione assente: {args.report}\n"
              f"       non c'e' nulla da riempire (la relazione tecnica estesa e' un documento a parte).")
        return 0

    records = load(args.bench)
    thresholds = sorted({r["threshold"] for r in records})
    by = index(records)
    names = sorted({r["variant"] for r in records if r["variant"] != "A"})
    rows = summary_stats(by, names, thresholds)

    blocks = {
        "AGGREGATE": table_aggregate(by, names),
        "SPEEDUP": table_speedup(by, names),
        "TOLERANCE": table_tolerance(by, names),
        "WILCOXON": table_wilcoxon(by, names),
    }
    # blocco di sintesi (variante raccomandata)
    blocks["SINTESI"] = table_summary(rows, variants={"S1"})

    # round 2/3 opzionali
    for tag, path in (("R2", args.r2), ("R3", args.r3)):
        if os.path.exists(path):
            extra = load(path)
            byx = index(records + extra)
            nx = sorted({r["variant"] for r in extra})
            blocks[f"TAB_{tag}"] = table_summary(summary_stats(byx, nx, sorted({r["threshold"] for r in extra})), nx)
            blocks[f"WILCOXON_{tag}"] = table_wilcoxon(byx, nx)
    if os.path.exists(args.d):
        drec = load(args.d)
        byd = index(drec)
        nd = sorted({r["variant"] for r in drec if r["variant"] != "A"})
        # confronto A(B) vs A(D) sullo stesso insieme di configurazioni
        basemain = {(r["threshold"], r["dataset"], r["run"]): r for r in records if r["variant"] == "A"}
        lines = ["| configurazione | corrette con `B` | corrette con `D` | Δ | copertura `B` | copertura `D` | Δ |",
                 "|---|---|---|---|---|---|---|"]
        agg = [0, 0]
        for k, mm in sorted(byd.items()):
            if "A" not in mm:
                continue
            aB = basemain.get(k)
            if not aB:
                continue
            aD = mm["A"]
            agg[0] += aB["correct"]; agg[1] += aD["correct"]
            lines.append(f"| {k[1]} run {k[2]} | {aB['correct']} | {aD['correct']} "
                         f"| {aD['correct']-aB['correct']:+d} | {aB['coverage']:.3f} | {aD['coverage']:.3f} "
                         f"| {aD['coverage']-aB['coverage']:+.3f} |")
        lines.append(f"| **TOTALE** | **{agg[0]}** | **{agg[1]}** | **{agg[1]-agg[0]:+d}** | | | |")
        blocks["TIPO_B"] = "\n".join(lines)

    txt = open(args.report, encoding="utf-8").read()
    filled = []
    for key, val in blocks.items():
        marker = f"<<{key}>>"
        if marker in txt:
            txt = txt.replace(marker, val)
            filled.append(key)
    open(args.report, "w", encoding="utf-8").write(txt)
    print(f"marker riempiti: {', '.join(filled)}")
    remaining = [l for l in txt.splitlines() if l.strip().startswith("<<")]
    if remaining:
        print("marker ancora vuoti:", remaining)


if __name__ == "__main__":
    main()
