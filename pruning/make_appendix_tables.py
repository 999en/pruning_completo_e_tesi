"""Genera le tabelle complete dell'appendice B della tesi.

Legge i file di risultato delle campagne in `results/` e scrive un file LaTeX che
l'appendice B include con \\input. La cartella della tesi non fa parte di questo pacchetto:
se non e' presente, l'output va in `results/analisi/B-tables-generated.tex`
(percorso forzabile con `--out`).

Uso:  python3 pruning/make_appendix_tables.py [--out file.tex]
Nessuna esecuzione di RENUVER: il calcolo lavora solo sui JSON gia' presenti.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
TES = os.path.join(ROOT, "Tesi Triennale", "_chapters")
OUT = os.path.join(TES, "B-tables-generated.tex")


def default_out():
    """Dove scrivere: nella tesi se c'e', altrimenti in `results/analisi/`."""
    return OUT if os.path.isdir(TES) else os.path.join(RES, "analisi", "B-tables-generated.tex")


def load(name):
    with open(os.path.join(RES, name), encoding="utf-8") as fh:
        return json.load(fh)


def key(r):
    return (r["threshold"], r["dataset"], r["run"])


def by_variant(records, variant):
    return {key(r): r for r in records if r.get("variant") == variant and r.get("rc") == 0}


def pairs(base_records, var_records, base="A", var="A5b"):
    b, v = by_variant(base_records, base), by_variant(var_records, var)
    out = []
    for k in sorted(set(b) & set(v)):
        out.append((k, b[k], v[k]))
    return out


def fmt(x, nd=1):
    return f"{x:.{nd}f}".replace(".", ",")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Tabelle dell'appendice B (nessuna esecuzione di RENUVER).")
    ap.add_argument("--out", default=None, help="file .tex di output (default: %s)" % default_out())
    args = ap.parse_args(argv)
    out = args.out or default_out()
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

    lines = []
    add = lines.append

    # ---------------------------------------------------------------- Bridges A5b
    base = load("results_benchmark.json")
    a5b = load("results_benchmark_A5b.json") + load("results_A5b_bridges_r345.json")
    rows = pairs(base, a5b, "A", "A5b")
    tot_dc = sum(v["correct"] - b["correct"] for _, b, v in rows)
    tot_dw = sum(v["wrong"] - b["wrong"] for _, b, v in rows)
    add("% FILE GENERATO da pruning/make_appendix_tables.py — non modificare a mano.")
    add("\\footnotesize")
    add("\\begin{longtable}{@{}llrrrrrr@{}}")
    add("\\caption{Campagna principale su Bridges, configurazione per configurazione. "
        "``RFD'' sono le regole in ingresso e in uscita dalla potatura, ``rid.''\\ la riduzione "
        "percentuale, $\\Delta$~corr.\\ e $\\Delta$~err.\\ le variazioni rispetto alla medesima "
        "configurazione non potata.}\\label{tab:app-bridges}\\\\")
    add("\\toprule")
    add("dataset & soglia & run & RFD in & RFD out & rid.\\ (\\si{\\percent}) & "
        "$\\Delta$ corr. & $\\Delta$ err. \\\\")
    add("\\midrule")
    add("\\endfirsthead")
    add("\\toprule")
    add("dataset & soglia & run & RFD in & RFD out & rid.\\ (\\si{\\percent}) & "
        "$\\Delta$ corr. & $\\Delta$ err. \\\\")
    add("\\midrule")
    add("\\endhead")
    add("\\midrule")
    add("\\multicolumn{5}{r}{totale} & & \\textbf{%+d} & \\textbf{%+d} \\\\" % (tot_dc, tot_dw))
    add("\\bottomrule")
    add("\\endlastfoot")
    for (thr, ds, run), b, v in rows:
        add("%s & %d & %d & %d & %d & %s & %+d & %+d \\\\"
            % (ds.replace("_", "\\_"), thr, run, b["rfd_in"], v["rfd_out"],
               fmt(100 * v["rfd_reduction"]),
               v["correct"] - b["correct"], v["wrong"] - b["wrong"]))
    add("\\end{longtable}")
    add("")

    # ---------------------------------------------------------------- ablazione
    a4 = load("results_benchmark_A4.json")
    a2 = load("results_benchmark_A2_0.85.json")
    b = by_variant(base, "A")
    a4v, a2v, a5bv = by_variant(a4, "A4"), by_variant(a2, "A2"), by_variant(a5b, "A5b")
    common = sorted(set(b) & set(a4v) & set(a2v) & set(a5bv))
    abl = []
    for k in common:
        dc = {n: m[k]["correct"] - b[k]["correct"] for n, m in
              (("prio", a4v), ("adattiva", a2v), ("A5b", a5bv))}
        abl.append((k, dc))
    somma = sum(d["prio"] + d["adattiva"] for _, d in abl)
    comb = sum(d["A5b"] for _, d in abl)
    add("\\begin{table}[htbp]")
    add("\\centering")
    add("\\caption{Ablazione di \\str{A5b} sulle %d configurazioni comuni ai quattro bracci. "
        "``priorità'' è il solo riordino, ``adattiva'' la sola potatura adattiva; la somma delle "
        "due variazioni è %+d, la variazione della combinazione è %+d.}"
        % (len(abl), somma, comb))
    add("\\label{tab:app-ablation}")
    add("\\footnotesize")
    add("\\begin{tabular}{@{}llrrrr@{}}")
    add("\\toprule")
    add("dataset & soglia & $\\Delta$ priorità & $\\Delta$ adattiva & somma & $\\Delta$ \\str{A5b} \\\\")
    add("\\midrule")
    for k, d in abl:
        add("%s & %d & %+d & %+d & %+d & %+d \\\\"
            % (k[1].replace("_", "\\_"), k[0], d["prio"], d["adattiva"],
               d["prio"] + d["adattiva"], d["A5b"]))
    add("\\midrule")
    add("\\multicolumn{2}{r}{totale} & %+d & %+d & %+d & %+d \\\\"
        % (sum(d["prio"] for _, d in abl), sum(d["adattiva"] for _, d in abl), somma, comb))
    add("\\bottomrule")
    add("\\end{tabular}")
    add("\\end{table}")
    add("")

    # ---------------------------------------------------------------- a99
    grid = (load("results_a99_glass_grid.json") + load("results_a99_restaurant_grid.json")
            + load("results_a99_restaurant259_grid.json"))
    gb, gv = by_variant(grid, "A"), by_variant(grid, "A99")
    keys = sorted(set(gb) & set(gv))
    dc = sum(gv[k]["correct"] - gb[k]["correct"] for k in keys)
    dw = sum(gv[k]["wrong"] - gb[k]["wrong"] for k in keys)
    red = [100 * gv[k]["rfd_reduction"] for k in keys]
    add("\\scriptsize")
    add("\\begin{longtable}{@{}llrrrr@{}}")
    add("\\caption{Taratura conservativa della potatura aggressiva ($\\alpha = 0{,}99$) sulle %d "
        "configurazioni con baseline disponibile. Riduzione mediana %s\\si{\\percent}, massima "
        "%s\\si{\\percent}; variazioni complessive $\\Delta$ corr.\\ %+d, $\\Delta$ err.\\ %+d.}"
        % (len(keys), fmt(sorted(red)[len(red) // 2]), fmt(max(red)), dc, dw))
    add("\\label{tab:app-a99}\\\\")
    add("\\toprule")
    add("dataset & soglia & run & rid.\\ (\\si{\\percent}) & $\\Delta$ corr. & $\\Delta$ err. \\\\")
    add("\\midrule")
    add("\\endfirsthead")
    add("\\toprule")
    add("dataset & soglia & run & rid.\\ (\\si{\\percent}) & $\\Delta$ corr. & $\\Delta$ err. \\\\")
    add("\\midrule")
    add("\\endhead")
    add("\\bottomrule")
    add("\\endlastfoot")
    for k in keys:
        add("%s & %d & %d & %s & %+d & %+d \\\\"
            % (k[1].replace("_", "\\_"), k[0], k[2], fmt(100 * gv[k]["rfd_reduction"]),
               gv[k]["correct"] - gb[k]["correct"], gv[k]["wrong"] - gb[k]["wrong"]))
    add("\\end{longtable}")

    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print("scritto", out)
    print("Bridges A5b: %d configurazioni, somma dCorrect %+d, somma dWrong %+d" % (len(rows), tot_dc, tot_dw))
    print("Ablazione: %d configurazioni comuni; somma %+d, combinazione %+d, sinergia %+d"
          % (len(abl), somma, comb, comb - somma))
    print("a99: %d configurazioni; dCorrect %+d, dWrong %+d, riduzione mediana %s%%, massima %s%%"
          % (len(keys), dc, dw, fmt(sorted(red)[len(red) // 2]), fmt(max(red))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
