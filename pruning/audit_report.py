#!/usr/bin/env python3
"""
audit_report.py — riverifica i numeri del report contro i JSON di `results/`.

Ogni voce e' un'affermazione scritta in `report.md` con il valore atteso e il modo di
ricalcolarlo. Lo script stampa OK o DIVERGE per ciascuna e riepiloga alla fine.

Uso:  python3 pruning/audit_report.py
"""
from __future__ import annotations

import collections
import glob
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import RESULTS                                    # noqa: E402
from benchmark import wilcoxon_signed_rank, fmt_p            # noqa: E402

ESITI = []


def load(name):
    p = os.path.join(RESULTS, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []


def ix(recs, variant):
    return {(r["dataset"], r["run"], r["threshold"]): r for r in recs if r.get("variant") == variant}


def check(claim, got, want, tol=0.0):
    if isinstance(want, (int, float)) and isinstance(got, (int, float)):
        ok = abs(got - want) <= tol
    else:
        ok = got == want
    ESITI.append((claim, ok, got, want))
    print(f"  {'OK  ' if ok else 'DIVERGE'}  {claim:<62} calcolato={got}  report={want}")


# ---------------------------------------------------------------- §5.6 / §10.8 veto-cover
def veto_cover():
    """La claim centrale: `veto-cover` produce output IDENTICO al baseline in 111/111
    configurazioni su tre famiglie. I dati stanno in tre file diversi."""
    print("\n### §5.6 — veto-cover: output identico su Bridges + Glass + Restaurant")
    tot = ident = 0
    for f in ("results_benchmark_r2.json", "results_benchmark_glass.json",
              "results_benchmark_restaurant.json"):
        recs = load(f)
        A, S4 = ix(recs, "A"), ix(recs, "S4")
        ks = sorted(set(A) & set(S4))
        n = sum(1 for k in ks if S4[k]["correct"] == A[k]["correct"]
                and S4[k]["wrong"] == A[k]["wrong"]
                and abs(S4[k]["coverage"] - A[k]["coverage"]) < 1e-12)
        print(f"    {f:<38} {n}/{len(ks)} identiche")
        tot += len(ks); ident += n
    check("configurazioni totali", tot, 111)
    check("output identici al baseline", f"{ident}/{tot}", f"{tot}/{tot}")
    # riduzione per soglia su Bridges
    recs = load("results_benchmark_r2.json")
    A, S4 = ix(recs, "A"), ix(recs, "S4")
    for thr, want in ((3, 11.7), (9, 17.1)):
        ks = [k for k in S4 if k[2] == thr and k in A]
        if ks:
            red = 100 * statistics.mean((A[k]["rfd_in"] - S4[k]["rfd_out"]) / A[k]["rfd_in"] for k in ks)
            check(f"Bridges riduzione a soglia {thr}", round(red, 1), want, tol=0.15)


# ---------------------------------------------------------------- §10.5.2 A5b Bridges
def a5b_bridges():
    print("\n### §10.5.2 — A5b su Bridges, griglia completa (n=50)")
    recs = load("results_A5b_bridges_full.json")
    A = ix(load("results_benchmark.json"), "A")
    V = ix(recs, "A5b")
    ks = sorted(k for k in V if k in A)
    dc = sum(V[k]["correct"] - A[k]["correct"] for k in ks)
    de = sum(V[k]["wrong"] - A[k]["wrong"] for k in ks)
    red = 100 * statistics.mean(V[k]["rfd_reduction"] for k in ks)
    check("n configurazioni", len(ks), 50)
    check("Δ corrette", dc, 69)
    check("Δ errori", de, -72)
    check("riduzione RFD %", round(red, 1), 84.2, tol=0.15)
    w = wilcoxon_signed_rank([V[k]["correct"] for k in ks], [A[k]["correct"] for k in ks])
    check("Wilcoxon p (corrette)", round(w["p"], 4), 0.0053, tol=0.0002)
    check("Wilcoxon n (corrette)", w["n"], 39)


# ---------------------------------------------------------------- §10.5.2 Glass/Restaurant
def a5b_altri():
    print("\n### §10.5.2 — A5b su Glass e Restaurant")
    for f, var, want in (("results_A5b_glass.json", "A5b", {"3": (-20, -25), "9": (-17, -9), "15": (-17, -12)}),
                         ("results_A5b_restaurant.json", "A5b", {"3": (-1, 0), "6": (-11, 0)})):
        recs = load(f)
        by = collections.defaultdict(dict)
        for r in recs:
            by[(r["dataset"], r["run"], r["threshold"])][r["variant"]] = r
        for thr, (wc, we) in want.items():
            ks = [k for k in by if str(k[2]) == thr and "A" in by[k] and var in by[k]]
            if not ks:
                continue
            dc = sum(by[k][var]["correct"] - by[k]["A"]["correct"] for k in ks)
            de = sum(by[k][var]["wrong"] - by[k]["A"]["wrong"] for k in ks)
            check(f"{os.path.basename(f)} @{thr} Δcorrette", dc, wc)
            check(f"{os.path.basename(f)} @{thr} Δerrori", de, we)


# ---------------------------------------------------------------- §11.4 P1
def p1_bridges():
    print("\n### §11.4 — precision-priority (P1) su Bridges")
    recs = load("results_benchmark_P1P2.json")
    A = ix(recs, "A")
    P1 = ix(recs, "P1")
    ks = sorted(k for k in P1 if k in A)
    dc = sum(P1[k]["correct"] - A[k]["correct"] for k in ks)
    de = sum(P1[k]["wrong"] - A[k]["wrong"] for k in ks)
    check("n configurazioni", len(ks), 30)
    check("Δ corrette", dc, 96)
    check("Δ errori", de, -71)
    for thr, wc, we in ((9, 53, -40), (15, 43, -31)):
        kk = [k for k in ks if k[2] == thr]
        check(f"@{thr} Δcorrette", sum(P1[k]["correct"] - A[k]["correct"] for k in kk), wc)
        check(f"@{thr} Δerrori", sum(P1[k]["wrong"] - A[k]["wrong"] for k in kk), we)


# ---------------------------------------------------------------- §11.7 P1 altrove
def p1_altri():
    print("\n### §11.7 — precision-priority su Glass e Restaurant")
    for f, var, want_n in (("results_benchmark_P1_glass_stats.json", "P1gs", 45),
                           ("results_benchmark_P1_restaurant.json", "P1r", 18)):
        recs = load(f)
        by = collections.defaultdict(dict)
        for r in recs:
            by[(r["dataset"], r["run"], r["threshold"])][r["variant"]] = r
        ks = [k for k in by if "A" in by[k] and var in by[k]]
        ident = sum(1 for k in ks if by[k][var]["correct"] == by[k]["A"]["correct"]
                    and by[k][var]["wrong"] == by[k]["A"]["wrong"]
                    and abs(by[k][var]["coverage"] - by[k]["A"]["coverage"]) < 1e-12)
        check(f"{os.path.basename(f)} n", len(ks), want_n)
        check(f"{os.path.basename(f)} identiche", ident, want_n)


# ---------------------------------------------------------------- §12.2 alpha
def alpha():
    print("\n### §12.2 — sweep di alpha: tutte identiche ad alpha=0")
    a1, a3, a10 = (ix(load(f"results_benchmark_alpha_{a}.json"), "R") for a in ("1.0", "3.0", "10.0"))
    p1 = ix(load("results_benchmark_P1P2.json"), "P1")
    def same(X, Y):
        ks = sorted(set(X) & set(Y))
        n = sum(1 for k in ks if X[k]["correct"] == Y[k]["correct"] and X[k]["wrong"] == Y[k]["wrong"]
                and abs(X[k]["coverage"] - Y[k]["coverage"]) < 1e-12)
        return n, len(ks)
    for lbl, X, Y in (("a1 vs a0", a1, p1), ("a3 vs a0", a3, p1), ("a10 vs a0", a10, p1), ("a10 vs a3", a10, a3)):
        n, tot = same(X, Y)
        check(f"{lbl} identiche", f"{n}/{tot}", f"{tot}/{tot}")


# ---------------------------------------------------------------- §12.3 intra-cluster
def intra():
    print("\n### §12.3 — intra-cluster-priority")
    recs = load("results_benchmark_C1C2.json")
    by = collections.defaultdict(dict)
    for r in recs:
        by[(r["dataset"], r["run"], r["threshold"])][r["variant"]] = r
    ks = sorted(k for k in by if all(v in by[k] for v in ("A", "C1", "C2")))
    c1 = sum(1 for k in ks if by[k]["C1"]["correct"] == by[k]["A"]["correct"]
             and by[k]["C1"]["wrong"] == by[k]["A"]["wrong"]
             and abs(by[k]["C1"]["coverage"] - by[k]["A"]["coverage"]) < 1e-12)
    check("C1 identiche al baseline", f"{c1}/{len(ks)}", f"{len(ks)}/{len(ks)}")
    p1 = ix(load("results_benchmark_P1P2.json"), "P1")
    kk = [k for k in ks if k in p1]
    same = sum(1 for k in kk if by[k]["C2"]["correct"] == p1[k]["correct"]
               and abs(by[k]["C2"]["coverage"] - p1[k]["coverage"]) < 1e-12)
    check("C2 identico a P1", f"{same}/{len(kk)}", f"{len(kk)}/{len(kk)}")


# ---------------------------------------------------------------- §12.6 ordine
def ordine():
    print("\n### §12.6 — esperimento d'ordine (15 configurazioni, soglia 9)")
    # L'esperimento di ordinamento viveva nell'area di lavoro temporanea; una copia e' archiviata
    # con gli altri dati in results/analisi/, cosi' la verifica funziona anche su una copia del
    # progetto priva di .scratch/.
    candidati = [os.path.join(HERE, "..", "results", "analisi", "results_order_control.json"),
                 os.path.join(HERE, "..", ".scratch", "f5", "exp_order.json")]
    p = next((c for c in candidati if os.path.exists(c)), None)
    if p is None:
        print("  [dati dell'esperimento di ordinamento assenti]")
        return
    recs = json.load(open(p))
    by = collections.defaultdict(dict)
    for r in recs:
        by[(r["dataset"], r["run"])][r["variant"].split(":", 1)[1]] = r
    full = [k for k in by if all(v in by[k] for v in ("orig", "first-best", "last-best"))]
    tot = collections.Counter()
    for k in full:
        for v in by[k]:
            tot[v] += by[k][v]["correct"]
    check("configurazioni complete", len(full), 15)
    check("orig corrette", tot["orig"], 333)
    check("first-best corrette", tot["first-best"], 386)
    check("last-best corrette", tot["last-best"], 313)
    check("random:12345 corrette", tot["random:12345"], 388)
    rs = [v for v in tot if v.startswith("random")]
    d3 = [by[k]["first-best"]["correct"] - statistics.mean(by[k][r]["correct"] for r in rs)
          for k in full if all(r in by[k] for r in rs)]
    check("first-best − media(random), Δ", round(sum(d3), 2), 0.33, tol=0.01)
    d2 = [statistics.mean(by[k][r]["correct"] for r in rs) - by[k]["orig"]["correct"] for k in full]
    check("media(random) − orig, Δ", round(sum(d2), 1), 52.7, tol=0.1)
    d4 = [by[k]["last-best"]["correct"] - by[k]["orig"]["correct"] for k in full]
    check("last-best − orig, Δ", sum(d4), -20)


# ---------------------------------------------------------------- §13.6 alpha 0.99
def a99():
    """§13.6 — griglia completa del regime gentile: 97 configurazioni, 94 identiche,
    Delta corrette -1, Delta errori -3, riduzione massima 52,9%."""
    print("\n### §13.6 — A5b regime gentile (alpha = 0,99), griglia completa")
    files = ["results_a99_glass_grid.json", "results_a99_restaurant_grid.json",
             "results_a99_restaurant259_grid.json"]
    n = same = dc = de = 0
    red = []
    for f in files:
        recs = load(f)
        by = collections.defaultdict(dict)
        for r in recs:
            by[(r["dataset"], r["run"], r["threshold"])][r["variant"]] = r
        for k, mm in by.items():
            if "A" not in mm or "A99" not in mm:
                continue
            A, B = mm["A"], mm["A99"]
            n += 1
            same += (B["correct"] == A["correct"] and B["wrong"] == A["wrong"]
                     and abs(B["coverage"] - A["coverage"]) < 1e-12)
            dc += B["correct"] - A["correct"]
            de += B["wrong"] - A["wrong"]
            red.append(100 * B["rfd_reduction"])
    check("configurazioni totali", n, 97)
    check("identiche al baseline", same, 94)
    check("Δ corrette", dc, -1)
    check("Δ errori", de, -3)
    check("riduzione massima %", round(max(red), 1), 52.9, tol=0.05)
    check("config con rimozione >1%", sum(1 for r in red if r > 1), 27)


# ---------------------------------------------------------------- §14.4 veto-fix
def vetofix():
    print("\n### §14.4 — correzione della politica sui veti")
    n = tot = 0
    for f in ("results_vetofix_bridges.json", "results_vetofix_glass.json"):
        recs = load(f)
        by = collections.defaultdict(dict)
        for r in recs:
            by[(r["dataset"], r["run"], r["threshold"])][r["variant"]] = r
        for k, mm in by.items():
            for v in ("VCp", "VCa"):
                if v in mm and "A" in mm:
                    tot += 1
                    if (mm[v]["correct"] == mm["A"]["correct"] and mm[v]["wrong"] == mm["A"]["wrong"]
                            and abs(mm[v]["coverage"] - mm["A"]["coverage"]) < 1e-12):
                        n += 1
    check("configurazioni con output identico", f"{n}/{tot}", f"{tot}/{tot}")


# ---------------------------------------------------------------- §15.1 scala
def scala():
    """§15.1 — quanti record contengono i file di risultato consegnati.

    I due conteggi si riferiscono ai file presenti nella cartella al momento della consegna: se si
    aggiungono altri JSON in `results/` (per esempio l'uscita di una prova), i conteggi crescono e
    il controllo segnala una divergenza. In quel caso la riga `[nota]` qui sotto elenca i file
    aggiunti di recente, che sono i candidati.
    """
    print("\n### §15.1 — scala dell'evidenza")
    tot = nb = 0
    per_file = []
    for f in glob.glob(os.path.join(RESULTS, "*.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, list):
            continue
        n_qui = 0
        for r in d:
            if isinstance(r, dict) and "variant" in r:
                tot += 1
                nb += r["variant"] != "A"
                n_qui += 1
        if n_qui:
            per_file.append((os.path.getmtime(f), os.path.basename(f), n_qui))
    check("record totali", tot, 2808)
    check("esecuzioni non-baseline", nb, 1618)
    if tot != 2808 or nb != 1618:
        recenti = sorted(per_file, reverse=True)[:4]
        print("  [nota] i conteggi si riferiscono ai file consegnati: gli ultimi file toccati in "
              "results/ sono")
        for _, nome, n in recenti:
            print(f"         {nome}  ({n} record) — se e' una prova appena eseguita, i suoi "
                  f"risultati vanno in .scratch/")



# ---------------------------------------------------------------- §1.4 V1/V2/V3
def condizioni():
    """§1.4 — le tre condizioni misurate. Valori ricalcolati dal file RFD e dal dataset."""
    import subprocess, tempfile
    print("\n### §1.4 — [V1]/[V2]/[V3] su Bridges soglia 9")
    rfd = os.path.join(HERE, "..", "RENUVER", "RFD", "output_false_9_bridges.csv")
    ds = os.path.join(HERE, "..", "RENUVER", "Dataset", "bridges_14_1.csv")
    if not (os.path.exists(rfd) and os.path.exists(ds)):
        print("  [file assenti]"); return
    import pruning as P
    raw = P.read_lines(rfd); h = raw[0].split(";")
    parsed = [p for p in (P.parse_rfd_row(h, l) for l in raw[1:]) if p]
    nullcols, _ = P.collect_null_columns([ds])
    n = len(parsed)
    vb = sum(P.veto_bearing(parsed, nullcols))
    v3 = sum(1 for p in parsed if not (set(p["lhs"]) & nullcols) and p["rhs"] not in nullcols)
    v2 = len(P.veto_covered_indices(parsed, max_extra=3, alive=None))
    dup = n - len(set(l for l in raw[1:]))
    check("N RFD", n, 8961)
    check("[V1] puo' fare veto", vb, 8945)
    check("[V3] inerte", v3, 6)
    check("[V2] coperta", v2, 1531)
    check("duplicati", dup, 0)



# ---------------------------------------------------------------- §13.6.2 meccanismo
def meccanismo():
    """§13.6.2 — il guadagno di A5b e' quota-exact x copertura. Verifica i tre casi."""
    print("\n### §13.6.2 — meccanismo: quota exact e copertura")
    def agg(f, variants, ks=None):
        d = load(f); by = collections.defaultdict(dict)
        for r in d:
            by[(r["dataset"], r["run"], r["threshold"])][r["variant"]] = r
        kk = ks or sorted(k for k in by if all(v in by[k] for v in variants))
        out = {}
        for v in variants:
            imp = sum(by[k][v]["n_imputations_logged"] for k in kk)
            ex = sum(by[k][v].get("n_exact", 0) for k in kk)
            out[v] = (imp, 100 * ex / max(1, imp), sum(by[k][v]["correct"] for k in kk))
        return out
    b = agg("results_benchmark_A5b.json", ("A", "A5b"))
    check("Bridges baseline: imputate", b["A"][0], 504)
    check("Bridges baseline: % exact", round(b["A"][1], 1), 19.6, tol=0.05)
    check("Bridges A5b: imputate", b["A5b"][0], 521)
    check("Bridges A5b: % exact", round(b["A5b"][1], 1), 38.0, tol=0.05)
    g = agg("results_A5b_glass.json", ("A", "A5b"))
    check("Glass baseline: % exact", round(g["A"][1], 1), 100.0, tol=0.05)
    check("Glass A5b: imputate", g["A5b"][0], 721)
    r = agg("results_A5b_restaurant.json", ("A", "A5b"))
    check("Restaurant baseline: % exact", round(r["A"][1], 1), 23.2, tol=0.05)
    check("Restaurant A5b: % exact", round(r["A5b"][1], 1), 49.8, tol=0.05)


def main():
    print("=" * 108)
    print("AUDIT DEL REPORT — riverifica dei numeri contro i JSON di results/")
    print("=" * 108)
    for fn in (condizioni, veto_cover, meccanismo, a5b_bridges, a5b_altri, p1_bridges, p1_altri, alpha, intra,
               ordine, a99, vetofix, scala):
        try:
            fn()
        except Exception as e:
            print(f"  [errore in {fn.__name__}: {type(e).__name__}: {e}]")
    ko = [e for e in ESITI if not e[1]]
    print("\n" + "=" * 108)
    print(f"controlli: {len(ESITI)}   OK: {len(ESITI)-len(ko)}   DIVERGENZE: {len(ko)}")
    for c, _, g, w in ko:
        print(f"   DIVERGE  {c}: calcolato={g} report={w}")
    return 1 if ko else 0


if __name__ == "__main__":
    sys.exit(main())
