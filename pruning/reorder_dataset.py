#!/usr/bin/env python3
"""
reorder_dataset.py — A3: riordino delle RIGHE del dataset (il JAR non si tocca).

RENUVER (euristica 0, `sequentialExecution`) processa le righe **nell'ordine in cui compaiono
nel CSV** e, dentro ogni riga, le celle null nell'ordine delle colonne. Ogni valore imputato
diventa disponibile come LHS per le righe successive: l'ordine determina quindi gli effetti a
cascata. Le tre euristiche alternative esistono nel bytecode come codice morto; due di esse si
possono emulare **dall'esterno**, riordinando il file di input.

Uso:
    python3 reorder_dataset.py \
        --dataset RENUVER/Dataset/bridges_70_1.csv \
        --rfd     RENUVER/RFD/output_false_15_bridges.csv \
        --heuristic null-count \
        --output  RENUVER/Dataset/bridges_70_1_rc.csv

ATTENZIONE — la ground truth va rimappata
-----------------------------------------
RENUVER produce `Populated/` leggendo `TupleIniziali/<dataset>` e facendo `dataset.get(row-1)`.
Riordinando le righe gli indici cambiano, quindi `TupleIniziali` va riscritto con i nuovi numeri
di riga, altrimenti il confronto con la verità di base e' sbagliato (o va in errore). Lo script
lo fa automaticamente: scrive `<output>` e, accanto, il `TupleIniziali` rimappato con lo stesso
nome base, cosi' che RENUVER lo trovi.

    RENUVER/Dataset/bridges_70_1_rc.csv          <- dataset riordinato
    RENUVER/TupleIniziali/bridges_70_1_rc.csv    <- ground truth rimappata

Euristiche
----------
  null-count        (RENUVER: nullValueBasedOrderExecution, variante ASC)
                    prima le righe con MENO celle nulle: hanno piu' LHS disponibili, quindi
                    piu' RFD applicabili -> imputazioni di qualita' migliore, che a loro volta
                    arricchiscono il dataset per le righe successive.
  null-count-desc   la variante fedele al bytecode (NullValueComparator ordina DESC): prima le
                    righe piu' incomplete.
  lhs-involvement   (RENUVER: timesInvolvedInLHSBasedOrderExecution)
                    per ultime le righe le cui colonne nulle compaiono piu' spesso nei LHS delle
                    RFD: cosi' quando servono come LHS sono gia' state valorizzate.
  lhs-involvement-desc  ordine inverso.
  identity          nessun riordino (controllo).
"""

from __future__ import annotations

import argparse
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import RENUVER, ensure_dirs                      # noqa: E402
from pruning import is_null, read_lines, parse_rfd_row, NULL_TOKENS   # noqa: E402

HEURISTICS = ["null-count", "null-count-desc", "lhs-involvement", "lhs-involvement-desc", "identity"]


def read_csv(path, sep=";"):
    lines = read_lines(path)
    header = lines[0].split(sep)
    rows = [l.split(sep) for l in lines[1:]]
    return header, rows


def null_count(row):
    return sum(1 for v in row if is_null(v))


def lhs_involvement(header, row, rfds):
    """Somma, sulle colonne nulle della riga, di quante RFD le usano nel LHS."""
    idx_by_name = {a: i for i, a in enumerate(header)}
    tot = 0
    for i, v in enumerate(row):
        if is_null(v) and i < len(header):
            tot += rfds.get(header[i], 0)
    return tot


def main(argv=None):
    ap = argparse.ArgumentParser(description="Riordina le righe di un dataset per emulare le "
                                             "euristiche di ordinamento di RENUVER.")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--rfd", default=None, help="serve solo per lhs-involvement")
    ap.add_argument("--heuristic", default="null-count", choices=HEURISTICS)
    ap.add_argument("--output", required=True)
    ap.add_argument("--sep", default=";")
    ap.add_argument("--tuple-in", default=None,
                    help="TupleIniziali originale (default: RENUVER/TupleIniziali/<basename>)")
    ap.add_argument("--tuple-out", default=None,
                    help="TupleIniziali rimappato (default: RENUVER/TupleIniziali/<basename output>)")
    args = ap.parse_args(argv)
    ensure_dirs()

    header, rows = read_csv(args.dataset, args.sep)
    n = len(rows)

    rhs_count = collections.Counter()
    if args.heuristic.startswith("lhs-involvement"):
        if not args.rfd:
            sys.exit("[errore] --rfd e' obbligatorio con lhs-involvement")
        rh, rhl, body = read_lines(args.rfd)[0].split(";"), None, read_lines(args.rfd)[1:]
        for line in body:
            p = parse_rfd_row(rh, line)
            if p:
                for c in p["lhs"]:
                    rhs_count[c] += 1
        print(f"[reorder] RFD lette: {len(body)}, colonne nel LHS: {len(rhs_count)}")

    if args.heuristic == "identity":
        perm = list(range(n))
    elif args.heuristic == "null-count":
        perm = sorted(range(n), key=lambda i: (null_count(rows[i]), i))
    elif args.heuristic == "null-count-desc":
        perm = sorted(range(n), key=lambda i: (-null_count(rows[i]), i))
    elif args.heuristic == "lhs-involvement":
        perm = sorted(range(n), key=lambda i: (lhs_involvement(header, rows[i], rhs_count), i))
    else:
        perm = sorted(range(n), key=lambda i: (-lhs_involvement(header, rows[i], rhs_count), i))

    # nuovo numero di riga (1-based) per ogni vecchia riga (0-based)
    new_row_of_old = {old: new for new, old in enumerate(perm)}

    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(args.sep.join(header) + "\n")
        for i in perm:
            fh.write(args.sep.join(rows[i]) + "\n")

    # ---- ground truth rimappata -------------------------------------------------
    base_out = os.path.basename(args.output)
    tuple_in = args.tuple_in or os.path.join(RENUVER, "TupleIniziali", os.path.basename(args.dataset))
    tuple_out = args.tuple_out or os.path.join(RENUVER, "TupleIniziali", base_out)
    n_gt = 0
    if os.path.exists(tuple_in):
        os.makedirs(os.path.dirname(os.path.abspath(tuple_out)), exist_ok=True)
        with open(tuple_out, "w", encoding="utf-8") as fh:
            for line in read_lines(tuple_in):
                parts = line.split(";")
                if len(parts) >= 3:
                    try:
                        old_row = int(parts[0])
                    except ValueError:
                        fh.write(line + "\n")
                        continue
                    if (old_row - 1) in new_row_of_old:
                        parts[0] = str(new_row_of_old[old_row - 1] + 1)
                        n_gt += 1
                fh.write(";".join(parts) + "\n")
        print(f"[reorder] ground truth rimappata: {n_gt} celle -> {tuple_out}")
    else:
        print(f"[avviso] TupleIniziali non trovato: {tuple_in}")

    print(f"[reorder] euristica '{args.heuristic}' applicata a {n} righe")
    print(f"  dataset    : {args.output}")
    print(f"  celle nulle: prima riga = {null_count(rows[perm[0]])}, "
          f"ultima riga = {null_count(rows[perm[-1]])}")
    print(f"  righe spostate: {sum(1 for i, p in enumerate(perm) if i != p)}/{n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
