"""Ripara i dataset remodulati Physician con righe malformate e prepara i file di ground truth.

Diagnosi (campagna Physician, quarta famiglia). Le versioni remodulate 0.05 e 0.1 non sono
eseguibili: RENUVER esce con `IndexOutOfBoundsException` all'avvio. La causa non è il materiale di
ground truth, che è ben formato, ma **righe dei dataset con un numero di campi inferiore a quello
dello schema** (7, 11 o 1 invece di 13): il file risulta troncato a metà di un record, e in un caso
un valore testuale contenente un ritorno a capo ha spezzato la riga. Il controllo di chiave del
sistema accede ai campi per indice e non sopravvive alla riga corta.

La riparazione è minima e conservativa: ogni riga con un numero di campi diverso da quello dello
schema viene sostituita da una riga di soli valori mancanti. La sostituzione **conserva la
numerazione delle righe**, su cui è indicizzato il ground truth, e produce una riga che il sistema
ignora in entrambi i ruoli (i valori mancanti non partecipano né alla generazione né al confronto
per il veto).

Lo script scrive in cartelle separate (`.scratch/physician_ds/` e `.scratch/physician_ti_fix/`) e
non modifica l'archivio.

Uso:  python3 pruning/repair_physician_datasets.py
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402

CONFIGS = [
    ("Physician_Compare_National_remodulated_0.05", 135),
    ("Physician_Compare_National_remodulated_0.1", 269),
]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ds-out", default=os.path.join(paths.SCRATCH, "physician_ds"))
    ap.add_argument("--ti-out", default=os.path.join(paths.SCRATCH, "physician_ti_fix"))
    args = ap.parse_args(argv)

    os.makedirs(args.ds_out, exist_ok=True)
    os.makedirs(args.ti_out, exist_ok=True)
    print(f"{'configurazione':<50}{'righe':>7}{'riparate':>9}{'celle':>7}{'escluse':>8}{'valutabili':>11}")
    for prefix, cells in CONFIGS:
        name = f"{prefix}_{cells}_1.csv"
        ds_path = os.path.join(paths.RENUVER, "Dataset", name)
        ti_path = os.path.join(paths.RENUVER, "TupleIniziali", name)
        with open(ds_path, encoding="utf-8", errors="replace") as fh:
            lines = [l.rstrip("\n") for l in fh]
        header, body = lines[0], [l for l in lines[1:] if l.strip()]
        n_cols = len(header.split(";"))
        repaired = 0
        out = [header]
        for line in body:
            if len(line.split(";")) == n_cols:
                out.append(line)
            else:
                repaired += 1
                out.append(";".join(["?"] * n_cols))
        with open(os.path.join(args.ds_out, name), "w", encoding="utf-8") as fh:
            fh.write("\n".join(out) + "\n")

        # ground truth: si tengono le celle con indice di riga interno al dataset riparato
        kept, dropped = [], 0
        with open(ti_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                parts = line.rstrip("\n").split(";", 2)
                try:
                    idx = int(parts[0])
                except (ValueError, IndexError):
                    dropped += 1
                    continue
                if 0 <= idx < len(body):
                    kept.append(parts)
                else:
                    dropped += 1
        with open(os.path.join(args.ti_out, name), "w", encoding="utf-8") as fh:
            for parts in kept:
                fh.write(";".join(parts) + "\n")
        print(f"  {name:<48}{len(body):>7}{repaired:>9}{len(kept) + dropped:>7}{dropped:>8}{len(kept):>11}")
    print(f"\ndataset riparati: {os.path.relpath(args.ds_out, paths.ROOT)}")
    print(f"ground truth filtrato: {os.path.relpath(args.ti_out, paths.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
