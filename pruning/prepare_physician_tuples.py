"""Prepara i file TupleIniziali della famiglia Physician per l'esecuzione.

Il difetto D3 della tesi consiste in indici di ground truth che eccedono il numero di righe del
dataset: RENUVER, leggendo quei file per sapere quali celle imputare, esce con
`IndexOutOfBoundsException`. Questo script costruisce una cartella alternativa di file
TupleIniziali in cui le righe con indice fuori intervallo sono **escluse**, e dichiara quante
celle restano valutabili per ciascuna configurazione.

Non modifica l'archivio: scrive in una cartella separata, da passare a `benchmark.py` con
`--tuple-dir`.

Uso:  python3 pruning/prepare_physician_tuples.py [--out .scratch/physician_ti]
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402

CONFIGS = [
    ("Physician_Compare_National_remodulated_0.005", 13),
    ("Physician_Compare_National_remodulated_0.01", 27),
    ("Physician_Compare_National_remodulated_0.05", 135),
    ("Physician_Compare_National_remodulated_0.1", 269),
]


def data_rows(dataset_path):
    """Righe di dati del dataset (esclusa l'intestazione)."""
    with open(dataset_path, encoding="utf-8", errors="replace") as fh:
        return max(0, sum(1 for line in fh if line.strip()) - 1)


def read_tuples(path):
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split(";", 2)
            rows.append(parts)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=os.path.join(paths.SCRATCH, "physician_ti"))
    ap.add_argument("--index-base", type=int, default=0, choices=[0, 1],
                    help="base degli indici di riga nel file TupleIniziali (default 0)")
    args = ap.parse_args(argv)

    os.makedirs(args.out, exist_ok=True)
    print(f"cartella di destinazione: {os.path.relpath(args.out, paths.ROOT)}")
    print(f"{'configurazione':<52}{'righe':>7}{'celle':>7}{'escluse':>8}{'valutabili':>11}")
    total_kept = total_drop = 0
    for prefix, cells in CONFIGS:
        ds_name = f"{prefix}_{cells}_1.csv"
        ds_path = os.path.join(paths.RENUVER, "Dataset", ds_name)
        ti_path = os.path.join(paths.RENUVER, "TupleIniziali", ds_name)
        if not (os.path.exists(ds_path) and os.path.exists(ti_path)):
            print(f"  {ds_name:<50} MANCANTE")
            continue
        n_rows = data_rows(ds_path)
        rows = read_tuples(ti_path)
        limit = n_rows + (1 if args.index_base == 1 else 0)
        kept, dropped = [], 0
        for parts in rows:
            try:
                idx = int(parts[0])
            except (ValueError, IndexError):
                dropped += 1
                continue
            if 0 <= idx < limit:
                kept.append(parts)
            else:
                dropped += 1
        with open(os.path.join(args.out, ds_name), "w", encoding="utf-8") as fh:
            for parts in kept:
                fh.write(";".join(parts) + "\n")
        total_kept += len(kept)
        total_drop += dropped
        print(f"  {ds_name:<50}{n_rows:>7}{len(rows):>7}{dropped:>8}{len(kept):>11}")
    print(f"{'totale':<52}{'':>7}{'':>7}{total_drop:>8}{total_kept:>11}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
