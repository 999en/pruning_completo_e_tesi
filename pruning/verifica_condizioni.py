#!/usr/bin/env python3
"""verifica_condizioni.py — ricalcola le due tabelle di dati del capitolo 3 della tesi.

La tesi (capitolo 3, sezione «Dal sistema alle condizioni esatte») riporta due tabelle costruite
sui file di regole dell'archivio:

  * `tab:conditions` — per ogni famiglia e soglia: numero di regole `N`, quante sono **inerti**
    `[V3]`, quante sono **coperte** `[V2]`, e la quota della loro unione (la classe potabile con
    garanzia);
  * `tab:veto-share` — quante regole **possono fare veto** `[V1]` e che quota rappresentano.

Questo script le ricalcola tutte e sedici le righe dai file dell'archivio e le confronta con i
valori stampati nella tesi. Non esegue RENUVER: le condizioni si valutano sulle regole piu' le
colonne che presentano valori mancanti nel dataset della famiglia (per Glass serve lo schema
corretto, che lo script prepara da solo in `.scratch/glass_fixed/`, cfr. il difetto di schema).

Uso:
    python3 pruning/verifica_condizioni.py
    python3 pruning/verifica_condizioni.py --solo bridges
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pruning as P                                        # noqa: E402
from paths import RENUVER, ROOT, SCRATCH                   # noqa: E402

GLASS_FIXED = os.path.join(SCRATCH, "glass_fixed")

# famiglia, soglia, dataset di riferimento, e i valori stampati nella tesi:
#   N, [V3] inerte, [V2] coperta, unione %, [V1] puo' fare veto
RIFERIMENTO = [
    ("bridges", 3, "bridges_14_1.csv", 1830, 2, 215, 11.9, 1818),
    ("bridges", 9, "bridges_14_1.csv", 8961, 6, 1531, 17.2, 8945),
    ("bridges", 15, "bridges_14_1.csv", 18844, 6, 3927, 20.9, 18828),
    ("glass", 3, "glass_22_1.csv", 1511, 5, 40, 3.0, 1476),
    ("glass", 9, "glass_22_1.csv", 11648, 18, 861, 7.5, 11564),
    ("glass", 15, "glass_22_1.csv", 27445, 24, 2363, 8.7, 27327),
    ("restaurant", 3, "restaurant_52_1.csv", 25, 0, 0, 0.0, 23),
    ("restaurant", 6, "restaurant_52_1.csv", 124, 0, 2, 1.6, 116),
]


def prepara_glass():
    """I dataset Glass dell'archivio hanno i nomi di colonna anonimizzati: serve la copia corretta."""
    ds = os.path.join(GLASS_FIXED, "Dataset", "glass_22_1.csv")
    if os.path.exists(ds):
        return True
    print("[nota] preparo i dataset Glass con lo schema corretto (.scratch/glass_fixed/)")
    cmd = [sys.executable, os.path.join(HERE, "fix_glass_schema.py"),
           "--output-dir", os.path.join(GLASS_FIXED, "Dataset"),
           "--tuple-dir", os.path.join(RENUVER, "TupleIniziali"),
           "--tuple-output-dir", os.path.join(GLASS_FIXED, "TupleIniziali")]
    rc = subprocess.run(cmd, cwd=ROOT).returncode
    if rc != 0 or not os.path.exists(ds):
        print("[errore] preparazione dei dataset Glass non riuscita"); return False
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Ricalcola le tabelle del capitolo 3 (nessuna esecuzione del sistema)")
    ap.add_argument("--solo", default=None,
                    help="limita a una famiglia (bridges, glass, restaurant)")
    args = ap.parse_args(argv)

    print("=" * 100)
    print("CONDIZIONI ESATTE [V1]/[V2]/[V3] — ricalcolo delle tabelle del capitolo 3 della tesi")
    print("=" * 100)
    if args.solo in (None, "glass") and not prepara_glass():
        return 1

    divergenze, righe = [], []
    for famiglia, soglia, ds_name, n_rif, v3_rif, v2_rif, un_rif, v1_rif in RIFERIMENTO:
        if args.solo and famiglia != args.solo:
            continue
        t0 = time.time()
        rfd = os.path.join(RENUVER, "RFD", f"output_false_{soglia}_{famiglia}.csv")
        ds = os.path.join(GLASS_FIXED, "Dataset", ds_name) if famiglia == "glass" \
            else os.path.join(RENUVER, "Dataset", ds_name)
        if not (os.path.isfile(rfd) and os.path.isfile(ds)):
            print(f"  [salto] {famiglia} @{soglia}: manca {os.path.relpath(rfd if not os.path.isfile(rfd) else ds, ROOT)}")
            continue
        raw = P.read_lines(rfd)
        h = raw[0].split(";")
        parsed = [p for p in (P.parse_rfd_row(h, l) for l in raw[1:]) if p]
        nullcols, _ = P.collect_null_columns([ds])
        n = len(parsed)
        inerti = {i for i, p in enumerate(parsed)
                  if not (set(p["lhs"]) & nullcols) and p["rhs"] not in nullcols}
        coperti = P.veto_covered_indices(parsed, max_extra=3, alive=None)
        v1 = sum(P.veto_bearing(parsed, nullcols))
        unione = len(inerti | coperti)
        un_pct = 100.0 * unione / n if n else 0.0
        v3_pct = 100.0 * len(inerti) / n if n else 0.0
        v1_pct = 100.0 * v1 / n if n else 0.0
        righe.append(dict(famiglia=famiglia, soglia=soglia, n=n, v3=len(inerti), v3_pct=v3_pct,
                          v2=len(coperti), v2_pct=100.0 * len(coperti) / n if n else 0.0,
                          unione=unione, un_pct=un_pct, v1=v1, v1_pct=v1_pct,
                          disgiunte=not (inerti & coperti), t=time.time() - t0))
        # confronto con la tesi (i conteggi esatti, le percentuali a meno di 0,1 punti)
        problemi = []
        if n != n_rif:
            problemi.append(f"N {n} != {n_rif}")
        if len(inerti) != v3_rif:
            problemi.append(f"[V3] {len(inerti)} != {v3_rif}")
        if len(coperti) != v2_rif:
            problemi.append(f"[V2] {len(coperti)} != {v2_rif}")
        if abs(un_pct - un_rif) > 0.06:
            problemi.append(f"unione {un_pct:.2f}% != {un_rif}%")
        if v1 != v1_rif:
            problemi.append(f"[V1] {v1} != {v1_rif}")
        if problemi:
            divergenze.append((famiglia, soglia, problemi))

    print("\ntab:conditions — classe potabile con garanzia")
    print(f"  {'caso':<16}{'N':>8}{'[V3] inerte':>14}{'[V2] coperta':>14}"
          f"{'unione':>9}{'quota':>8}   tesi")
    for r in righe:
        esito = "OK" if not any(d[0] == r["famiglia"] and d[1] == r["soglia"] for d in divergenze) else "DIVERGENZA"
        print(f"  {r['famiglia'] + ' @' + str(r['soglia']):<16}{r['n']:>8}"
              f"{r['v3']:>8} ({r['v3_pct']:.2f}%){r['v2']:>6} ({r['v2_pct']:.1f}%)"
              f"{r['unione']:>9}{r['un_pct']:>7.1f}%   {esito}")

    print("\ntab:veto-share — regole che possono fare veto [V1]")
    print(f"  {'caso':<16}{'N':>8}{'[V1]':>8}{'quota':>9}   tesi")
    for r in righe:
        esito = "OK" if not any(d[0] == r["famiglia"] and d[1] == r["soglia"] for d in divergenze) else "DIVERGENZA"
        print(f"  {r['famiglia'] + ' @' + str(r['soglia']):<16}{r['n']:>8}{r['v1']:>8}"
              f"{r['v1_pct']:>8.1f}%   {esito}")

    if all(r["disgiunte"] for r in righe):
        print("\n  [nota] [V3] e [V2] sono insiemi disgiunti su tutte le configurazioni: la quota "
              "dell'unione\n         e' la somma delle due, come nella tabella della tesi.")
    else:
        print("\n  [nota] su alcune configurazioni [V3] e [V2] si sovrappongono: la quota "
              "dell'unione non e'\n         la somma delle due quote (la tesi somma: va corretto).")

    if divergenze:
        print("\nESITO: divergenze rispetto alla tesi:")
        for famiglia, soglia, problemi in divergenze:
            print(f"  {famiglia} @{soglia}: " + "; ".join(problemi))
        return 1
    print(f"\nESITO: tutte e {len(righe)} le configurazioni coincidono con le tabelle del capitolo 3 "
          f"({sum(r['n'] for r in righe)} regole esaminate).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
