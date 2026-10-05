#!/usr/bin/env python3
"""
fix_glass_schema.py — B1: allinea lo schema di Glass fra dataset e file RFD (JAR invariato).

IL BUG
------
    Dataset/glass_*.csv          header: A;B;C;D;E;F;G;H;I;J;K        (anonimizzato)
    RFD/output_false_*_glass.csv header: RHS;ID;RI;Na;Mg;Al;Si;K;Ca;Ba;Fe;Type   (nomi UCI)

RENUVER costruisce le `Column` dal header del file RFD assegnando `index = posizione - 1`, e
risolve il RHS **per nome** (`findBestRFDs` confronta `r.getRHS().getName()` con il nome della
colonna del dataset). Quando i nomi non coincidono:
  * per 10 colonne su 11 nessuna RFD viene mai trovata -> la colonna non e' imputabile;
  * per la colonna che coincide per caso (`K` nel file RFD e' alla posizione 7 -> indice 6, che
    nel dataset e' `G`), RENUVER **legge e scrive nella colonna sbagliata**, sovrascrivendo un
    valore noto e lasciando vuota la cella richiesta.

IL FIX (esterno)
----------------
Si rinominano le colonne del dataset in modo **posizionale**, facendole coincidere con i nomi del
file RFD. Il mapping e' una permutazione identita' sulle posizioni:

    posizione:  0   1   2   3   4   5   6   7   8   9   10
    dataset:    A   B   C   D   E   F   G   H   I   J   K
    RFD:        ID  RI  Na  Mg  Al  Si  K   Ca  Ba  Fe  Type

Dopo il fix i nomi coincidono **e le posizioni restano le stesse**, quindi gli indici usati da
RENUVER tornano corretti.

ATTENZIONE — anche la ground truth va rinominata
-------------------------------------------------
`TupleIniziali/glass_*.csv` usa i nomi del dataset anonimizzato (`C`, `D`, `I`, `K`, ...). Dopo il
fix quei nomi non esistono piu': RENUVER cercherebbe una colonna inesistente in `saveOutputFile`
e andrebbe in `NullPointerException`. Lo script riscrive anche i TupleIniziali con i nomi nuovi.

Uso:
    python3 fix_glass_schema.py \
        --dataset-dir RENUVER/Dataset --pattern "glass_*.csv" \
        --mapping "A:ID,B:RI,C:Na,D:Mg,E:Al,F:Si,G:K,H:Ca,I:Ba,J:Fe,K:Type" \
        --output-dir RENUVER/Dataset/glass_fixed \
        --tuple-dir RENUVER/TupleIniziali --tuple-output-dir RENUVER/TupleIniziali/glass_fixed
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import RENUVER                                   # noqa: E402
from pruning import read_lines                              # noqa: E402

DEFAULT_MAPPING = "A:ID,B:RI,C:Na,D:Mg,E:Al,F:Si,G:K,H:Ca,I:Ba,J:Fe,K:Type"


def parse_mapping(text):
    m = {}
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            sys.exit(f"[errore] voce di mapping non valida: {part!r} (atteso NUOVO:VECCHIO? no: VECCHIO:NUOVO)")
        old, new = part.split(":", 1)
        m[old.strip()] = new.strip()
    return m


def rename_header(header, mapping, sep):
    """Rinomina le colonne in un solo passaggio (evita collisioni tipo G->K e K->Type)."""
    return [mapping.get(c, c) for c in header]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Allinea i nomi delle colonne di Glass fra dataset e RFD.")
    ap.add_argument("--dataset-dir", default=os.path.join(RENUVER, "Dataset"))
    ap.add_argument("--pattern", default="glass_*.csv")
    ap.add_argument("--mapping", default=DEFAULT_MAPPING,
                    help="VECCHIO:NUOVO separati da virgola (default: mapping Glass)")
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--tuple-dir", default=os.path.join(RENUVER, "TupleIniziali"))
    ap.add_argument("--tuple-output-dir", default=None,
                    help="se omesso, i TupleIniziali non vengono riscritti")
    ap.add_argument("--sep", default=";")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args(argv)

    mapping = parse_mapping(args.mapping)
    os.makedirs(args.output_dir, exist_ok=True)
    if args.tuple_output_dir:
        os.makedirs(args.tuple_output_dir, exist_ok=True)

    files = sorted(glob.glob(os.path.join(args.dataset_dir, args.pattern)))
    if not files:
        sys.exit(f"[errore] nessun file trovato per {os.path.join(args.dataset_dir, args.pattern)}")

    print("=" * 84)
    print("FIX SCHEMA GLASS — allineamento posizionale dei nomi di colonna")
    print("=" * 84)
    tot_ds = tot_ti = 0
    for path in files:
        lines = read_lines(path)
        header = lines[0].split(args.sep)
        missing = [c for c in header if c not in mapping]
        if missing:
            print(f"[salto] {os.path.basename(path)}: colonne non mappate {missing}")
            continue
        new_header = rename_header(header, mapping, args.sep)
        if len(set(new_header)) != len(new_header):
            print(f"[salto] {os.path.basename(path)}: il mapping produce nomi duplicati")
            continue
        out = os.path.join(args.output_dir, os.path.basename(path))
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(args.sep.join(new_header) + "\n")
            for l in lines[1:]:
                fh.write(l + "\n")
        tot_ds += 1
        if args.report:
            print(f"  {os.path.basename(path)}: {len(lines)-1} righe")
            print(f"    prima : {args.sep.join(header)}")
            print(f"    dopo  : {args.sep.join(new_header)}")

        # ---- ground truth ----
        if args.tuple_output_dir:
            tp = os.path.join(args.tuple_dir, os.path.basename(path))
            if not os.path.exists(tp):
                continue
            tlines = read_lines(tp)
            tout = os.path.join(args.tuple_output_dir, os.path.basename(path))
            with open(tout, "w", encoding="utf-8") as fh:
                for l in tlines:
                    parts = l.split(args.sep)
                    if len(parts) >= 3 and parts[1] in mapping:
                        parts[1] = mapping[parts[1]]
                    fh.write(args.sep.join(parts) + "\n")
            tot_ti += 1

    print()
    print(f"dataset rinominati          : {tot_ds}  -> {args.output_dir}")
    if args.tuple_output_dir:
        print(f"ground truth rinominata     : {tot_ti}  -> {args.tuple_output_dir}")
    print(f"mapping applicato           : {mapping}")
    print()
    print("Per eseguire RENUVER su Glass corretto servono 11 tipi di colonna, es.:")
    print('  java -jar RENUVER_EDBT.jar "D,D,D,D,D,D,D,D,D,D,D" "glass_22_1.csv" ";" \\')
    print('       "output_false_15_glass.csv" "15" "0"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
