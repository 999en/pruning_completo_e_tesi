#!/usr/bin/env python3
"""
benchmark.py — Confronto A/B fra RENUVER originale e RENUVER + Semantic Pruning.

Per ogni configurazione (dataset, soglia, run) esegue:
    A) RENUVER con il file RFD originale
    B) RENUVER con il file RFD ridotto da pruning.py

e misura: accuratezza, coverage, precision, F1, RMSE/MAE (attributi numerici),
numero di RFD distinte effettivamente usate, tempo di preprocessing, tempo di
imputazione, riduzione del set di RFD.

Al termine aggrega e applica il test di Wilcoxon signed-rank sui confronti appaiati.

    python3 benchmark.py \
        --datasets "bridges_14,bridges_28,bridges_42,bridges_56,bridges_70" \
        --runs 1,2,3,4,5 \
        --thresholds 3,6,9,12,15 \
        --variants "S1=dom-sub:allow,S2=used:allow,S3=hybrid:allow" \
        --out results_benchmark.json

NOTE METODOLOGICHE
------------------
* Il baseline A per la tipizzazione con `B` e' letto dall'archivio originale (Logs/Results/
  Populated). La riproducibilita' e' stata verificata: rieseguendo il JAR su 4 configurazioni
  campione (soglie 3, 6, 9, 15) gli output sono byte-identici agli originali.
* Le RFD usate in B sono generate con pruning.py e dipendono dal run (leave-one-out per le
  strategie data-driven): il file potato viene rigenerato per ogni run.
* I confronti sono appaiati per (dataset, soglia, run).
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import os
import re
import shlex
import shutil
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import (ROOT, RENUVER as REN, RESULTS as RESULTS_DIR, LAB, PRUNED_DIR,
                   BENCH_JSON, ensure_dirs)
NULLS = {"?", ""}

COLTYPES_B = "D,C,D,D,D,D,D,B,B,D,D,D,D"      # quello usato dallo script pubblicato
COLTYPES_D = "D,C,D,D,D,D,D,D,D,D,D,D,D"      # fix: nessuna colonna marcata B

# Famiglie di dataset: prefisso -> (tipizzazione, prefisso file RFD).
# La tipizzazione e' quella dello script pubblicato per Bridges; per gli altri dataset
# si usa "tutto D" perche' non esiste uno script di riferimento.
FAMILIES = {
    "bridges":    ("D,C,D,D,D,D,D,B,B,D,D,D,D", "bridges"),
    "restaurant": ("D,D,D,D,D,D",               "restaurant"),
    "glass":      ("D,D,D,D,D,D,D,D,D,D,D",     "glass"),
    "nursery":    ("D,D,D,D,D,D,D,D,D",         "nursery"),
    "Physician_Compare_National": ("D," * 12 + "D", "Physician_Compare_National"),
    # Varianti "remodulate": stesso schema del dataset completo ma poche centinaia di righe,
    # pensate per la sperimentazione. Ogni livello di rumore ha il proprio file RFD, quindi
    # serve una voce per livello (il prefisso deve combaciare con il nome del file RFD).
    # ATTENZIONE: i dataset NON remodulati hanno 103 592 righe e ~100 000 celle nulle ciascuno:
    # una singola esecuzione di RENUVER richiederebbe giorni. Solo i remodulati sono trattabili.
    "Physician_Compare_National_remodulated_0.005_13": ("D," * 12 + "D", "Physician_Compare_National_remodulated_0.005"),
    "Physician_Compare_National_remodulated_0.01_27":  ("D," * 12 + "D", "Physician_Compare_National_remodulated_0.01"),
    "Physician_Compare_National_remodulated_0.05_135": ("D," * 12 + "D", "Physician_Compare_National_remodulated_0.05"),
    "Physician_Compare_National_remodulated_0.1_269":  ("D," * 12 + "D", "Physician_Compare_National_remodulated_0.1"),
}


def resolve_family(ds_name):
    """Deduce la famiglia dal nome del dataset (prefisso piu' lungo che combacia)."""
    best = None
    for fam in FAMILIES:
        if ds_name.startswith(fam) and (best is None or len(fam) > len(best)):
            best = fam
    return best


def coltypes_for(fam, mode):
    if fam is None:
        return COLTYPES_B if mode == "B" else COLTYPES_D
    ct = FAMILIES[fam][0]
    if mode == "D" and fam == "bridges":
        return COLTYPES_D
    return ct


def rfd_file_for(fam, thr):
    pref = FAMILIES.get(fam, (None, "bridges"))[1]
    return f"output_false_{thr}_{pref}.csv"


# =====================================================================================
# utility
# =====================================================================================
def ensure_lab():
    for d in ("Dataset", "RFD", "TupleIniziali", "Results", "Populated", "Logs"):
        os.makedirs(os.path.join(LAB, d), exist_ok=True)
    jar = os.path.join(LAB, "RENUVER_EDBT.jar")
    if not os.path.exists(jar):
        shutil.copy(os.path.join(REN, "RENUVER_EDBT.jar"), jar)


def clear_out():
    for d in ("Results", "Populated", "Logs"):
        p = os.path.join(LAB, d)
        if os.path.isdir(p):
            for f in os.listdir(p):
                fp = os.path.join(p, f)
                if os.path.isfile(fp):
                    os.remove(fp)


def read_populated(path):
    """-> lista di (riga, attributo, valore_reale, valore_imputato)."""
    rows = []
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return rows
    for i, line in enumerate(open(path, encoding="utf-8", errors="replace")):
        q = line.rstrip("\n").split(";")
        if i == 0 and q and q[0].lower().startswith("riga"):
            continue
        if len(q) >= 4:
            rows.append((q[0].strip(), q[1].strip(), q[2].strip(), q[3].strip()))
    return rows


def is_number(s):
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


def values_equal(a, b):
    if a == b:
        return True
    if is_number(a) and is_number(b):
        return abs(float(a) - float(b)) < 1e-9
    return False


def read_log(path):
    out = {}
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return out
    num = lambda s: int(re.search(r"(-?\d+)", s).group(1)) if re.search(r"(-?\d+)", s) else None
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if line.startswith("#RFD after remove:"):
            out["rfd_after"] = num(line.split(":", 1)[1])
        elif line.startswith("Time required for pre"):
            out["pre_ms"] = num(line.split(":", 1)[1])
        elif line.startswith("Total execution time"):
            out["exec_ms"] = num(line)
        elif line.startswith("#Null cells:"):
            out["null_cells"] = num(line.split(":", 1)[1])
        elif line.startswith("#Cells not filled:"):
            out["not_filled"] = num(line.split(":", 1)[1])
        elif line.startswith("Memory"):
            out["mem_mb"] = num(line.split(":", 1)[1])
    return out


RHS_PAT = re.compile(r"\[([^\[\]]*)\]\s*->\s*\(([^)]+)\)_([-\d.]+)\s*;(.*)$")


def read_results(path):
    """-> (n_imputazioni, set di firme RFD distinte usate, n_exact)."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return 0, set(), 0
    n = 0
    sigs = set()
    n_exact = 0
    for line in open(path, encoding="utf-8", errors="replace"):
        m = RHS_PAT.search(line)
        if not m:
            continue
        n += 1
        if m.group(4).strip() == "exact":
            n_exact += 1
        try:
            lhs = tuple(sorted((c.strip(), round(float(t), 9))
                               for c, t in re.findall(r"\(([^)]+)\)_([-\d.]+)", m.group(1))))
        except ValueError:
            continue
        sigs.add((m.group(2).strip(), round(float(m.group(3)), 9), lhs))
    return n, sigs, n_exact


def levenshtein(a, b):
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def text_similarity(a, b):
    """Similarita' normalizzata di Levenshtein in [0,1]: 1 - dist / max(len)."""
    if a == b:
        return 1.0
    m = max(len(a), len(b))
    if m == 0:
        return 1.0
    return 1.0 - levenshtein(a, b) / m


def metrics_from(pop_rows, log, results_path, rfd_in, rfd_out, wall_s=None, text_thr=None):
    """Calcola tutte le metriche di un singolo run.

    `text_thr` (0..1): se valorizzato, per le celle non numeriche conta come CORRETTA anche
    un'imputazione con similarita' di Levenshtein normalizzata >= text_thr. Serve per i
    dataset testuali (Restaurant) dove l'exact match e' troppo severo."""
    total = len(pop_rows)
    imputed = [r for r in pop_rows if r[3] not in NULLS]
    correct = [r for r in imputed if values_equal(r[2], r[3])]
    correct_txt = correct
    if text_thr is not None:
        correct_txt = []
        for r in imputed:
            if values_equal(r[2], r[3]):
                correct_txt.append(r)
            elif not (is_number(r[2]) and is_number(r[3])):
                if text_similarity(r[2], r[3]) >= text_thr:
                    correct_txt.append(r)
    wrong = len(imputed) - len(correct)
    n_imp, sigs, n_exact = read_results(results_path)

    # RMSE / MAE sugli attributi numerici (solo celle con valore reale numerico)
    errs = []
    by_attr = collections.defaultdict(list)
    for _, attr, gt, im in imputed:
        if is_number(gt) and is_number(im):
            e = float(im) - float(gt)
            errs.append(e)
            by_attr[attr].append(e)
    rmse = math.sqrt(sum(e * e for e in errs) / len(errs)) if errs else None
    mae = sum(abs(e) for e in errs) / len(errs) if errs else None
    # RMSE/MAE normalizzati per attributo (range dei valori reali) -> comparabili fra attributi
    nr = []
    for attr, es in by_attr.items():
        gts = [float(gt) for _, a, gt, im in imputed if a == attr and is_number(gt) and is_number(im)]
        rng = (max(gts) - min(gts)) if len(gts) > 1 else 0.0
        if rng > 0:
            nr += [e / rng for e in es]
    rmse_n = math.sqrt(sum(e * e for e in nr) / len(nr)) if nr else None
    mae_n = sum(abs(e) for e in nr) / len(nr) if nr else None

    P = len(correct) / len(imputed) if imputed else None
    C = len(imputed) / total if total else 0.0
    F1 = (2 * P * C / (P + C)) if (P is not None and P + C > 0) else None
    return {
        "missing_total": total,
        "imputed": len(imputed),
        "correct": len(correct),
        "wrong": wrong,
        "not_imputed": total - len(imputed),
        "precision": P,
        "coverage": C,
        "accuracy": len(correct) / total if total else 0.0,
        "f1": F1,
        "correct_text": len(correct_txt),
        "accuracy_text": len(correct_txt) / total if total else 0.0,
        "precision_text": len(correct_txt) / len(imputed) if imputed else None,
        "text_thr": text_thr,
        "rmse": rmse, "mae": mae, "rmse_norm": rmse_n, "mae_norm": mae_n,
        "n_imputations_logged": n_imp,
        "n_rfd_used": len(sigs),
        "n_exact": n_exact,
        "rfd_in": rfd_in,
        "rfd_out": rfd_out,
        "rfd_reduction": (rfd_in - rfd_out) / rfd_in if rfd_in else 0.0,
        "pre_ms": log.get("pre_ms"),
        "exec_ms": log.get("exec_ms"),
        "total_ms": (log.get("pre_ms") or 0) + (log.get("exec_ms") or 0),
        "null_cells": log.get("null_cells"),
        "not_filled": log.get("not_filled"),
        "mem_mb": log.get("mem_mb"),
        "wall_s": wall_s,
    }


# =====================================================================================
# esecuzione
# =====================================================================================
def run_renuver(ds_file, thr, rfd_file, coltypes, maxthr=None, timeout=7200):
    """Esegue RENUVER. `thr` e' la soglia del file RFD (usata per la strategia di pruning);
    `maxthr` e' il valore passato come args[4] (default = thr). RENUVER usa args[4] sia come
    soglia di accettazione del punteggio sia per nominare i file di output, quindi va passato
    anche ai percorsi."""
    mt = thr if maxthr is None else maxthr
    clear_out()
    t0 = time.time()
    try:
        p = subprocess.run(["java", "-jar", "RENUVER_EDBT.jar", coltypes, ds_file, ";",
                            rfd_file, str(mt), "0"],
                           cwd=LAB, capture_output=True, text=True, timeout=timeout)
        rc, err = p.returncode, p.stderr
    except subprocess.TimeoutExpired:
        rc, err = -9, "TIMEOUT"
    wall = time.time() - t0
    pop = os.path.join(LAB, "Populated", f"output_{ds_file}_{mt}H0.csv")
    log = read_log(os.path.join(LAB, "Logs", f"log_{ds_file}_{mt}H0.txt"))
    res = os.path.join(LAB, "Results", f"output_{ds_file}_{mt}H0.txt")
    return dict(rc=rc, err=(err.strip().splitlines() or [""])[0][:200], wall_s=round(wall, 2),
                pop_rows=read_populated(pop), log=log, results_path=res, maxthr=mt)


def file_digest(path):
    """MD5 del contenuto, per accorgersi se due braccia leggono lo stesso file."""
    import hashlib
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def count_rfd_lines(path):
    if not os.path.exists(path):
        return 0
    return max(0, sum(1 for l in open(path, encoding="utf-8", errors="replace") if l.strip()) - 1)


def keep_outputs(tag, ds_file, mt, pop_dir, res_dir):
    """Copia `Populated/` e `Results/` del run appena eseguito in cartelle dedicate.

    Serve all'analisi dell'impatto dei veti (§10.4): la LAB e' condivisa e ogni run
    sovrascrive gli output del precedente, quindi senza ritenzione non e' possibile
    confrontare cella per cella il baseline con un run potato. Il nome del file copiato
    e' `<tag>__<nome originale>`, dove `tag` e' la variante (A, VC, SB4, ...).
    """
    if not pop_dir and not res_dir:
        return
    for src_dir, dst_dir, name in (
            (os.path.join(LAB, "Populated"), pop_dir, f"output_{ds_file}_{mt}H0.csv"),
            (os.path.join(LAB, "Results"), res_dir, f"output_{ds_file}_{mt}H0.txt")):
        if not dst_dir:
            continue
        src = os.path.join(src_dir, name)
        if os.path.exists(src):
            os.makedirs(dst_dir, exist_ok=True)
            shutil.copy(src, os.path.join(dst_dir, f"{tag}__{name}"))


def make_pruned(strategy, veto_policy, threshold, ds_file, ds_name, run, out_path,
                family="bridges", dataset_dir=None, extra=None, maxthr=None):
    """Invoca pruning.py per generare il file ridotto specifico di questo run.

    `maxthr` va passato SEMPRE: e' il valore di args[4] con cui RENUVER eseguira' davvero il run,
    e `score-argmin` lo usa come soglia di accettazione del punteggio per calcolare l'argmin.
    Senza, pruning.py lo deriva dalla massima soglia RHS del file, che NON coincide con la soglia
    del run su Bridges (30/90/130 contro 3/9/15), Glass @15 (12 contro 15) e Restaurant @3
    (2 contro 3). La discrepanza si e' rivelata numericamente inerte — su tutti e 8 i casi il
    set di rimozione e' identico — ma la decisione di pruning va presa allo stesso punto di
    funzionamento del run, non a uno diverso.
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    rfd_name = rfd_file_for(family, threshold)
    strategy = strategy.replace("+", ",")      # piu' strategie in pipeline: "a+b" -> "a,b"
    cmd = [sys.executable, os.path.join(HERE, "pruning.py"),
           "--rfd", os.path.join(REN, "RFD", rfd_name),
           "--dataset", os.path.join(dataset_dir or os.path.join(REN, "Dataset"), ds_file),
           "--output", out_path,
           "--strategy", strategy,
           "--veto-policy", veto_policy,
           "--maxthr", str(threshold if maxthr is None else maxthr),
           "--results-dir", os.path.join(REN, "Results"),
           "--populated-dir", os.path.join(REN, "Populated"),
           "--family", family,
           "--exclude", re.escape(ds_name)]
    if extra:
        cmd += shlex.split(extra)
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"pruning.py fallito ({p.returncode}): {p.stderr[:400]}")
    return count_rfd_lines(out_path)


# =====================================================================================
# statistica: Wilcoxon signed-rank
# =====================================================================================
def wilcoxon_signed_rank(x, y):
    """Test di Wilcoxon signed-rank a due code sui campioni appaiati x, y.
    Ritorna dict con n, W+, W-, statistica, p-value, metodo, mediane."""
    d = [a - b for a, b in zip(x, y) if a is not None and b is not None]
    d = [v for v in d if abs(v) > 1e-12]
    n = len(d)
    if n == 0:
        return {"n": 0, "p": 1.0, "method": "nessuna differenza non nulla", "W+": 0, "W-": 0}
    absd = [abs(v) for v in d]
    order = sorted(range(n), key=lambda i: absd[i])
    ranks = [0.0] * n
    i = 0
    ties = []
    while i < n:
        j = i
        while j + 1 < n and abs(absd[order[j + 1]] - absd[order[i]]) < 1e-12:
            j += 1
        avg = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        ties.append(j - i + 1)
        i = j + 1
    Wp = sum(ranks[i] for i in range(n) if d[i] > 0)
    Wm = sum(ranks[i] for i in range(n) if d[i] < 0)
    has_ties = any(t > 1 for t in ties)

    # esatta (senza ranghi medi) se possibile
    if not has_ties and n <= 25:
        maxs = n * (n + 1) // 2
        cnt = [0] * (maxs + 1)
        cnt[0] = 1
        for r in range(1, n + 1):
            for s in range(maxs, r - 1, -1):
                if cnt[s - r]:
                    cnt[s] += cnt[s - r]
        tot = 2 ** n
        obs = int(round(Wp))
        p = sum(c for s, c in enumerate(cnt) if s <= obs or s >= maxs - obs) / tot
        return {"n": n, "W+": Wp, "W-": Wm, "p": min(1.0, p), "method": "esatta",
                "median_diff": statistics.median(d)}

    mean = n * (n + 1) / 4.0
    var = n * (n + 1) * (2 * n + 1) / 24.0
    for t in ties:
        var -= (t ** 3 - t) / 48.0
    if var <= 0:
        return {"n": n, "W+": Wp, "W-": Wm, "p": 1.0, "method": "varianza nulla",
                "median_diff": statistics.median(d)}
    z = (Wp - mean)
    z -= 0.5 * (1 if z > 0 else -1)                 # correzione di continuita'
    z /= math.sqrt(var)
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return {"n": n, "W+": Wp, "W-": Wm, "z": z, "p": min(1.0, p),
            "method": "approssimazione normale con correzione per i ranghi medi",
            "median_diff": statistics.median(d)}


def fmt_p(p):
    if p < 1e-4:
        return f"{p:.2e}"
    return f"{p:.4f}"


# =====================================================================================
# main
# =====================================================================================
def main(argv=None):
    ap = argparse.ArgumentParser(description="Benchmark A/B di RENUVER con e senza semantic pruning.")
    ap.add_argument("--datasets", default="bridges_14,bridges_28,bridges_42,bridges_56,bridges_70")
    ap.add_argument("--runs", default="1,2,3,4,5")
    ap.add_argument("--thresholds", default="3,6,9,12,15")
    ap.add_argument("--variants", default="S1=dom-sub:allow,S2=used:allow,S3=hybrid:allow",
                    help="nome=strategia:politica_veti, separate da virgola. "
                         "Per concatenare piu' strategie nella stessa variante usare '+' "
                         "(es. A5=exact-priority+dom-sub-adaptive:allow)")
    ap.add_argument("--coltypes", default="B", choices=["B", "D"],
                    help="B = tipizzazione dello script pubblicato (archivio); D = fix del bug B")
    ap.add_argument("--skip-baseline", action="store_true",
                    help="usa il baseline dell'archivio invece di rieseguirlo (solo con --coltypes B)")
    ap.add_argument("--out", default=BENCH_JSON)
    ap.add_argument("--maxthr-offset", type=int, default=0,
                    help="aggiunge N a maxthr (args[4]) per le varianti B: compensa la copertura "
                         "persa dal pruning. Il baseline A usa sempre maxthr = soglia.")
    ap.add_argument("--reuse-baseline", default=None,
                    help="JSON con record A gia' calcolati da riusare (evita di rieseguire il baseline)")
    ap.add_argument("--family", default="auto",
                    help="famiglia di dataset (bridges, restaurant, glass, ...) o 'auto' per dedurla")
    ap.add_argument("--dataset-dir", default=None,
                    help="cartella alternativa dei dataset (es. Glass rinominato)")
    ap.add_argument("--tuple-dir", default=None,
                    help="cartella alternativa dei file TupleIniziali")
    ap.add_argument("--prune-extra", default=None,
                    help="argomenti aggiuntivi passati testualmente a pruning.py "
                         "(es. --adaptive-alpha 0.9 --adaptive-side stable)")
    ap.add_argument("--text-thr", type=float, default=None,
                    help="soglia di similarita' Levenshtein normalizzata (0..1) oltre la quale "
                         "un'imputazione testuale conta come corretta (es. 0.8 per Restaurant)")
    ap.add_argument("--keep-populated-dir", default=None,
                    help="copia il Populated/ di ogni run in questa cartella (prefissato dal nome "
                         "della variante). Serve all'analisi per-cella dell'impatto dei veti.")
    ap.add_argument("--keep-results-dir", default=None,
                    help="come --keep-populated-dir, per i file Results/")
    ap.add_argument("--checkpoint-every", type=int, default=1)
    args = ap.parse_args(argv)

    ensure_dirs()
    ensure_lab()

    # baseline riusabile, indicizzato per (soglia, dataset, run)
    reused = {}
    if args.reuse_baseline and os.path.exists(args.reuse_baseline):
        for r in json.load(open(args.reuse_baseline)):
            if r.get("variant") == "A":
                reused[(r["threshold"], r["dataset"], r["run"])] = r
        print(f"[benchmark] baseline riusato: {len(reused)} configurazioni da {args.reuse_baseline}")

    datasets = [d.strip() for d in args.datasets.split(",") if d.strip()]
    runs = [int(r) for r in args.runs.split(",") if r.strip()]
    thresholds = [int(t) for t in args.thresholds.split(",") if t.strip()]
    variants = []
    for v in args.variants.split(","):
        v = v.strip()
        if not v:
            continue
        name, spec = v.split("=", 1)
        strat, pol = (spec.split(":", 1) + ["allow"])[:2]
        variants.append({"name": name.strip(), "strategy": strat.strip(), "veto": pol.strip()})
    use_archive = bool(args.skip_baseline) and args.coltypes == "B"
    if args.coltypes == "D" and args.skip_baseline:
        sys.exit("[errore] --skip-baseline vale solo con --coltypes B (l'archivio usa B)")
    ds_dir = args.dataset_dir or os.path.join(REN, "Dataset")
    ti_dir = args.tuple_dir or os.path.join(REN, "TupleIniziali")

    records = []
    t_start = time.time()
    total_cfg = len(datasets) * len(runs) * len(thresholds)

    for thr in thresholds:
        for ds_name in datasets:
            for run in runs:
                ds_file = f"{ds_name}_{run}.csv"
                fam = args.family if args.family != "auto" else resolve_family(ds_name)
                if fam is None:
                    print(f"  !! famiglia non riconosciuta per {ds_name}, salto", flush=True)
                    continue
                coltypes = coltypes_for(fam, args.coltypes)
                rfd_name = rfd_file_for(fam, thr)
                src_ds = os.path.join(ds_dir, ds_file)
                src_ti = os.path.join(ti_dir, ds_file)
                src_rfd = os.path.join(REN, "RFD", rfd_name)
                if not (os.path.exists(src_ds) and os.path.exists(src_rfd)):
                    continue
                shutil.copy(src_ds, os.path.join(LAB, "Dataset", ds_file))
                if os.path.exists(src_ti):
                    shutil.copy(src_ti, os.path.join(LAB, "TupleIniziali", ds_file))
                shutil.copy(src_rfd, os.path.join(LAB, "RFD", rfd_name))
                rfd_in = count_rfd_lines(src_rfd)

                # ---------- A ----------
                cached = reused.get((thr, ds_name, run))
                if cached is not None:
                    mA = dict(cached)
                    mA["source"] = cached.get("source", "riusato") + " (riusato)"
                elif use_archive:
                    pop = os.path.join(REN, "Populated", f"output_{ds_file}_{thr}H0.csv")
                    logp = os.path.join(REN, "Logs", f"log_{ds_file}_{thr}H0.txt")
                    resp = os.path.join(REN, "Results", f"output_{ds_file}_{thr}H0.txt")
                    if not os.path.exists(resp):
                        continue
                    mA = metrics_from(read_populated(pop), read_log(logp), resp, rfd_in, rfd_in,
                                      text_thr=args.text_thr)
                    mA.update(rc=0, err="", variant="A", source="archivio")
                else:
                    r = run_renuver(ds_file, thr, rfd_name, coltypes)
                    mA = metrics_from(r["pop_rows"], r["log"], r["results_path"], rfd_in, rfd_in,
                                      r["wall_s"], text_thr=args.text_thr)
                    mA.update(rc=r["rc"], err=r["err"], variant="A", source="rieseguito")
                    keep_outputs("A", ds_file, thr, args.keep_populated_dir, args.keep_results_dir)
                    # controllo incrociato con l'archivio (stessa configurazione, hardware diverso)
                    if args.coltypes == "B":
                        pop = os.path.join(REN, "Populated", f"output_{ds_file}_{thr}H0.csv")
                        logp = os.path.join(REN, "Logs", f"log_{ds_file}_{thr}H0.txt")
                        resp = os.path.join(REN, "Results", f"output_{ds_file}_{thr}H0.txt")
                        if os.path.exists(resp):
                            arch = metrics_from(read_populated(pop), read_log(logp), resp, rfd_in, rfd_in,
                                                text_thr=args.text_thr)
                            mA["archive_correct"] = arch["correct"]
                            mA["archive_coverage"] = arch["coverage"]
                            mA["archive_matches"] = (arch["correct"] == mA["correct"]
                                                     and abs(arch["coverage"] - mA["coverage"]) < 1e-12)
                mA.update(dataset=ds_name, run=run, threshold=thr, family=fam)
                records.append(mA)

                # ---------- B ----------
                for v in variants:
                    out_rfd = os.path.join(PRUNED_DIR, f"{v['name']}_{ds_name}_{run}_{thr}.csv")
                    try:
                        rfd_out = make_pruned(v["strategy"], v["veto"], thr, ds_file, ds_name, run, out_rfd,
                                              family=fam, dataset_dir=ds_dir, extra=args.prune_extra,
                                              maxthr=thr + args.maxthr_offset)
                    except Exception as e:
                        print(f"  !! pruning fallito per {v['name']} {ds_file} thr{thr}: {e}", flush=True)
                        continue
                    shutil.copy(out_rfd, os.path.join(LAB, "RFD", f"pruned_{thr}.csv"))
                    # anti-trappola: se il file potato e' identico all'originale, il confronto
                    # A/B e' vacuo (nessuna differenza possibile) e il Wilcoxon dara' n = 0.
                    lab_pruned = os.path.join(LAB, "RFD", f"pruned_{thr}.csv")
                    if file_digest(lab_pruned) == file_digest(src_rfd):
                        print(f"  [WARNING] {v['name']} {ds_file} thr={thr}: il file RFD potato e' "
                              f"IDENTICO all'originale — confronto A/B vacuo (n=0 differenze).",
                              file=sys.stderr, flush=True)
                    mt = thr + args.maxthr_offset
                    r = run_renuver(ds_file, thr, f"pruned_{thr}.csv", coltypes, maxthr=mt)
                    mB = metrics_from(r["pop_rows"], r["log"], r["results_path"], rfd_in, rfd_out,
                                      r["wall_s"], text_thr=args.text_thr)
                    keep_outputs(v["name"], ds_file, mt, args.keep_populated_dir, args.keep_results_dir)
                    mB["maxthr"] = mt
                    mB.update(rc=r["rc"], err=r["err"], variant=v["name"], source="pruned",
                              strategy=v["strategy"], veto_policy=v["veto"],
                              dataset=ds_name, run=run, threshold=thr, family=fam)
                    records.append(mB)

                done = len(records)
                print(f"[{time.time()-t_start:7.0f}s] thr={thr} {ds_file}  "
                      f"A: acc={mA['accuracy']:.3f} cov={mA['coverage']:.3f} rfd={rfd_in}  "
                      + "  ".join(f"{r['variant']}: acc={r['accuracy']:.3f} cov={r['coverage']:.3f} "
                                  f"rfd={r['rfd_out']} ({r['rfd_reduction']*100:.0f}%)"
                                  for r in records[-len(variants):] if r["variant"] != "A"),
                      flush=True)
                json.dump(records, open(args.out, "w"), indent=1)

    json.dump(records, open(args.out, "w"), indent=1)
    print(f"\n[benchmark] {len(records)} record salvati in {args.out}")
    aggregate(records, variants)
    return 0


def aggregate(records, variants):
    """Stampa la tabella comparativa aggregata e i test di Wilcoxon."""
    by = collections.defaultdict(dict)
    for r in records:
        by[(r["threshold"], r["dataset"], r["run"])][r["variant"]] = r

    names = [v["name"] for v in variants]
    print("\n" + "=" * 118)
    print("TABELLA COMPARATIVA AGGREGATA (media sui run, per soglia)")
    print("=" * 118)
    hdr = f"{'soglia':>7}{'variante':>10}{'RFD':>9}{'rid.%':>7}{'cover':>8}{'precis':>8}{'acc':>7}" \
          f"{'F1':>7}{'RFD usate':>11}{'pre_ms':>10}{'exec_ms':>10}{'RMSE':>9}{'MAE':>9}"
    print(hdr)
    print("-" * 118)
    for thr in sorted({r["threshold"] for r in records}):
        for name in ["A"] + names:
            sub = [m[name] for k, m in by.items() if k[0] == thr and name in m and m[name].get("rc") == 0]
            if not sub:
                continue
            f = lambda k: statistics.mean([s[k] for s in sub if s.get(k) is not None]) if any(
                s.get(k) is not None for s in sub) else float("nan")
            print(f"{thr:>7}{name:>10}{f('rfd_out'):>9.0f}{100*f('rfd_reduction'):>7.1f}"
                  f"{f('coverage'):>8.3f}{f('precision'):>8.3f}{f('accuracy'):>7.3f}{f('f1'):>7.3f}"
                  f"{f('n_rfd_used'):>11.1f}{f('pre_ms'):>10.0f}{f('exec_ms'):>10.0f}"
                  f"{f('rmse'):>9.3f}{f('mae'):>9.3f}")
        print("-" * 118)

    print("\n" + "=" * 118)
    print("TEST DI WILCOXON SIGNED-RANK (appaiato per dataset+soglia+run, A vs B)")
    print("=" * 118)
    print(f"{'variante':>10}{'metrica':>12}{'n':>5}{'mediana Δ':>12}{'W+':>9}{'W-':>9}{'p-value':>12}  metodo")
    print("-" * 118)
    for name in names:
        for metric in ("accuracy", "coverage", "precision", "f1", "correct", "wrong",
                       "n_rfd_used", "total_ms", "pre_ms", "exec_ms", "rmse", "mae"):
            xs, ys = [], []
            for k, m in by.items():
                if "A" in m and name in m and m["A"].get("rc") == 0 and m[name].get("rc") == 0:
                    a, b = m["A"].get(metric), m[name].get(metric)
                    if a is not None and b is not None:
                        xs.append(b); ys.append(a)          # B - A
            if len(xs) < 3:
                continue
            res = wilcoxon_signed_rank(xs, ys)
            md = res.get("median_diff")
            print(f"{name:>10}{metric:>12}{res['n']:>5}{(f'{md:+.4f}' if md is not None else '-'):>12}"
                  f"{res['W+']:>9.1f}{res['W-']:>9.1f}{fmt_p(res['p']):>12}  {res.get('method','')}")
        print("-" * 118)


if __name__ == "__main__":
    sys.exit(main())
