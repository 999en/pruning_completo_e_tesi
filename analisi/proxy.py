#!/usr/bin/env python3
"""
proxy.py — Proxy offline della qualità di una strategia di pruning, senza rieseguire RENUVER.

IDEA
----
Nei `Results/` dell'archivio ogni imputazione registra la RFD che ha *vinto* (quella con il
punteggio minimo per il candidato scelto). Se una strategia di pruning rimuove quella RFD, quella
cella rischia di non essere piu' imputata allo stesso modo.

Definiamo, per una configurazione (soglia, dataset, run) e una maschera di pruning:

    retention_correct = PESO delle imputazioni CORRETTE la cui RFD vincente sopravvive
                        / PESO totale delle imputazioni corrette
    retention_wrong   = idem per le imputazioni SBAGLIATE

Questi due numeri forniscono un profilo atteso:
  * retention_correct alta  -> poche imputazioni buone a rischio
  * retention_wrong alta    -> gli errori preesistenti restano (non vengono "curati" dal pruning)

Il proxy e' PESSIMISTA (se la vincente sparisce la cella potrebbe comunque essere imputata bene da
un'altra RFD) ma dovrebbe essere MONOTONO rispetto all'effetto reale, quindi utile per ORDINARE le
strategie prima di spendere ore di esecuzioni.

VALIDAZIONE
-----------
Il modulo confronta le previsioni con i delta realmente misurati nel benchmark (S1/S2/S3) e riporta
la correlazione di Spearman fra retention_correct e Δcorrette osservato.
"""
import os
import sys
import json
import math
import collections
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))       # .../analisi
ROOT = os.path.dirname(HERE)                            # radice del progetto
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "pruning"))       # per `import pruning`

from prune import read_rfd, parse_row, read_dataset, is_null          # noqa: E402
from strategies_v2 import mask_veto_cover, mask_dom_sub_strict        # noqa: E402
import pruning as P                                                    # noqa: E402

REN = os.path.join(ROOT, "RENUVER")
RESULTS_PARSED = os.path.join(ROOT, "results", "analisi", "results_parsed.json")
BENCH = os.path.join(ROOT, "results", "results_benchmark.json")


# --------------------------------------------------------------------------- dati baseline
def load_baseline_winners():
    """-> { (thr, base) : [ (firma_rfd, correct_bool), ... ] }"""
    recs = json.load(open(RESULTS_PARSED))
    out = collections.defaultdict(list)
    for r in recs:
        if not str(r["base"]).startswith("bridges"):
            continue
        if not r.get("known"):
            continue
        if r.get("imputed") in (None, "?", ""):
            continue
        sig = (r["rhs"], round(float(r["rhs_thr"]), 9),
               tuple(sorted((c, round(float(t), 9)) for c, t in r["lhs"])))
        out[(r["thr"], r["base"])].append((sig, bool(r["correct"])))
    return out


def load_masks(thr, dataset_file, train_stats):
    """Costruisce le maschere delle strategie candidate per un dato file RFD."""
    header, hline, raw = read_rfd(os.path.join(REN, "RFD", f"output_false_{thr}_bridges.csv"))
    parsed, raws = [], []
    for l in raw:
        p = parse_row(header, l)
        if p is not None:
            parsed.append(p)
            raws.append(l)

    attrs, dsrows = read_dataset(os.path.join(REN, "Dataset", dataset_file))
    nullcells = collections.defaultdict(list)
    for ri, row in enumerate(dsrows):
        for a in attrs:
            if is_null(row[a]):
                nullcells[a].append(ri)

    masks = {}
    def add(name, m):
        masks[name] = m[0] if isinstance(m, tuple) else m

    add("coverage", P.mask_coverage(parsed, nullcells, dsrows, set(attrs)))
    add("inert", P.mask_inert(parsed, nullcols=set(nullcells)))
    add("duplicates", P.mask_duplicates(parsed, raws))
    add("dom-exact", P.mask_dom_exact(parsed))
    for me in (1, 2, 3):
        add(f"dom-sub(me={me})", P.mask_dom_sub(parsed, max_extra=me))
    add("veto-cover", mask_veto_cover(parsed, 3))
    add("dom-sub-strict", mask_dom_sub_strict(parsed))
    add("used", P.mask_used(parsed, train_stats))
    add("used-acc", mask_used_acc_light(parsed, train_stats))
    add("dom-sub+used", [a and b for a, b in zip(P.mask_dom_sub(parsed, 1), P.mask_used(parsed, train_stats))])
    add("dom-sub|used", [a or b for a, b in zip(P.mask_dom_sub(parsed, 1), P.mask_used(parsed, train_stats))])
    add("dom-sub+used+coverage",
        [a and b and c for a, b, c in zip(P.mask_dom_sub(parsed, 1), P.mask_used(parsed, train_stats),
                                          P.mask_coverage(parsed, nullcells, dsrows, set(attrs)))])
    for cap in (4, 5):
        add(f"lhs-cap({cap})", P.mask_lhs_cap(parsed, cap))
    return parsed, masks


def mask_used_acc_light(parsed, train_stats, min_acc=0.5):
    """used + filtro di accuratezza (tiene le RFD con <2 usi per prudenza)."""
    if not train_stats:
        return [True] * len(parsed)
    keep = []
    for p in parsed:
        k = (p["rhs"], round(float(p["rhs_thr"]), 9),
             tuple(sorted((c, round(float(t), 9)) for c, t in p["lhs"].items())))
        st = train_stats.get(k)
        if not st or st["uses"] == 0:
            keep.append(False)
        elif st["uses"] < 2:
            keep.append(True)
        else:
            keep.append(st["correct"] / st["uses"] >= min_acc)
    return keep


def signature(p):
    return (p["rhs"], round(float(p["rhs_thr"]), 9),
            tuple(sorted((c, round(float(t), 9)) for c, t in p["lhs"].items())))


# --------------------------------------------------------------------------- proxy
def retention(parsed, mask, winners):
    """Ritorna (ret_correct, ret_wrong, n_correct, n_wrong) sulle imputazioni baseline."""
    kept = {signature(p) for p, k in zip(parsed, mask) if k}
    nc = nw = kc = kw = 0
    for sig, ok in winners:
        if ok:
            nc += 1
            kc += 1 if sig in kept else 0
        else:
            nw += 1
            kw += 1 if sig in kept else 0
    return (kc / nc if nc else None, kw / nw if nw else None, nc, nw)


def spearman(x, y):
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    if len(pairs) < 4:
        return None
    xs = [a for a, _ in pairs]
    ys = [b for _, b in pairs]
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and abs(v[order[j + 1]] - v[order[i]]) < 1e-12:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else None


# --------------------------------------------------------------------------- main
def main():
    winners = load_baseline_winners()
    thresholds = [3, 6, 9, 12, 15]
    levels = ["bridges_14", "bridges_28", "bridges_42", "bridges_56", "bridges_70"]

    print("=" * 112)
    print("PROXY OFFLINE: ritenzione delle RFD VINCENTI del baseline")
    print("=" * 112)

    rows = []
    for thr in thresholds:
        for level in levels:
            # statistiche di training in leave-one-out (esclude tutte le run dello stesso livello)
            stats = P.load_training_stats(os.path.join(REN, "Results"), os.path.join(REN, "Populated"),
                                          "bridges", exclude=level)
            for run in range(1, 6):
                ds = f"{level}_{run}"
                key = (thr, ds + ".csv")
                if key not in winners:
                    continue
                if not os.path.exists(os.path.join(REN, "Dataset", ds + ".csv")):
                    # versione leggera del pacchetto: senza dataset il proxy non e' calcolabile
                    continue
                parsed, masks = load_masks(thr, ds + ".csv", stats)
                for name, mask in masks.items():
                    rc, rw, nc, nw = retention(parsed, mask, winners[key])
                    n_kept = sum(1 for k in mask if k)
                    rows.append(dict(threshold=thr, level=level, run=run, dataset=ds, strategy=name,
                                     reduction=1 - n_kept / max(1, len(parsed)),
                                     ret_correct=rc, ret_wrong=rw, n_correct=nc, n_wrong=nw))

    # ---- aggregato per strategia -------------------------------------------------
    agg = collections.defaultdict(list)
    for r in rows:
        agg[r["strategy"]].append(r)
    print(f"\n{'strategia':<26}{'rid.% media':>12}{'ret. corrette':>15}{'ret. errate':>13}"
          f"{'proxy prec.':>13}{'score':>9}")
    print("-" * 112)
    scored = []
    for name, rs in agg.items():
        red = statistics.mean(x["reduction"] for x in rs)
        rc = statistics.mean([x["ret_correct"] for x in rs if x["ret_correct"] is not None])
        rw = statistics.mean([x["ret_wrong"] for x in rs if x["ret_wrong"] is not None])
        tot_c = sum(x["n_correct"] for x in rs)
        kc = sum((x["ret_correct"] or 0) * x["n_correct"] for x in rs)
        kw = sum((x["ret_wrong"] or 0) * x["n_wrong"] for x in rs)
        pp = kc / (kc + kw) if (kc + kw) else float("nan")
        # score: premia la riduzione e la ritenzione delle corrette
        score = red * rc if rc == rc else 0.0
        scored.append((score, name, red, rc, rw, pp))
    for score, name, red, rc, rw, pp in sorted(scored, reverse=True):
        print(f"{name:<26}{100*red:>11.1f}%{rc:>15.3f}{rw:>13.3f}{pp:>13.3f}{score:>9.3f}")

    # ---- validazione contro il benchmark reale ----------------------------------
    if os.path.exists(BENCH):
        bench = json.load(open(BENCH))
        by = collections.defaultdict(dict)
        for b in bench:
            by[(b["threshold"], b["dataset"], b["run"])][b["variant"]] = b
        mapping = {"S1": "dom-sub(me=1)", "S2": "used", "S3": None}
        print("\n" + "=" * 112)
        print("VALIDAZIONE DEL PROXY contro i Δ misurati nel benchmark")
        print("=" * 112)
        print(f"{'variante':>9}{'strategia proxy':>20}{'n':>5}{'ret_correct':>13}"
              f"{'Δcorrette oss.':>16}{'Δcov oss.':>12}{'ρ Spearman':>12}")
        print("-" * 112)
        for var, sname in mapping.items():
            if sname is None:
                continue
            proxy = {(r["threshold"], r["dataset"]): r for r in rows if r["strategy"] == sname}
            xs, ys = [], []
            for (thr, lvl, run), m in by.items():
                k = (thr, f"{lvl}_{run}")
                if k not in proxy or var not in m or "A" not in m:
                    continue
                if m["A"].get("rc") != 0 or m[var].get("rc") != 0:
                    continue
                xs.append(proxy[k]["ret_correct"])
                ys.append(m[var]["correct"] - m["A"]["correct"])
            if len(xs) < 4:
                continue
            rho = spearman(xs, ys)
            print(f"{var:>9}{sname:>20}{len(xs):>5}{statistics.mean(xs):>13.3f}"
                  f"{statistics.mean(ys):>16.2f}{'':>12}{(f'{rho:+.3f}' if rho is not None else 'n/d'):>12}")

    # L'artefatto della fase e' results/analisi/proxy.json: quel file NON viene sovrascritto,
    # perche' e' stato prodotto da una revisione precedente del potatore e differisce, in una
    # parte delle righe, negli ultimi decimali della riduzione (la classifica non cambia).
    # Il risultato di questa esecuzione finisce nell'area di lavoro.
    if not rows:
        print("\n[nessun risultato] i dataset di RENUVER/Dataset/ non sono presenti: il proxy "
              "offline\n                 richiede il dataset per calcolare le colonne nulle; "
              "nessun file scritto.")
        return 0
    out = os.path.join(ROOT, ".scratch", "analisi", "proxy_rigenerato.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1)
    print(f"\n[scritto {os.path.relpath(out, ROOT)}  ({len(rows)} righe)]")
    print("[nota] l'artefatto archiviato e' results/analisi/proxy.json: e' stato prodotto nella fase "
          "con una\n       revisione precedente del potatore, quindi alcune righe differiscono negli "
          "ultimi decimali\n       della riduzione; l'ordinamento delle strategie resta quello.")


if __name__ == "__main__":
    main()
