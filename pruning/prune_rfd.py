#!/usr/bin/env python3
"""
prune_rfd.py — Semantic pruning di un set di RFD per RENUVER.

Uso:
    python3 prune_rfd.py --rfd RFD/output_false_15_bridges.csv \
                         --dataset Dataset/bridges_14_1.csv \
                         --out RFD/output_false_15_bridges.pruned.csv \
                         [--coverage] [--dominance {none,sub,super,sub+super}] \
                         [--max-lhs N] [--min-rhs-thr X] [--blacklist FILE] [--report]

Strategie implementate
----------------------
--coverage      (P2) Rimuove le RFD che non possono applicarsi ad alcuna cella nulla del dataset:
                     per ogni cella (riga, attributo) con valore "?", una RFD con RHS == attributo e
                     tutte le colonne del LHS non nulle in quella riga e' applicabile.
                     ESATTO: non puo' perdere imputazioni. Rende 33-46% su bridges, ~0% su ristorante.

--dominance sub (P3) Rimuove r se esiste r' con stesso RHS, insieme di attributi LHS SOTTOINSIEME di
                     quello di r, soglie <= sulle colonne condivise e soglia RHS <=.
                     Aggressiva. Misurata come la piu' efficace (-67% su bridges senza perdite).
--dominance super    Direzione opposta (LHS sovrainsieme). Teoricamente "sicura" ma MISURATA come
                     controproducente su RENUVER: perde imputazioni. Sconsigliata.
--dominance sub+super  Applica entrambe.

--max-lhs N     (P4) Tiene solo le RFD con al piu' N colonne nel LHS.
--min-rhs-thr X (P5) Tiene solo le RFD con soglia RHS >= X (0 tiene tutto).
                     Alzare X migliora la precisione ma riduce la copertura.
--blacklist F   (P6) File con una RFD per riga (stesso formato del file RFD) da eliminare.
                     Serve per il pruning data-driven: le RFD con accuratezza empirica troppo bassa.
                     ATTENZIONE: le statistiche vanno stimate su run disgiunti da quello di test.

--report        Stampa un riepilogo delle rimozioni per strategia.

ATTENZIONE — vincoli di formato
-------------------------------
RENUVER legge il file RFD per posizione: `Column.index` e' la posizione 0-based della colonna nel
header. Se il header del file RFD non ha le stesse colonne, nello stesso ordine, del dataset, RENUVER
scrive nella colonna sbagliata (corruzione silenziosa). Questo script NON riordina mai le colonne e
preserva le righe originali byte per byte; verifica comunque l'allineamento e avvisa.
"""

import argparse
import collections
import os
import re
import sys

NULL_TOKENS = {"?", "", "null", "NULL", "NA", "nan", "NaN", "None"}


def is_null(v):
    return v in NULL_TOKENS


# --------------------------------------------------------------------------- IO
def read_lines(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = [l.rstrip("\n").rstrip("\r") for l in fh]
    return [l for l in lines if l.strip()]


def read_dataset(path, sep=";"):
    lines = read_lines(path)
    header = lines[0].split(sep)
    rows = []
    for l in lines[1:]:
        cells = l.split(sep)
        rows.append({a: (cells[i].strip() if i < len(cells) else "") for i, a in enumerate(header)})
    return header, rows


def parse_rfd(header, line):
    """Restituisce dict(rhs, rhs_thr, lhs) oppure None se la riga non e' interpretabile."""
    cells = line.split(";")
    if len(cells) < len(header):
        cells = cells + ["?"] * (len(header) - len(cells))
    rhs = cells[0].strip()
    if rhs not in header:
        return None
    rhs_pos = header.index(rhs)
    lhs, rhs_thr = {}, None
    for i, attr in enumerate(header):
        if i == 0:
            continue
        tok = cells[i].strip()
        if tok == "?":
            continue
        try:
            thr = float(tok)
        except ValueError:
            continue
        if i == rhs_pos:
            rhs_thr = thr
        else:
            lhs[attr] = thr
    if rhs_thr is None:
        return None
    return {"rhs": rhs, "rhs_thr": rhs_thr, "lhs": lhs}


# --------------------------------------------------------------------- strategie
def mask_coverage(parsed, null_by_attr, rows, attrs):
    """P2 — esatto. True = tenere."""
    keep = []
    for p in parsed:
        ok = False
        for ri in null_by_attr.get(p["rhs"], ()):
            row = rows[ri]
            if all((c in attrs) and not is_null(row[c]) for c in p["lhs"]):
                ok = True
                break
        keep.append(ok)
    return keep


def _signature(p):
    return (p["rhs_thr"], tuple(sorted(p["lhs"].items())))


def mask_dominance(parsed, direction="sub", max_extra=1):
    """P3 — rimuove le RFD dominate.

    direction='sub'   : r e' rimossa se esiste r' con LHS SOTTOINSIEME (al piu' `max_extra` colonne
                        in meno), soglie <= sulle condivise e soglia RHS <=.
    direction='super' : r e' rimossa se esiste r' con LHS SOVRAINSIEME (al piu' `max_extra` colonne
                        in piu'), stesse condizioni.
    """
    buckets = collections.defaultdict(list)
    for i, p in enumerate(parsed):
        buckets[(p["rhs"], frozenset(p["lhs"]))].append(i)
    by_rhs = collections.defaultdict(set)
    for rhs, s in buckets:
        by_rhs[rhs].add(s)

    keep = [True] * len(parsed)
    for i, r in enumerate(parsed):
        S = frozenset(r["lhs"])
        Ssig = _signature(r)
        for T in by_rhs[r["rhs"]]:
            if direction == "sub":
                if not (T <= S) or len(S) - len(T) > max_extra or T == S:
                    continue
                shared = T
            else:
                if not (S <= T) or len(T) - len(S) > max_extra or T == S:
                    continue
                shared = S
            for j in buckets[(r["rhs"], T)]:
                q = parsed[j]
                if any(q["lhs"][c] > r["lhs"][c] for c in shared):
                    continue
                if q["rhs_thr"] > r["rhs_thr"]:
                    continue
                if T == S and _signature(q) >= Ssig:      # evita rimozione mutua
                    continue
                keep[i] = False
                break
            if not keep[i]:
                break
    return keep


def mask_same_lhs_dominance(parsed):
    """P3 — variante esatta e conservativa: solo RFD con lo STESSO insieme di attributi LHS."""
    return mask_dominance(parsed, direction="super", max_extra=0)


def mask_lhs_cap(parsed, cap):
    return [len(p["lhs"]) <= cap for p in parsed]


def mask_rhs_thr(parsed, minimum):
    return [p["rhs_thr"] >= minimum for p in parsed]


def mask_blacklist(parsed, blacklist_signatures):
    return [_signature(p) not in blacklist_signatures for p in parsed]


def read_blacklist(path):
    lines = read_lines(path)
    if not lines:
        return set()
    header = lines[0].split(";")
    sigs = set()
    for l in lines[1:]:
        p = parse_rfd(header, l)
        if p is not None:
            sigs.add(_signature(p))
    return sigs


# ------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description="Semantic pruning di un set di RFD per RENUVER.")
    ap.add_argument("--rfd", required=True, help="file RFD di input")
    ap.add_argument("--dataset", required=True, help="dataset CSV (per il pruning per copertura e la validazione schema)")
    ap.add_argument("--out", required=True, help="file RFD di output")
    ap.add_argument("--coverage", action="store_true", help="P2: pruning per copertura (esatto)")
    ap.add_argument("--dominance", default="none", choices=["none", "sub", "super", "sub+super"],
                    help="P3: pruning per dominanza (default: none)")
    ap.add_argument("--max-lhs", type=int, default=None, help="P4: massimo numero di colonne nel LHS")
    ap.add_argument("--min-rhs-thr", type=float, default=0.0, help="P5: soglia RHS minima accettata")
    ap.add_argument("--blacklist", default=None, help="P6: file di RFD da eliminare")
    ap.add_argument("--report", action="store_true", help="stampa il riepilogo")
    args = ap.parse_args(argv)

    rfd_lines = read_lines(args.rfd)
    if not rfd_lines:
        sys.exit("file RFD vuoto")
    header = rfd_lines[0].split(";")
    body = rfd_lines[1:]

    parsed, raws = [], []
    for line in body:
        p = parse_rfd(header, line)
        if p is None:
            print(f"[warn] riga RFD non interpretabile, tenuta cosi' com'e': {line[:80]}", file=sys.stderr)
            continue
        parsed.append(p)
        raws.append(line)

    # --- validazione dello schema -------------------------------------------------
    ds_header, ds_rows = read_dataset(args.dataset)
    attrs = set(ds_header)
    lhs_attrs = {c for p in parsed for c in p["lhs"]}
    rhs_attrs = {p["rhs"] for p in parsed}
    unknown = (lhs_attrs | rhs_attrs) - attrs
    if unknown:
        print(f"[ERRORE] il file RFD referenzia attributi assenti nel dataset: {sorted(unknown)}",
              file=sys.stderr)
        print("         RENUVER risolve le colonne per POSIZIONE: con header disallineati scrive nella",
              file=sys.stderr)
        print("         colonna sbagliata. Allinea i due schemi prima di procedere.", file=sys.stderr)
        return 2
    rfd_attrs = [a for a in header[1:]]
    if rfd_attrs != ds_header:
        print(f"[warn] ordine delle colonne diverso fra RFD e dataset.", file=sys.stderr)
        print(f"       RFD     : {rfd_attrs}", file=sys.stderr)
        print(f"       dataset : {ds_header}", file=sys.stderr)
        print("       RENUVER usa gli indici posizionali: verifica che sia voluto.", file=sys.stderr)

    # --- maschere -----------------------------------------------------------------
    keep = [True] * len(parsed)
    steps = []

    def apply(name, mask):
        nonlocal keep
        before = sum(keep)
        keep = [a and b for a, b in zip(keep, mask)]
        removed = before - sum(keep)
        steps.append((name, removed, sum(keep)))
        return removed

    if args.coverage:
        null_by_attr = collections.defaultdict(list)
        for ri, row in enumerate(ds_rows):
            for a in ds_header:
                if is_null(row[a]):
                    null_by_attr[a].append(ri)
        apply("P2 copertura", mask_coverage(parsed, null_by_attr, ds_rows, attrs))

    if args.dominance in ("sub", "sub+super"):
        apply("P3 dominanza LHS-sottoinsieme", mask_dominance(parsed, "sub"))
    if args.dominance in ("super", "sub+super"):
        apply("P3 dominanza LHS-sovrainsieme", mask_dominance(parsed, "super"))

    if args.max_lhs is not None:
        apply(f"P4 |LHS| <= {args.max_lhs}", mask_lhs_cap(parsed, args.max_lhs))

    if args.min_rhs_thr > 0:
        apply(f"P5 soglia RHS >= {args.min_rhs_thr}", mask_rhs_thr(parsed, args.min_rhs_thr))

    if args.blacklist:
        apply(f"P6 blacklist ({args.blacklist})", mask_blacklist(parsed, read_blacklist(args.blacklist)))

    # --- scrittura ----------------------------------------------------------------
    kept = [l for l, k in zip(raws, keep) if k]
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(rfd_lines[0] + "\n")
        for l in kept:
            fh.write(l + "\n")

    if args.report or True:
        n0 = len(raws)
        print(f"RFD in ingresso : {n0}")
        for name, removed, remaining in steps:
            print(f"  {name:<34} -{removed:>6}  -> {remaining:>6}  ({100*removed/max(1,n0):>5.1f}%)")
        print(f"RFD in uscita   : {len(kept)}  (riduzione {100*(n0-len(kept))/max(1,n0):.1f}%)")
        print(f"scritto         : {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
