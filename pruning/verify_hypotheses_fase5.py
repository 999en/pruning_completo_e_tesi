#!/usr/bin/env python3
"""
verify_hypotheses_fase5.py — verifica delle ipotesi H10–H13 della Fase 5.

H10: α=3 aumenta Δ corrette di ≥20% rispetto ad α=0 sulle stesse configurazioni.
H11: `precision-priority` su Glass e Restaurant produce Δ corrette > 0 in media,
     con ≥70% di configurazioni positive.
H12: la versione regolarizzata migliora su Glass/Restaurant più che su Bridges.
H13: `intra-cluster-priority` cambia il vincitore (Δ corrette > 0) oppure è inerte (Δ corrette = 0).

Uso:  python3 pruning/verify_hypotheses_fase5.py
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

def p(*a): return os.path.join(RESULTS, *a)


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


def delta(by, ref, variant, only=None):
    """Somma i delta su tutte le configurazioni presenti in `by` e nel riferimento."""
    rows = []
    for k, mm in by.items():
        if variant not in mm or k not in ref:
            continue
        if only is not None and k not in only:
            continue
        a, b = ref[k], mm[variant]
        rows.append((k, a, b))
    return rows


def summarize(rows):
    if not rows:
        return None
    d_corr = sum(b["correct"] - a["correct"] for _, a, b in rows)
    d_wrong = sum(b["wrong"] - a["wrong"] for _, a, b in rows)
    tot = sum(a["correct"] for _, a, _ in rows)
    return dict(
        n=len(rows), d_corr=d_corr, d_wrong=d_wrong,
        d_corr_rel=100 * d_corr / max(1, tot),
        d_cov=mean([b["coverage"] - a["coverage"] for _, a, b in rows]),
        d_prec=mean([b["precision"] - a["precision"] for _, a, b in rows
                     if a.get("precision") is not None and b.get("precision") is not None]),
        d_acc=mean([b["accuracy"] - a["accuracy"] for _, a, b in rows]),
        n_pos=sum(1 for _, a, b in rows if b["correct"] > a["correct"]),
        n_neg=sum(1 for _, a, b in rows if b["correct"] < a["correct"]),
        n_ident=sum(1 for _, a, b in rows if b["correct"] == a["correct"]
                    and abs(b["coverage"] - a["coverage"]) < 1e-12))


def line(tag, s):
    if not s:
        print(f"  {tag:<28} [nessun dato]")
        return
    print(f"  {tag:<28} n={s['n']:<4} Δcorr={s['d_corr']:+5d} ({s['d_corr_rel']:+6.2f}%) "
          f"Δerr={s['d_wrong']:+5d} Δcov={s['d_cov']:+.4f} Δprec={s['d_prec']:+.4f} "
          f"| +{s['n_pos']}/-{s['n_neg']}/={s['n_ident']}")


def main():
    base = index(load(BENCH_JSON))
    ref = {k: mm["A"] for k, mm in base.items() if "A" in mm}
    print("=" * 118)
    print("FASE 5 — VERIFICA DELLE IPOTESI H10–H13")
    print("=" * 118)

    # ---------------- H10: sweep di alpha ----------------
    print("\n### H10 — sweep dello shrinkage α (Bridges, run 1–2)")
    alphas = {}
    for a in ("1.0", "3.0", "10.0"):
        recs = load(p(f"results_benchmark_alpha_{a}.json"))
        if recs:
            alphas[a] = index(recs)
    # α = 0 = P1 dalla campagna di Fase 4
    p1 = index(load(p("results_benchmark_P1P2.json")))
    # per confrontare ad armi pari si usa l'intersezione delle configurazioni con α=1.0
    common = None
    for ix in list(alphas.values()) + [p1]:
        keys = {k for k, mm in ix.items() if "R" in mm or "P1" in mm}
        common = keys if common is None else (common & keys)
    if common:
        print(f"  configurazioni comuni a tutte le varianti: {len(common)}")
        line("α = 0 (P1)", summarize(delta(p1, ref, "P1", only=common)))
        null_h10 = summarize(delta(p1, ref, "P1", only=common))
        results = {}
        for a, ix in sorted(alphas.items()):
            s = summarize(delta(ix, ref, "R", only=common))
            results[a] = s
            line(f"α = {a}", s)
        if null_h10 and null_h10["d_corr"] > 0:
            print(f"\n  guadagno di α=0: {null_h10['d_corr']:+d} corrette")
            for a, s in sorted(results.items()):
                if s:
                    gain = s["d_corr"] - null_h10["d_corr"]
                    print(f"  α={a:<5} Δcorr vs α=0: {gain:+d} ({100*gain/null_h10['d_corr']:+.1f}%)")
            best = max(((a, s) for a, s in results.items() if s),
                       key=lambda kv: kv[1]["d_corr"], default=None)
            if best:
                a_best, s_best = best
                gain = s_best["d_corr"] - null_h10["d_corr"]
                rel = 100 * gain / null_h10["d_corr"]
                ok = rel >= 20.0
                # H10 chiede specificamente α=3
                s3 = results.get("3.0")
                g3 = (s3["d_corr"] - null_h10["d_corr"]) if s3 else None
                r3 = (100 * g3 / null_h10["d_corr"]) if g3 is not None else None
                print(f"\n  migliore: α={a_best} con {s_best['d_corr']:+d} corrette")
                if r3 is not None:
                    print(f"  α=3 vs α=0: {g3:+d} corrette ({r3:+.1f}%) "
                          f"-> H10 {'CONFERMATA' if r3 >= 20.0 else 'FALSIFICATA'}")

    # ---------------- P-a: il meccanismo dell' "ultimo cluster" ----------------
    # Se nei tuple multi-cella il valore e' deciso dall'ULTIMO cluster produttivo della colonna
    # (e non dal primo), allora l'esito dipende solo dalla posizione finale dei cluster:
    #   * alpha=1 cambia il primo cluster di 4 colonne ma l'ultimo di NESSUNA -> deve essere inerte;
    #   * alpha=10 e alpha=3 hanno gli STESSI ultimi cluster in tutte le colonne -> devono coincidere.
    print("\n\n### P-a — il meccanismo dell'ultimo cluster (predizione falsificabile)")
    p1ix = index(load(p("results_benchmark_P1P2.json")))
    a1ix = index(load(p("results_benchmark_alpha_1.0.json")))
    a3ix = index(load(p("results_benchmark_alpha_3.0.json")))
    a10ix = index(load(p("results_benchmark_alpha_10.0.json")))

    def compare(ix_a, va, ix_b, vb, label):
        """Quante configurazioni comuni hanno metriche IDENTICHE fra le due varianti."""
        keys = sorted({k for k, mm in ix_a.items() if va in mm} &
                      {k for k, mm in ix_b.items() if vb in mm})
        if not keys:
            print(f"  {label}: [dati non ancora disponibili]")
            return None
        same = diff = 0
        det = []
        for k in keys:
            A, B = ix_a[k][va], ix_b[k][vb]
            eq = (A["correct"] == B["correct"] and A["wrong"] == B["wrong"]
                  and abs(A["coverage"] - B["coverage"]) < 1e-12)
            same += eq
            diff += (not eq)
            if not eq:
                det.append(f"{k[1]}_{k[2]}@{k[0]}: {A['correct']}/{A['wrong']} vs {B['correct']}/{B['wrong']}")
        print(f"  {label}: {same}/{len(keys)} configurazioni IDENTICHE, {diff} diverse")
        for d in det[:8]:
            print(f"      diversa: {d}")
        return same, len(keys)

    r1 = compare(a1ix, "R", p1ix, "P1", "α=1 vs α=0 (attese: TUTTE identiche)")
    if r1:
        print(f"      => P-a1 {'CONFERMATA' if r1[0] == r1[1] else 'FALSIFICATA'}"
              f" (il primo cluster non e' la posizione decisiva)")
    r2 = compare(a10ix, "R", a3ix, "R", "α=10 vs α=3 (attese: TUTTE identiche)")
    if r2:
        print(f"      => P-a2 {'CONFERMATA' if r2[0] == r2[1] else 'FALSIFICATA'}"
              f" (la posizione decisiva e' l'ULTIMA, non la prima)")

    # ---------------- H13: intra-cluster ----------------
    print("\n\n### H13 — riordino intra-cluster (Bridges, soglia 9, run 1–3)")
    cc = index(load(p("results_benchmark_C1C2.json")))
    if not cc:
        print("  [dati non ancora disponibili]")
    else:
        for v in ("C1", "C2"):
            s = summarize(delta(cc, ref, v))
            line(v, s)
        s1 = summarize(delta(cc, ref, "C1"))
        if s1:
            if s1["d_corr"] == 0 and s1["n_ident"] == s1["n"]:
                print("\n  => C1 NON cambia nulla: conferma il Caso 1 del brief")
                print("     (`getCandidatesForField` scorre TUTTE le RFD del cluster e tiene il minimo;")
                print("      l'unica uscita anticipata scrive il valore della tupla candidata,")
                print("      che non dipende da quale RFD l'ha attivata)")
                print("     => H13: il riordino intra-cluster NON e' una leva di qualita'")
            else:
                print(f"\n  => C1 cambia il risultato ({s1['d_corr']:+d} corrette): "
                      f"il Caso 2 e' confermato, l'ipotesi va rivista")
        # Wilcoxon su C1
        xs, ys = [], []
        for k, mm in cc.items():
            if "C1" in mm and k in ref:
                xs.append(mm["C1"]["correct"]); ys.append(ref[k]["correct"])
        if len(xs) >= 3:
            w = wilcoxon_signed_rank(xs, ys)
            print(f"  Wilcoxon C1 vs baseline: n={w['n']} W+={w['W+']:.1f} W-={w['W-']:.1f} "
                  f"p={fmt_p(w['p'])}")

    # ---------------- H11 / H12: generalizzazione ----------------
    print("\n\n### H11/H12 — generalizzazione su Glass e Restaurant")
    for tag, path, var in (("Glass α=0", "results_benchmark_P1_glass.json", "P1g"),
                           ("Glass α=3", "results_benchmark_P1reg_glass.json", "P1g_reg"),
                           ("Restaurant α=0", "results_benchmark_P1_restaurant.json", "P1r")):
        recs = load(p(path))
        if not recs:
            print(f"\n  --- {tag}: [dati non ancora disponibili] ---")
            continue
        ix = index(recs)
        # il baseline e' interno alla campagna (variante A), non quello di Bridges
        own = {k: mm["A"] for k, mm in ix.items() if "A" in mm}
        s = summarize(delta(ix, own, var))
        print(f"\n  --- {tag} (baseline interna) ---")
        line(var, s)
        if s:
            frac = 100 * s["n_pos"] / max(1, s["n"])
            print(f"      configurazioni con Δcorrette > 0: {s['n_pos']}/{s['n']} ({frac:.0f}%)")
            if tag.startswith("Glass α=0") or tag.startswith("Restaurant"):
                ok = s["d_corr"] > 0 and frac >= 70.0
                print(f"      => H11 {'CONFERMATA' if ok else 'FALSIFICATA'} "
                      f"(richiede Δcorr > 0 e ≥70% config positive)")


if __name__ == "__main__":
    main()
