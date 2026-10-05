#!/usr/bin/env python3
"""estrai_classi.py — copia di comodo delle classi dell'applicazione contenute nell'archivio.

Le analisi del bytecode (`analisi/bytecode_analysis.md`, `analisi/sub_datamodel.md`,
`analisi/sub_deadcode.md`) e gli strumenti di `analisi/strumenti/` lavorano su **file .class**,
non sull'archivio JAR. Questo script estrae dall'archivio le classi del package di default — le
tredici classi scritte dagli autori del sistema — e le deposita in `analisi/classi/`.

L'archivio **non viene modificato**: l'impronta MD5 viene stampata prima e dopo l'estrazione e
deve restare la stessa. Le classi sono le stesse che si ottengono con

    unzip -o RENUVER/RENUVER_EDBT.jar '*.class' -d analisi/classi
    # (solo il primo livello: le librerie di terze parti non servono)

Uso:
    python3 analisi/estrai_classi.py                       # estrae in analisi/classi/
    python3 analisi/estrai_classi.py --out .scratch/classi # estrae altrove
    python3 analisi/estrai_classi.py --jar altro.jar --out /tmp/classi
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_JAR = os.path.join(ROOT, "RENUVER", "RENUVER_EDBT.jar")
DEFAULT_OUT = os.path.join(HERE, "classi")


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def classi_di_primo_livello(jar):
    """Nomi dei membri `<Nome>.class` che stanno nella radice dell'archivio (package di default)."""
    with zipfile.ZipFile(jar) as z:
        nomi = [n for n in z.namelist()
                if n.endswith(".class") and "/" not in n and not n.startswith("META-INF")]
    return sorted(nomi)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Estrae le classi dell'applicazione dall'archivio RENUVER (copia di comodo).")
    ap.add_argument("--jar", default=DEFAULT_JAR)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    if not os.path.isfile(args.jar):
        sys.exit(f"[errore] archivio non trovato: {args.jar}")
    prima = md5(args.jar)

    nomi = classi_di_primo_livello(args.jar)
    if not nomi:
        sys.exit("[errore] nessuna classe di primo livello nell'archivio: file inatteso")
    os.makedirs(args.out, exist_ok=True)

    tot = 0
    with zipfile.ZipFile(args.jar) as z:
        for n in nomi:
            dati = z.read(n)
            with open(os.path.join(args.out, n), "wb") as fh:
                fh.write(dati)
            tot += len(dati)
            print(f"  {n:<48} {len(dati):>7} byte")

    dopo = md5(args.jar)
    print(f"\nclassi estratte : {len(nomi)}  ({tot} byte) in {os.path.relpath(args.out, ROOT)}")
    print(f"md5 archivio    : {prima} -> {dopo}  ({'invariato' if prima == dopo else 'MODIFICATO'})")
    if prima != dopo:
        sys.exit("[errore] l'archivio e' cambiato durante l'estrazione: non deve accadere")
    print("\nDa qui gli strumenti di analisi, per esempio:")
    print("  python3 analisi/strumenti/cfhdr.py analisi/classi/FillingAlgorithm.class")
    print("  python3 analisi/strumenti/jvmdis.py analisi/classi/FillingAlgorithm.class | head -40")
    print("  cd analisi/strumenti && python3 absbr.py ../classi/FillingAlgorithm.class | head -40")
    return 0


if __name__ == "__main__":
    sys.exit(main())
