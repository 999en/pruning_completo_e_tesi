#!/usr/bin/env python3
"""verifica_tetto.py — il tetto di [V2] e' intrinseco al criterio o dipende da `max_extra`?

La ricerca delle regole coprenti di [V2] ha un parametro `max_extra` che limita di quante colonne
il LHS del copritore puo' essere piu' piccolo. E' una scelta di *ricerca*, non di correttezza: il
teorema resta valido per qualunque valore. Questo script ricalcola, dai soli file di regole
dell'archivio, quante RFD rimuove `veto-cover` al variare di `max_extra`, e confronta il totale con
i valori della tabella del §1.4 della relazione tecnica (richiamata nel capitolo 4 della tesi,
sezione «Quanto e' stretto il limite»).

Risultato atteso: la riduzione e' **piatta** da `max_extra` = 3 a 20 — una sola RFD in piu' su
8 939 (Bridges a soglia 15). Il tetto della potatura certificata e' quindi una proprieta' del
criterio, non del suo parametro di ricerca.

Nessuna esecuzione di RENUVER e nessun dataset: la condizione [V2] si valuta sulle regole.

Uso:
    python3 pruning/verifica_tetto.py                     # valori 3 e 20 (circa un minuto)
    python3 pruning/verifica_tetto.py --valori 3,4,5,6,8,10,15,20
"""
from __future__ import annotations

import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pruning as P                                        # noqa: E402
from paths import RENUVER                                  # noqa: E402

# (famiglia, soglia): valori della tabella del §1.4 della relazione
#   N regole, rimosse con max_extra = 3, rimosse con max_extra = 20
RIFERIMENTO = {
    ("bridges", 3): (1830, 215, 215),
    ("bridges", 9): (8961, 1531, 1531),
    ("bridges", 15): (18844, 3927, 3928),
    ("glass", 3): (1511, 40, 40),
    ("glass", 9): (11648, 861, 861),
    ("glass", 15): (27445, 2363, 2363),
    ("restaurant", 3): (25, 0, 0),
    ("restaurant", 6): (124, 2, 2),
}


def carica(famiglia, soglia):
    """Regole del file RFD dell'archivio: [(indice, riga, campi)] con i campi gia' interpretati."""
    path = os.path.join(RENUVER, "RFD", f"output_false_{soglia}_{famiglia}.csv")
    if not os.path.isfile(path):
        sys.exit(f"[errore] file di regole assente: {path}")
    righe = P.read_lines(path)
    header = righe[0].split(";")
    parsed = []
    for i, riga in enumerate(righe[1:]):
        p = P.parse_rfd_row(header, riga)
        if p is not None:
            parsed.append(p)
    return parsed


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Il tetto di [V2] dipende da max_extra? (nessuna esecuzione del sistema)")
    ap.add_argument("--valori", default="3,20",
                    help="valori di max_extra da confrontare (default: 3,20)")
    args = ap.parse_args(argv)
    valori = [int(v) for v in args.valori.split(",")]
    if 3 not in valori:
        valori = [3] + valori

    print("=" * 96)
    print("TETTO DELLA POTATURA CERTIFICATA [V2] — effetto del parametro di ricerca max_extra")
    print("=" * 96)
    print(f"{'caso':<16}{'N':>8}" + "".join(f"{'me=' + str(v):>10}" for v in valori)
          + f"{'delta':>8}   riferimento §1.4")
    tot = {v: 0 for v in valori}
    divergenze = []
    for famiglia, soglia in RIFERIMENTO:
        t0 = time.time()
        parsed = carica(famiglia, soglia)
        n_rif, me3_rif, me20_rif = RIFERIMENTO[(famiglia, soglia)]
        rimozioni = {}
        for v in valori:
            rimozioni[v] = len(P.veto_covered_indices(parsed, max_extra=v))
            tot[v] += rimozioni[v]
        delta = rimozioni[max(valori)] - rimozioni[min(valori)]
        # confronto con la tabella della relazione
        atteso = []
        if 3 in valori:
            atteso.append(rimozioni[3] == me3_rif)
        if 20 in valori:
            atteso.append(rimozioni[20] == me20_rif)
        esito = "OK" if all(atteso) and len(parsed) == n_rif else "DIVERGENZA"
        if esito == "DIVERGENZA":
            divergenze.append(f"{famiglia}@{soglia}")
        print(f"{famiglia + ' @' + str(soglia):<16}{len(parsed):>8}"
              + "".join(f"{rimozioni[v]:>10}" for v in valori)
              + f"{delta:>+8}   {esito}  (N={n_rif}, me3={me3_rif}, me20={me20_rif})"
              + f"  [{time.time() - t0:.1f}s]")
    print("-" * 96)
    print(f"{'totale':<16}{'':>8}" + "".join(f"{tot[v]:>10}" for v in valori)
          + f"{tot[max(valori)] - tot[min(valori)]:>+8}   "
          + f"(tabella: {sum(v[1] for v in RIFERIMENTO.values())} -> "
          + f"{sum(v[2] for v in RIFERIMENTO.values())})")
    print()
    if divergenze:
        print(f"ESITO: {len(divergenze)} casi divergenti dalla tabella del §1.4: {divergenze}")
        return 1
    print("ESITO: la riduzione e' piatta al variare di max_extra su tutti i casi; il totale "
          "coincide\n       con la tabella del §1.4 della relazione: il tetto e' intrinseco al "
          "criterio [V2].")
    return 0


if __name__ == "__main__":
    sys.exit(main())
