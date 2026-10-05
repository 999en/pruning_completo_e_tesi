#!/usr/bin/env python3
"""
stats_effects.py — dimensione dell'effetto, IC bootstrap e correzione di Holm per i test
di Wilcoxon signed-rank gia' usati nel lavoro.

NON esegue RENUVER (nessun `java -jar`, nessuna chiamata a `benchmark.py` come programma):
legge soltanto JSON gia' presenti (`results/`, `.scratch/f5/`) e NON modifica nessun file
esistente. Scrive solo `results/stats_effects.json`.

Uso:
    python3 pruning/stats_effects.py

================================================================================
EFFECT SIZE — r rank-biserial per campioni appaiati
================================================================================
    r = (W+ − W−) / (W+ + W−)

dove W+ e' la somma dei ranghi delle differenze positive (Δ = B − A) e W− quella dei
ranghi delle differenze negative, calcolati dal test di Wilcoxon signed-rank di
`benchmark.wilcoxon_signed_rank` (ranghi medi in caso di pareggi). Proprieta':

  * il segno di r segue il segno dell'effetto: r > 0 ⇒ la variante B fa meglio della
    baseline A, r < 0 ⇒ peggio;
  * |r| ∈ [0, 1]; se W+ + W− == 0 (nessuna differenza non nulla) si riporta r = 0.0;
  * scala convenzionale (Cohen): |r| ≈ 0,1 piccolo, 0,3 medio, 0,5 grande.

================================================================================
FAMIGLIA PRIMARIA (correzione di Holm)
================================================================================
La famiglia primaria e' l'insieme dichiarato a priori dei test che rispondono alla
domanda principale del lavoro. Contiene 5 test (A5b e A99 sono lo stesso intervento a due
tarature; l'esperimento di ordinamento entra con i suoi due confronti decisivi):

  1. `a5b_bridges_correct`          A5b vs A su Bridges, griglia completa (50 config), `correct`
  2. `a5b_bridges_wrong`            A5b vs A su Bridges, griglia completa (50 config), `wrong`
  3. `a99_glass_correct`            A99 (α = 0,99) vs A su Glass, `correct`
                                    (Glass e Restaurant stanno in due file distinti, con dataset
                                    e soglie diversi: NON sono unibili in un solo test, quindi
                                    la famiglia include Glass e Restaurant resta un confronto
                                    separato, fuori dalla famiglia)
  4. `order_first_vs_A`             ordinamento `first-best` vs `A` (= `ord:orig`), `correct`
  5. `order_first_vs_randommean`    ordinamento `first-best` vs media dei 3 semi casuali, `correct`

Holm: si ordinano i p in senso crescente, il k-esimo (1-based) viene moltiplicato per
(m − k + 1); la monotonia e' imposta con p_corr_k = max(p_corr_{k−1}, valore corrente) e il
risultato e' troncato a 1.0. Gli altri confronti (controlli di regressione, repliche
per-seme, griglia A99 allargata) sono riportati con il solo p grezzo e NON entrano nella
famiglia: `p_holm` resta null.

================================================================================
APPAIAMENTO (identico a benchmark.aggregate(), righe ~637-690)
================================================================================
I record si raggruppano per chiave `(threshold, dataset, run)`; per ogni chiave si
confronta la variante di base `"A"` con la variante in esame. Si tengono solo le coppie in
cui ENTRAMBE hanno `rc == 0` e il valore della metrica non e' `None`. La differenza passata
al test e' Δ = B − A (variante meno baseline).

  * `n_coppie` = configurazioni appaiate valide (usato per mediana/media/IC);
  * `n_test`   = differenze NON nulle, cioe' l'`n` esatto del Wilcoxon (che scarta i
    pareggi). Nel lavoro i due numeri coincidono solo se nessuna coppia e' pari.

IC BOOTSTRAP: 10 000 ricampionamenti con reimmissione delle differenze appaiate, seme
fisso 20260923 (`random.Random(20260923)`), percentili 2,5% e 97,5% con interpolazione
lineare. Il punto di riferimento e' la mediana su TUTTE le `n_coppie` (non solo sulle
differenze non nulle), cosi' l'IC e' coerente con la mediana Δ stampata accanto. Se
`n_coppie < 3` l'IC e' `null`.
"""

from __future__ import annotations

import collections
import glob
import json
import math
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from benchmark import wilcoxon_signed_rank          # noqa: E402  (stessa implementazione del lavoro)
from benchmark import fmt_p                         # noqa: E402  (stessa formattazione dei p)
from paths import RESULTS, SCRATCH                  # noqa: E402

ROOT = os.path.dirname(RESULTS)
OUT_PATH = os.path.join(RESULTS, "stats_effects.json")

BOOTSTRAP_RESAMPLES = 10000
BOOTSTRAP_SEED = 20260923
CI_LOW_PCT, CI_HIGH_PCT = 2.5, 97.5
MIN_PAIRS_FOR_CI = 3
CHECK_DECIMALS = 4
CHECK_TOL = 5e-4

# ------------------------------------------------------------------------------------
# confronti
# ------------------------------------------------------------------------------------
# id -> (etichetta, file baseline, variante base, file variante, variante, metrica, famiglia)
A5B_BRIDGES_CANON = "results/results_benchmark.json"
A5B_BRIDGES_OLD = "results/results_benchmark_A5b.json"
A5B_BRIDGES_R345 = "results/results_A5b_bridges_r345.json"

# famiglia primaria, nell'ordine in cui e' dichiarata in testa al file
PRIMARY_FAMILY = [
    "a5b_bridges_correct",
    "a5b_bridges_wrong",
    "a99_glass_correct",
    "order_first_vs_A",
    "order_first_vs_randommean",
]

# controlli di regressione: (descrizione, id confronto, p pubblicato)
REGRESSION_CHECKS = [
    ("A5b su Bridges, metrica `correct`", "a5b_bridges_correct", 0.0053),
    ("ordinamento `first-best` vs `A`, metrica `correct`", "order_first_vs_A", 0.0016),
    ("ordinamento `last-best` vs `A`, metrica `correct`", "order_last_vs_A", 0.2702),
    ("ordinamento `first-best` vs media dei 3 casuali, metrica `correct`",
     "order_first_vs_randommean", 0.8878),
]

# varianti cercate per l'esperimento di ordinamento
ORDER_BASELINE = "ord:orig"
ORDER_FIRST = "ord:first-best"
ORDER_LAST = "ord:last-best"


# ------------------------------------------------------------------------------------
# I/O
# ------------------------------------------------------------------------------------
def resolve(rel):
    """Percorso assoluto a partire dalla radice del progetto."""
    return rel if os.path.isabs(rel) else os.path.join(ROOT, rel)


def load_json(rel):
    """Ritorna (records, errore). `errore` e' None quando il file e' stato letto."""
    path = resolve(rel)
    if not os.path.exists(path):
        return None, f"file assente: {rel}"
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:                                    # noqa: BLE001
        return None, f"JSON illeggibile ({rel}): {exc}"
    if not isinstance(data, list) or not data:
        return None, f"contenuto inatteso in {rel}: attesa una lista non vuota di record"
    return data, None


def variants_of(records):
    return sorted({str(r.get("variant")) for r in records if isinstance(r, dict)})


def find_order_file():
    """Individua il file dell'esperimento di ordinamento.

    Cerca prima la copia archiviata in `results/analisi/` (che rende l'esperimento
    riproducibile insieme agli altri risultati), poi il file del laboratorio
    (`.scratch/f5/exp_order.json`, scritto da `pruning/exp_order.py`), infine scandisce
    `results/` in cerca di un JSON con varianti `first-best`. Ritorna (path_relativo, records,
    errore).
    """
    candidates = [os.path.join(ROOT, "results", "analisi", "results_order_control.json"),
                  os.path.join(SCRATCH, "f5", "exp_order.json")]
    for path in candidates:
        rel = os.path.relpath(path, ROOT)
        recs, err = load_json(rel)
        if recs and any(ORDER_FIRST in str(r.get("variant")) for r in recs):
            return rel, recs, None
    for path in sorted(glob.glob(os.path.join(RESULTS, "*.json"))):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:                                       # noqa: BLE001
            continue
        if isinstance(data, list) and any(
                isinstance(r, dict) and ORDER_FIRST in str(r.get("variant")) for r in data):
            rel = os.path.relpath(path, ROOT)
            recs, err = load_json(rel)
            return rel, recs, err
    return None, None, ("nessun file con varianti `first-best` trovato: atteso "
                        "results/analisi/results_order_control.json")


# ------------------------------------------------------------------------------------
# appaiamento (identico a benchmark.aggregate)
# ------------------------------------------------------------------------------------
def index_by_key(records):
    """{(threshold, dataset, run): {variant: record}} — stessa chiave di aggregate()."""
    by = collections.defaultdict(dict)
    for r in records:
        by[(r["threshold"], r["dataset"], r["run"])][r["variant"]] = r
    return by


def collect_pairs(records, base_variant, variant, metric):
    """Coppie appaiate (B − A) con lo stesso criterio di benchmark.aggregate().

    Ritorna (keys, xs, ys) con xs = valori della variante B e ys = valori della baseline A.
    """
    by = index_by_key(records)
    keys, xs, ys = [], [], []
    for k in sorted(by):
        m = by[k]
        if base_variant not in m or variant not in m:
            continue
        if m[base_variant].get("rc") != 0 or m[variant].get("rc") != 0:
            continue
        a = m[base_variant].get(metric)
        b = m[variant].get(metric)
        if a is None or b is None:
            continue
        keys.append(k)
        xs.append(b)
        ys.append(a)
    return keys, xs, ys


def add_random_mean(records, seeds, metric, name="media-3-semi"):
    """Aggiunge record sintetici con la media dei semi casuali, per ogni chiave.

    Per ogni (threshold, dataset, run) in cui TUTTI i semi hanno `rc == 0` e la metrica non
    nulla, la media viene trattata come un unico campione appaiato (variante sintetica).
    """
    by = index_by_key(records)
    out = list(records)
    made = 0
    for k, m in by.items():
        vals = []
        for s in seeds:
            rec = m.get(s)
            if rec is None or rec.get("rc") != 0 or rec.get(metric) is None:
                break
            vals.append(rec[metric])
        else:
            if vals:
                out.append({"variant": name, "threshold": k[0], "dataset": k[1], "run": k[2],
                            "rc": 0, metric: statistics.mean(vals)})
                made += 1
    return out, made


# ------------------------------------------------------------------------------------
# statistica
# ------------------------------------------------------------------------------------
def holm_adjust(pvals):
    """Correzione di Holm: k-esimo p (1-based, ordinato) × (m − k + 1), monotonia, troncamento."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    prev = 0.0
    for k0, i in enumerate(order):
        val = min(1.0, max(prev, pvals[i] * (m - k0)))
        adj[i] = val
        prev = val
    return adj


def _percentile(sorted_vals, pct):
    """Percentile con interpolazione lineare (stessa convenzione di numpy)."""
    n = len(sorted_vals)
    if n == 0:
        return None
    if n == 1:
        return float(sorted_vals[0])
    pos = (n - 1) * (pct / 100.0)
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return float(sorted_vals[int(pos)])
    return float(sorted_vals[lo] * (hi - pos) + sorted_vals[hi] * (pos - lo))


def bootstrap_median_ci(diffs):
    """IC 95% bootstrap della mediana Δ: 10 000 ricampionamenti, seme 20260923."""
    n = len(diffs)
    if n < MIN_PAIRS_FOR_CI:
        return None
    rng = random.Random(BOOTSTRAP_SEED)
    meds = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        meds.append(statistics.median([diffs[rng.randrange(n)] for _ in range(n)]))
    meds.sort()
    return {
        "low": _percentile(meds, CI_LOW_PCT),
        "high": _percentile(meds, CI_HIGH_PCT),
        "level": 0.95,
        "percentiles": [CI_LOW_PCT, CI_HIGH_PCT],
        "n_resamples": BOOTSTRAP_RESAMPLES,
        "seed": BOOTSTRAP_SEED,
        "method": "percentile con interpolazione lineare sui ricampionamenti delle coppie",
    }


def short_method(method):
    m = (method or "").lower()
    if "esatta" in m:
        return "esatta"
    if "approssim" in m:
        return "approssimata"
    return method or "-"


def build_comparison(cid, label, records, base_variant, variant, metric, sources,
                     in_family=False, note=""):
    """Calcola il confronto appaiato B − A con Wilcoxon, effect size e IC bootstrap."""
    keys, xs, ys = collect_pairs(records, base_variant, variant, metric)
    n_pairs = len(xs)
    diffs = [b - a for b, a in zip(xs, ys)]     # Δ = B − A
    res = wilcoxon_signed_rank(xs, ys)          # d = B − A, come in benchmark.aggregate()
    wp = float(res.get("W+", 0.0) or 0.0)
    wm = float(res.get("W-", 0.0) or 0.0)
    denom = wp + wm
    r = (wp - wm) / denom if denom > 1e-12 else 0.0
    return {
        "id": cid,
        "label": label,
        "metric": metric,
        "base_variant": base_variant,
        "variant": variant,
        "sources": sources,
        "in_primary_family": bool(in_family),
        "n_pairs": n_pairs,
        "n_test": res.get("n", 0),
        "n_nonzero": res.get("n", 0),
        "median_delta": statistics.median(diffs) if diffs else None,
        "mean_delta": statistics.mean(diffs) if diffs else None,
        "median_delta_nonzero": res.get("median_diff"),
        "W_plus": wp,
        "W_minus": wm,
        "p": res.get("p", 1.0),
        "method": res.get("method", ""),
        "method_short": short_method(res.get("method", "")),
        "r_rank_biserial": r,
        "ci95_median_delta": bootstrap_median_ci(diffs),
        "p_holm": None,
        "note": note,
        "keys": [list(k) for k in keys],
    }


# ------------------------------------------------------------------------------------
# stampa
# ------------------------------------------------------------------------------------
def fmt_signed(v, nd=3):
    return "—" if v is None else f"{v:+.{nd}f}"


def fmt_w(v):
    return "—" if v is None else f"{v:.1f}"


def print_table(rows, title, show_holm=True):
    print(title)
    hdr = (f"{'confronto':<30}{'n_coppie':>9}{'n_test':>7}{'mediana Δ':>11}{'media Δ':>10}"
           f"{'r':>9}{'IC 95% mediana Δ':>21}{'p':>11}{'p_Holm':>10}  metodo")
    print(hdr)
    print("-" * len(hdr))
    for c in rows:
        ci = c["ci95_median_delta"]
        ci_s = f"[{ci['low']:+.2f}, {ci['high']:+.2f}]" if ci else "n/d (n<3)"
        if show_holm:
            ph = fmt_p(c["p_holm"]) if c["p_holm"] is not None else "—"
        else:
            ph = "—"
        print(f"{c['id']:<30}{c['n_pairs']:>9}{c['n_test']:>7}"
              f"{fmt_signed(c['median_delta']):>11}{fmt_signed(c['mean_delta']):>10}"
              f"{fmt_signed(c['r_rank_biserial']):>9}{ci_s:>21}"
              f"{fmt_p(c['p']):>11}{ph:>10}  {c['method_short']}")
    print()


def print_provenance(rows):
    print("--- provenienza (file e varianti usate) ---")
    for c in rows:
        src = " + ".join(f"{s['file']} [{s['variant']}]" for s in c["sources"])
        print(f"  {c['id']:<30} {src}")
    print()


def _public_view(c):
    """Copia del confronto senza l'elenco esteso delle chiavi (solo il conteggio)."""
    out = dict(c)
    out.pop("keys", None)
    out["n_keys"] = c["n_pairs"]
    return out


def autotest():
    """Verifiche interne delle regole dichiarate, su dati sintetici in memoria.

    Non legge e non scrive file: controlla la formula di r, il segno di Δ = B − A, il caso
    degenere W+ + W− == 0, la monotonia di Holm e la regola IC = null per n < 3.
    """
    out = []

    def chk(name, got, want):
        out.append({"regola": name, "esito": "PASS" if got == want else "FAIL",
                    "ottenuto": got, "atteso": want})

    def fake(pairs, metric="correct"):
        """Record sintetici: pairs = [(valore A, valore A5b), ...] sulle stesse chiavi."""
        recs = []
        for i, (a, b) in enumerate(pairs, start=1):
            for var, val in (("A", a), ("A5b", b)):
                recs.append({"threshold": 9, "dataset": "sintetico", "run": i,
                             "variant": var, "rc": 0, metric: val})
        return recs

    # Δ = B − A con segno positivo
    c = build_comparison("autotest_pos", "", fake([(1, 4), (2, 5), (3, 6)]), "A", "A5b", "correct", [])
    chk("Δ = B − A (mediana)", c["median_delta"], 3)
    chk("Δ = B − A (media)", c["mean_delta"], 3)
    chk("r = +1 con tutte le differenze positive", c["r_rank_biserial"], 1.0)
    chk("W+ = 6, W− = 0", (c["W_plus"], c["W_minus"]), (6.0, 0.0))

    # Δ = B − A con segno negativo
    c = build_comparison("autotest_neg", "", fake([(4, 1), (5, 2), (6, 3)]), "A", "A5b", "correct", [])
    chk("Δ = B − A (mediana negativa)", c["median_delta"], -3)
    chk("r = −1 con tutte le differenze negative", c["r_rank_biserial"], -1.0)

    # caso degenere: W+ + W− == 0 ⇒ r = 0.0
    c = build_comparison("autotest_zero", "", fake([(7, 7), (8, 8), (9, 9)]), "A", "A5b", "correct", [])
    chk("r = 0.0 se W+ + W− == 0", c["r_rank_biserial"], 0.0)
    chk("p = 1.0 se nessuna differenza non nulla", c["p"], 1.0)

    # Holm: monotonia e troncamento
    chk("holm([0.01, 0.02, 0.03])", [round(v, 6) for v in holm_adjust([0.01, 0.02, 0.03])],
        [0.03, 0.04, 0.04])
    chk("holm tronca a 1.0", [round(v, 6) for v in holm_adjust([0.6, 0.9])], [1.0, 1.0])

    # IC bootstrap: null sotto le 3 coppie, calcolabile da 3 in su
    chk("IC = null con n = 2", bootstrap_median_ci([1.0, 2.0]), None)
    chk("IC non null con n = 3", bootstrap_median_ci([1.0, 2.0, 3.0]) is not None, True)
    return out


# ------------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------------
def main():
    comparisons = []
    unavailable = []
    notes = []

    # ---------------------------------------------------------------- 1. A5b su Bridges
    # Griglia completa (50 configurazioni) riprodotta come in ablation_a5b.merge_e_wilcoxon():
    # baseline A da results_benchmark.json, A5b da results_benchmark_A5b.json (run 1-2)
    # + results_A5b_bridges_r345.json (run 3-5).
    canon, err_canon = load_json(A5B_BRIDGES_CANON)
    old, err_old = load_json(A5B_BRIDGES_OLD)
    new, err_new = load_json(A5B_BRIDGES_R345)
    if canon and old and new:
        canon_a = [r for r in canon if r.get("variant") == "A"]
        a5b_records = (canon_a
                       + [r for r in old if r.get("variant") == "A5b"]
                       + [r for r in new if r.get("variant") == "A5b"])
        sources = [
            {"file": A5B_BRIDGES_CANON, "variant": "A",
             "role": "baseline (griglia completa, run 1-5)"},
            {"file": A5B_BRIDGES_OLD, "variant": "A5b", "role": "variante (run 1-2)"},
            {"file": A5B_BRIDGES_R345, "variant": "A5b", "role": "variante (run 3-5)"},
        ]
        for metric in ("correct", "wrong"):
            comparisons.append(build_comparison(
                f"a5b_bridges_{metric}",
                f"A5b vs A su Bridges (griglia completa 50 config), metrica `{metric}`",
                a5b_records, "A", "A5b", metric, sources,
                in_family=(f"a5b_bridges_{metric}" in PRIMARY_FAMILY)))
    else:
        for lbl, e in (("baseline", err_canon), ("A5b run 1-2", err_old), ("A5b run 3-5", err_new)):
            if e:
                unavailable.append({"id": "a5b_bridges", "reason": f"{lbl}: {e}"})

    # Variante "solo file full": il file merged conserva le baseline A solo per i run 1-2.
    full, err_full = load_json("results/results_A5b_bridges_full.json")
    if full:
        for metric in ("correct", "wrong"):
            comparisons.append(build_comparison(
                f"a5b_bridges_full_only_{metric}",
                f"A5b vs A, solo `results_A5b_bridges_full.json` (run 1-2, 20 config), `{metric}`",
                full, "A", "A5b", metric,
                [{"file": "results/results_A5b_bridges_full.json", "variant": "A vs A5b",
                  "role": "confronto ristretto al solo file merged"}],
                note="20 sole coppie: il merge di ablation_a5b.py ha conservato dal file r345 "
                     "i soli record A5b, quindi le baseline A esistono solo per i run 1-2."))
    else:
        unavailable.append({"id": "a5b_bridges_full_only", "reason": err_full})

    # ---------------------------------------------------------------- 2. A5b con taratura conservativa (A99)
    a99_specs = [
        ("a99_glass_correct", "results/results_a99_glass_full.json", "Glass"),
        ("a99_restaurant_correct", "results/results_a99_restaurant_full.json", "Restaurant"),
    ]
    for cid, rel, lab in a99_specs:
        recs, err = load_json(rel)
        if not recs:
            unavailable.append({"id": cid, "reason": err})
            continue
        others = [v for v in variants_of(recs) if v != "A"]
        if not others:
            unavailable.append({"id": cid,
                                "reason": f"{rel}: nessuna variante diversa da A "
                                          f"(presenti: {', '.join(variants_of(recs))})"})
            continue
        var = others[0]
        comparisons.append(build_comparison(
            cid, f"{var} (α = 0,99) vs A su {lab}, metrica `correct`",
            recs, "A", var, "correct",
            [{"file": rel, "variant": "A vs " + var, "role": "taratura conservativa α = 0,99"}],
            in_family=(cid in PRIMARY_FAMILY),
            note="Glass e Restaurant stanno in due file distinti, con dataset e soglie "
                 "diversi: restano due confronti separati."))

    # Griglia allargata α = 0,99 (§13.6): 97 configurazioni su tre file.
    grid_files = ["results/results_a99_glass_grid.json",
                  "results/results_a99_restaurant_grid.json",
                  "results/results_a99_restaurant259_grid.json"]
    grid_records, grid_sources, grid_ok = [], [], True
    for rel in grid_files:
        recs, err = load_json(rel)
        if not recs:
            unavailable.append({"id": "a99_grid_pooled_correct", "reason": err})
            grid_ok = False
            continue
        grid_records.extend(recs)
        grid_sources.append({"file": rel, "variant": "A vs A99", "role": "griglia α = 0,99"})
    if grid_ok:
        comparisons.append(build_comparison(
            "a99_grid_pooled_correct",
            "A99 vs A, griglia α = 0,99 su Glass + Restaurant (97 config), `correct`",
            grid_records, "A", "A99", "correct", grid_sources,
            note="confronto esplorativo su dataset diversi (base del §13.6 del report), "
                 "NON in famiglia primaria."))

    # ---------------------------------------------------------------- 3. Esperimento di ordinamento
    order_rel, order_recs, order_err = find_order_file()
    if order_recs:
        ovars = variants_of(order_recs)
        randoms = sorted(v for v in ovars if "random" in v)
        order_src = [{"file": order_rel, "variant": f"A = {ORDER_BASELINE} vs varianti di ordine",
                      "role": "esperimento di ordinamento (5 dataset × run 1-3, soglia 9)"}]
        base = ORDER_BASELINE if ORDER_BASELINE in ovars else "A"
        if base != ORDER_BASELINE:
            notes.append(f"nel file di ordinamento non esiste `{ORDER_BASELINE}`: "
                         f"usata la variante `{base}` come baseline A.")
        else:
            notes.append(f"nel file di ordinamento la baseline `A` e' la variante "
                         f"`{ORDER_BASELINE}` (ordine originale del file, nessun riordino).")

        if ORDER_FIRST in ovars:
            comparisons.append(build_comparison(
                "order_first_vs_A", "ordinamento `first-best` vs `A` (= `ord:orig`), `correct`",
                order_recs, base, ORDER_FIRST, "correct", order_src,
                in_family=("order_first_vs_A" in PRIMARY_FAMILY)))
        else:
            unavailable.append({"id": "order_first_vs_A",
                                "reason": f"{order_rel}: variante `{ORDER_FIRST}` assente "
                                          f"(presenti: {', '.join(ovars)})"})
        if ORDER_LAST in ovars:
            comparisons.append(build_comparison(
                "order_last_vs_A", "ordinamento `last-best` vs `A` (= `ord:orig`), `correct`",
                order_recs, base, ORDER_LAST, "correct", order_src))
        else:
            unavailable.append({"id": "order_last_vs_A",
                                "reason": f"{order_rel}: variante `{ORDER_LAST}` assente"})

        if len(randoms) == 3 and ORDER_FIRST in ovars:
            with_mean, made = add_random_mean(order_recs, randoms, "correct")
            mean_src = order_src + [{"file": order_rel,
                                     "variant": "media di " + ", ".join(randoms),
                                     "role": f"{made} chiavi con tutti e 3 i semi validi"}]
            comparisons.append(build_comparison(
                "order_first_vs_randommean",
                "ordinamento `first-best` vs media dei 3 semi casuali, `correct`",
                with_mean, "media-3-semi", ORDER_FIRST, "correct", mean_src,
                in_family=("order_first_vs_randommean" in PRIMARY_FAMILY),
                note="per ogni chiave la media dei 3 semi e' un unico campione appaiato; "
                     "la differenza e' first-best − media."))
            comparisons.append(build_comparison(
                "order_randommean_vs_A",
                "ordinamento media dei 3 semi casuali vs `A` (= `ord:orig`), `correct`",
                with_mean, base, "media-3-semi", "correct", mean_src,
                note="controllo D2 del report."))
        elif randoms:
            unavailable.append({"id": "order_first_vs_randommean",
                                "reason": f"trovati {len(randoms)} semi casuali invece di 3 "
                                          f"({', '.join(randoms)})"})

        for s in randoms:
            tag = s.split(":")[-1]
            comparisons.append(build_comparison(
                f"order_random{tag}_vs_A",
                f"ordinamento `{s}` vs `A` (= `ord:orig`), `correct`",
                order_recs, base, s, "correct", order_src,
                note="controllo: singolo seme casuale (replica la tabella §12.6)."))
    else:
        for cid in ("order_first_vs_A", "order_last_vs_A", "order_first_vs_randommean"):
            unavailable.append({"id": cid, "reason": order_err})
        notes.append("esperimento di ordinamento NON trovato: atteso "
                     "results/analisi/results_order_control.json, rigenerabile con "
                     "`python3 pruning/exp_order.py` (vedi pruning/analyze_order.py).")

    # ---------------------------------------------------------------- 4. Ablazione su configurazioni comuni
    abl, err_abl = load_json(A5B_BRIDGES_OLD)
    if abl:
        avars = variants_of(abl)
        for want in ("exact-priority", "dom-sub-adaptive"):
            cid = "a5b_vs_" + want.replace("-", "_")
            present = want in avars
            if not present:
                unavailable.append({
                    "id": cid,
                    "reason": f"{A5B_BRIDGES_OLD}: variante `{want}` assente "
                              f"(presenti: {', '.join(avars)}); nessun file di results/ "
                              f"contiene insieme A5b e `{want}`, quindi non esistono "
                              f"configurazioni comuni da appaiare."})
            else:
                comparisons.append(build_comparison(
                    cid, f"ablazione A5b vs `{want}` su configurazioni comuni, `correct`",
                    abl, want, "A5b", "correct",
                    [{"file": A5B_BRIDGES_OLD, "variant": f"{want} vs A5b",
                      "role": "ablazione su configurazioni comuni"}]))
    else:
        unavailable.append({"id": "a5b_ablation", "reason": err_abl})

    # ---------------------------------------------------------------- Holm sulla famiglia primaria
    fam = [c for c in comparisons if c["id"] in PRIMARY_FAMILY]
    ordered_fam = sorted(fam, key=lambda c: PRIMARY_FAMILY.index(c["id"]))
    if ordered_fam:
        adj = holm_adjust([c["p"] for c in ordered_fam])
        for c, p in zip(ordered_fam, adj):
            c["p_holm"] = p
    missing_fam = [cid for cid in PRIMARY_FAMILY if cid not in {c["id"] for c in fam}]

    # ---------------------------------------------------------------- controlli di regressione
    by_id = {c["id"]: c for c in comparisons}
    checks = []
    for desc, cid, published in REGRESSION_CHECKS:
        c = by_id.get(cid)
        if c is None:
            checks.append({"descrizione": desc, "id": cid, "p_pubblicato": published,
                           "p_calcolato": None, "esito": "FAIL",
                           "dettaglio": "confronto non calcolabile"})
            continue
        rounded = round(c["p"], CHECK_DECIMALS)
        ok = abs(rounded - published) <= CHECK_TOL
        checks.append({
            "descrizione": desc, "id": cid, "p_pubblicato": published,
            "p_calcolato": c["p"], "p_calcolato_4decimali": rounded,
            "tolleranza": CHECK_TOL, "esito": "PASS" if ok else "FAIL",
            "dettaglio": (f"|{rounded:.4f} − {published:.4f}| = {abs(rounded - published):.2e} "
                          f"{'≤' if ok else '>'} {CHECK_TOL:.0e}")})

    # ---------------------------------------------------------------- autotest delle regole
    autos = autotest()

    # ---------------------------------------------------------------- note sulle discrepanze
    a5b_full = by_id.get("a5b_bridges_correct")
    a5b_only = by_id.get("a5b_bridges_full_only_correct")
    if a5b_full and a5b_only:
        notes.append(
            "il p pubblicato 0,0053 di A5b su Bridges (n = 39, W+ = 589) si riproduce solo "
            "sulla griglia completa di 50 configurazioni (baseline A da results_benchmark.json "
            "+ A5b da results_benchmark_A5b.json e results_A5b_bridges_r345.json, come fa "
            "ablation_a5b.merge_e_wilcoxon()): p = "
            f"{a5b_full['p']:.6f}. Il solo file results_A5b_bridges_full.json contiene le "
            "baseline A unicamente per i run 1-2 (20 coppie) e da' p = "
            f"{a5b_only['p']:.6f}: NON e' il numero pubblicato. Il file merged non ha le "
            "baseline dei run 3-5 perche' il merge conserva dal file r345 i soli record A5b.")
    a99 = by_id.get("a99_glass_correct")
    if a99 and a99["n_test"] == 0:
        notes.append(
            f"A99 su Glass (`correct`): {a99['n_pairs']} coppie, ma TUTTE le differenze sono "
            "nulle, quindi il Wilcoxon non ha differenze non nulle (n_test = 0, p = 1,0, r = 0,0). "
            "Non e' un errore di calcolo: su `correct` la taratura α = 0,99 e' identica al "
            "baseline in questo file. La griglia allargata §13.6 (97 configurazioni) ha una sola "
            "differenza non nulla.")
    if order_rel and not order_rel.startswith("results/"):
        notes.append(f"l'esperimento di ordinamento non e' in results/: il file usato dal lavoro "
                     f"e' `{order_rel}` (DEFAULT di pruning/analyze_order.py); le sue varianti "
                     f"sono {', '.join(variants_of(order_recs)) if order_recs else '—'}.")

    # ---------------------------------------------------------------- stampa
    print("=" * 132)
    print("DIMENSIONE DELL'EFFETTO, IC BOOTSTRAP E CORREZIONE DI HOLM SUI TEST DI WILCOXON")
    print("=" * 132)
    print(f"script            : pruning/stats_effects.py  (nessuna esecuzione di RENUVER)")
    print(f"appaiamento       : chiave (threshold, dataset, run), baseline A vs variante, "
          f"rc == 0 su entrambe, metrica non nulla, Δ = B − A")
    print(f"effect size       : r = (W+ − W−) / (W+ + W−)   (0,0 se W+ + W− == 0)")
    print(f"bootstrap         : {BOOTSTRAP_RESAMPLES} ricampionamenti delle coppie, seme "
          f"{BOOTSTRAP_SEED}, percentili {CI_LOW_PCT}%/{CI_HIGH_PCT}%, IC = null se n < "
          f"{MIN_PAIRS_FOR_CI}")
    print(f"famiglia primaria : {len(PRIMARY_FAMILY)} test → {', '.join(PRIMARY_FAMILY)}")
    print()

    print_table(ordered_fam, "FAMIGLIA PRIMARIA (p_Holm calcolato su questi "
                             f"{len(ordered_fam)} test)")
    extras = [c for c in comparisons if c["id"] not in PRIMARY_FAMILY]
    if extras:
        print_table(extras, "CONFRONTI SECONDARI ED ESPLORATIVI (p grezzo, nessuna correzione)",
                    show_holm=False)

    print("--- controlli di regressione sui p pubblicati nel lavoro ---")
    for c in checks:
        calc = "—" if c["p_calcolato"] is None else f"{c['p_calcolato']:.6f}"
        print(f"  [{c['esito']}] {c['descrizione']}")
        print(f"          pubblicato {c['p_pubblicato']:.4f} | calcolato {calc}")
        print(f"          {c['dettaglio']}")
    n_pass = sum(1 for c in checks if c["esito"] == "PASS")
    print(f"  → {n_pass}/{len(checks)} PASS")
    print()

    print("--- autotest delle regole dichiarate (dati sintetici in memoria) ---")
    for a in autos:
        print(f"  [{a['esito']}] {a['regola']}  → ottenuto {a['ottenuto']!r}, "
              f"atteso {a['atteso']!r}")
    n_auto = sum(1 for a in autos if a["esito"] == "PASS")
    print(f"  → {n_auto}/{len(autos)} PASS")
    print()

    print_provenance(ordered_fam + extras)

    if unavailable:
        print("--- confronti NON calcolabili (file o varianti assenti) ---")
        for u in unavailable:
            print(f"  {u['id']:<34} {u['reason']}")
        print()

    if missing_fam:
        print("--- ATTENZIONE: test della famiglia primaria non calcolabili ---")
        for cid in missing_fam:
            print(f"  {cid}")
        print()

    if notes:
        print("--- note e discrepanze ---")
        for n in notes:
            print(f"  * {n}")
        print()

    # ---------------------------------------------------------------- JSON
    payload = {
        "meta": {
            "script": "pruning/stats_effects.py",
            "comando": "python3 pruning/stats_effects.py",
            "esecuzione_renuver": False,
            "metrica_differenza": "Δ = B − A (variante meno baseline)",
            "appaiamento": "chiave (threshold, dataset, run); baseline A vs variante; entrambe "
                           "rc == 0; metrica non None — identico a benchmark.aggregate()",
            "effect_size": "r rank-biserial appaiato = (W+ − W−) / (W+ + W−); 0.0 se "
                           "W+ + W− == 0",
            "bootstrap": {"n_resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED,
                          "percentili": [CI_LOW_PCT, CI_HIGH_PCT],
                          "riferimento": "mediana su tutte le n_coppie",
                          "ic_null_se": f"n_coppie < {MIN_PAIRS_FOR_CI}"},
            "holm": {"famiglia_primaria": PRIMARY_FAMILY,
                     "procedura": "p ordinati crescenti; k-esimo (1-based) × (m − k + 1); "
                                  "monotonia p_corr_k = max(p_corr_{k−1}, valore); "
                                  "troncamento a 1.0"},
            "nomi_campi": {"n_coppie": "n_pairs", "n_test": "differenze non nulle (n del Wilcoxon)",
                           "mediana_delta": "median_delta (tutte le coppie)",
                           "mediana_delta_nonzero": "median_delta_nonzero (convenzione "
                                                    "benchmark.wilcoxon_signed_rank)"},
        },
        "famiglia_primaria": {
            "ordine": PRIMARY_FAMILY,
            "m": len(ordered_fam),
            "p_grezzi": {c["id"]: c["p"] for c in ordered_fam},
            "p_holm": {c["id"]: c["p_holm"] for c in ordered_fam},
            "test_non_calcolabili": missing_fam,
        },
        "comparisons": [_public_view(c) for c in comparisons],
        "regression_checks": checks,
        "autotest": autos,
        "unavailable": unavailable,
        "note": notes,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, ensure_ascii=False)
    print(f"[stats_effects] scritto {os.path.relpath(OUT_PATH, ROOT)} "
          f"({len(comparisons)} confronti, {len(checks)} controlli, "
          f"{len(unavailable)} non calcolabili)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
