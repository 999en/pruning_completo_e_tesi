#!/usr/bin/env python3
"""
verify_veto.py — C: verifica EMPIRICA della condizione di copertura del veto [V2].

Il limite L4 del report: `veto-cover` e' dimostrato corretto per implicazione logica, ma il
comportamento di `isFaultless` non era mai stato confrontato, set completo contro set potato,
su stati reali del dataset.

COSA VERIFICA
-------------
`isFaultless` rifiuta un'imputazione di un valore `v` nella cella (t, a) se esiste una RFD in
`allRfd` con `a` nel LHS e una tupla `s` che:
    * concorda con t'(= t con a := v) su TUTTE le colonne del LHS, entro le soglie della RFD
      (colonne nulle su un lato non contano);
    * viola il RHS: |t'[RHS] - s[RHS]| > soglia_RHS  (per il testo, Levenshtein > soglia_RHS).

Lo script enumera **tutte** le terne (cella nulla, valore candidato, tupla s) e, per ciascuna,
confronta l'insieme delle RFD che farebbero scattare il veto nel set COMPLETO e in quello POTATO.

    discrepanza = esiste una RFD rimossa che scatta, e nessuna RFD rimasta che scatti.

Se non ci sono discrepanze, la condizione [V2] e' confermata empiricamente su quel dataset.
Se ce ne sono, lo script le riporta con la RFD coinvolta e la sua copritrice attesa.

Uso:
    python3 verify_veto.py \
        --rfd-full   RENUVER/RFD/output_false_9_bridges.csv \
        --rfd-pruned /percorso/pruned_9.csv \
        --dataset    RENUVER/Dataset/bridges_70_1.csv \
        --coltypes   "D,C,D,D,D,D,D,B,B,D,D,D,D" --maxthr 9 \
        --report
"""

from __future__ import annotations

import argparse
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import RENUVER, ensure_dirs                            # noqa: E402
from pruning import read_lines, parse_rfd_row, is_null, levenshtein, signature, read_dataset  # noqa: E402


# --------------------------------------------------------------------------- distanze (percorso VETO)
def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def col_agrees(c_type, v1, v2, thr, maxthr):
    """Replica della condizione per colonna in `areThereTuplesViolatingRFD`.
    Ritorna True se la colonna passa (conta verso thresholdPassed)."""
    if c_type == "B":
        if thr == maxthr:
            return v1 == v2                       # uguaglianza esatta di stringa
        return False                              # soglia diversa da maxthr: non incrementa mai
    if c_type == "C":
        if not v1 or not v2:
            return False
        return abs(ord(v1[0]) - ord(v2[0])) <= thr
    a, b = _num(v1), _num(v2)
    if a is not None and b is not None:
        return abs(a - b) <= thr
    return levenshtein(v1, v2) <= thr             # levenshtein3 non torna mai negativo


def rhs_violates(v1, v2, thr):
    """|v1 - v2| > thr, con fallback Levenshtein. True = violazione (il veto puo' scattare)."""
    a, b = _num(v1), _num(v2)
    if a is not None and b is not None:
        return abs(a - b) > thr
    return levenshtein(v1, v2) > thr


# --------------------------------------------------------------------------- copertura del veto
def veto_cover_map(parsed_full, keep_mask, max_extra=3):
    """Per ogni RFD rimossa, l'elenco degli indici delle RFD SOPRAVVISSUTE che ne implicano il veto.
    Stessa condizione di pruning.mask_veto_cover ([V2]): LHS sottoinsieme, soglie LHS >=,
    soglia RHS <=. Ritorna (cover: dict indice->lista indici, senza_copritrice: lista indici)."""
    alive = [i for i, k in enumerate(keep_mask) if k]
    buckets = collections.defaultdict(list)
    for i in alive:
        p = parsed_full[i]
        buckets[(p["rhs"], frozenset(p["lhs"]))].append(i)
    by_rhs = collections.defaultdict(set)
    for rhs, sk in buckets:
        by_rhs[rhs].add(sk)

    cover, uncovered = {}, []
    for i, k in enumerate(keep_mask):
        if k:
            continue
        r = parsed_full[i]
        S = frozenset(r["lhs"])
        found = []
        for T in by_rhs[r["rhs"]]:
            if T == S or not (T <= S) or len(S) - len(T) > max_extra or len(T) == 0:
                continue
            for j in buckets[(r["rhs"], T)]:
                q = parsed_full[j]
                if any(q["lhs"][c] < r["lhs"][c] for c in T):
                    continue
                if q["rhs_thr"] > r["rhs_thr"]:
                    continue
                found.append(j)
        if found:
            cover[i] = found
        else:
            uncovered.append(i)
    return cover, uncovered


# --------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description="Verifica empirica della copertura del veto [V2].")
    ap.add_argument("--rfd-full", required=True, help="set RFD completo (riferimento)")
    ap.add_argument("--rfd-pruned", required=True, help="set RFD potato da veto-cover")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--coltypes", default=None, help="tipi di colonna (args0 di RENUVER)")
    ap.add_argument("--maxthr", type=int, default=None, help="args[4] di RENUVER")
    ap.add_argument("--max-cells", type=int, default=None, help="limita il numero di celle nulle")
    ap.add_argument("--max-values", type=int, default=None, help="limita i valori candidati per cella")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args(argv)
    ensure_dirs()

    try:
        import numpy as np
    except ImportError:                                     # pragma: no cover
        sys.exit("[errore] `verify_veto.py` usa numpy (matrici di distanza n x n): e' uno dei\n"
                 "         due soli script del pacchetto che ne hanno bisogno. Le verifiche di\n"
                 "         equivalenza principali non dipendono da questo script: vedi\n"
                 "         `pruning/audit_report.py` e i controlli di `verifica_completa.sh`.")

    # ---- caricamento -------------------------------------------------------------
    hf, _, bf = read_lines(args.rfd_full)[0].split(";"), None, read_lines(args.rfd_full)[1:]
    hp, _, bp = read_lines(args.rfd_pruned)[0].split(";"), None, read_lines(args.rfd_pruned)[1:]
    full, pruned = [], set()
    for l in bf:
        p = parse_rfd_row(hf, l)
        if p:
            full.append(p)
    for l in bp:
        p = parse_rfd_row(hp, l)
        if p:
            pruned.add(signature(p))
    removed = [(i, p) for i, p in enumerate(full) if signature(p) not in pruned]
    print("=" * 92)
    print("VERIFICA EMPIRICA DELLA COPERTURA DEL VETO [V2]")
    print("=" * 92)
    print(f"RFD nel set completo : {len(full)}")
    print(f"RFD nel set potato   : {len(pruned)}")
    print(f"RFD rimosse          : {len(removed)}")

    attrs, dsrows = read_dataset(args.dataset)
    n = len(dsrows)
    if args.coltypes:
        ct = args.coltypes.split(",")
    else:
        ct = ["D"] * len(attrs)
    types = {a: (ct[i] if i < len(ct) else "D") for i, a in enumerate(attrs)}
    maxthr = args.maxthr
    if maxthr is None:
        maxthr = int(max(p["rhs_thr"] for p in full))
    print(f"dataset              : {os.path.basename(args.dataset)} ({n} righe)")
    print(f"maxthr               : {maxthr}")

    # ---- indici colonne ----------------------------------------------------------
    idx = {a: i for i, a in enumerate(attrs)}
    vals = [[(r.get(a) or "") for a in attrs] for r in dsrows]

    null_cells = [(i, a) for i in range(n) for a in attrs if is_null(vals[i][idx[a]])]
    if args.max_cells:
        null_cells = null_cells[:args.max_cells]
    print(f"celle nulle da verificare: {len(null_cells)}")

    # ---- per ogni attributo: RFD rimosse e RFD rimaste che lo hanno nel LHS ------
    def pack(rfds_with_a):
        """Prepara gli array numpy per un gruppo di RFD che hanno l'attributo `a` nel LHS."""
        R = len(rfds_with_a)
        lhs_cols = sorted({c for _, p in rfds_with_a for c in p["lhs"]})
        ci = {c: k for k, c in enumerate(lhs_cols)}
        thr = np.full((R, len(lhs_cols)), -np.inf)
        mask = np.zeros((R, len(lhs_cols)), dtype=bool)
        ridx = np.zeros(R, dtype=np.int64)
        rthr = np.zeros(R)
        for row, (_, p) in enumerate(rfds_with_a):
            for c, t in p["lhs"].items():
                thr[row, ci[c]] = t
                mask[row, ci[c]] = True
            ridx[row] = idx[p["rhs"]]
            rthr[row] = p["rhs_thr"]
        return dict(R=R, cols=lhs_cols, ci=ci, thr=thr, mask=mask, ridx=ridx, rthr=rthr,
                    rfds=rfds_with_a)

    # maschera di sopravvivenza nel set potato
    sig_pruned = pruned
    keep_mask = [signature(p) in sig_pruned for p in full]
    cover, uncovered = veto_cover_map(full, keep_mask)
    print(f"RFD rimosse senza copritrice [V2]: {len(uncovered)}")
    if uncovered:
        for i in uncovered[:5]:
            print(f"   ! {full[i]['rhs']} thr={full[i]['rhs_thr']} lhs={full[i]['lhs']}")
    print()
    print("-" * 92)

    checks = 0
    removed_fired = 0
    discrepancies = []
    per_attr = collections.Counter()
    tested_cells = 0
    # RFD rimaste (non potate) per attributo del LHS: serve solo al riepilogo finale
    kept_per_attr = collections.Counter(c for i in range(len(full)) if keep_mask[i]
                                        for c in full[i]["lhs"])

    for a in attrs:
        rem_a = [(i, full[i]) for i in range(len(full))
                 if not keep_mask[i] and a in full[i]["lhs"]]
        if not rem_a:
            continue
        # unione delle copritrici di tutte le RFD rimosse di questo attributo
        cov_idx = sorted({c for i, _ in rem_a for c in cover.get(i, [])})
        if not cov_idx:
            continue
        P_rem = pack(rem_a)
        P_kept = pack([(i, full[i]) for i in cov_idx])
        per_attr[a] = [len(rem_a), kept_per_attr.get(a, 0)]

        distinct = sorted({vals[i][idx[a]] for i in range(n) if not is_null(vals[i][idx[a]])})
        if args.max_values:
            distinct = distinct[:args.max_values]

        for ti, ta in [(i, x) for i, x in null_cells if x == a]:
            tested_cells += 1
            base = list(vals[ti])
            for v in distinct:
                t = list(base)
                t[idx[a]] = v
                cols_need = set(P_rem["cols"]) | set(P_kept["cols"])
                d_lhs, d_rhs = {}, {}
                for c in cols_need:
                    ci_ = idx[c]
                    tv = t[ci_]
                    dl = np.full(n, np.inf)
                    dr = np.full(n, np.inf)
                    for j in range(n):
                        sv = vals[j][ci_]
                        if is_null(sv) or is_null(tv):
                            continue
                        if types.get(c, "D") == "C":
                            dl[j] = abs(ord(tv[0]) - ord(sv[0])) if tv and sv else np.inf
                        else:
                            na, nb = _num(tv), _num(sv)
                            dl[j] = abs(na - nb) if (na is not None and nb is not None) \
                                else levenshtein(tv, sv)
                        na, nb = _num(tv), _num(sv)
                        dr[j] = abs(na - nb) if (na is not None and nb is not None) \
                            else levenshtein(tv, sv)
                    d_lhs[c] = dl
                    d_rhs[c] = dr
                for c in cols_need:                       # regola speciale delle colonne 'B'
                    if types.get(c, "D") == "B":
                        ci_ = idx[c]
                        tv = t[ci_]
                        d_lhs[c] = np.array([0.0 if (not is_null(vals[j][ci_]) and vals[j][ci_] == tv)
                                             else np.inf for j in range(n)])

                def fire_matrix(P):
                    ok = np.ones((P["R"], n), dtype=bool)
                    for k, c in enumerate(P["cols"]):
                        cond = d_lhs[c][None, :] <= P["thr"][:, k, None]
                        if types.get(c, "D") == "B":
                            cond = cond & (P["thr"][:, k] == maxthr)[:, None]
                        ok &= np.where(P["mask"][:, k][:, None], cond, True)
                    viol = np.zeros((P["R"], n), dtype=bool)
                    for row in range(P["R"]):
                        viol[row, :] = d_rhs[attrs[P["ridx"][row]]] > P["rthr"][row]
                    return ok & viol

                FR = fire_matrix(P_rem)
                FR[:, ti] = False                       # Tuple.equals esclude s = t
                if not FR.any():
                    continue
                FK = fire_matrix(P_kept)
                FK[:, ti] = False
                pos = {gi: r for r, gi in enumerate(cov_idx)}           # indice globale -> riga
                for r in range(P_rem["R"]):
                    rows = np.where(FR[r])[0]
                    if rows.size == 0:
                        continue
                    removed_fired += int(rows.size)
                    checks += int(rows.size)
                    covs = cover.get(rem_a[r][0], [])
                    if not covs:
                        discrepancies.append((rem_a[r][1]["rhs"], "senza copritrice", int(rows[0])))
                        continue
                    sub = FK[[pos[c] for c in covs if c in pos]][:, rows]
                    bad = rows[~sub.any(axis=0)] if sub.size else rows
                    for j in bad[:5]:
                        discrepancies.append((ti, a, v, int(j), rem_a[r][1]["rhs"],
                                              round(rem_a[r][1]["rhs_thr"], 3)))

    print()
    print("-" * 92)
    print(f"terne (cella, valore, tupla s) in cui una RFD RIMOSSA farebbe scattare il veto: {checks}")
    print(f"discrepanze (veto perso): {len(discrepancies)}")
    if args.report:
        print()
        print("RFD rimosse / rimaste con l'attributo nel LHS, per attributo:")
        for a, (r, k) in sorted(per_attr.items(), key=lambda kv: (-kv[1][0], kv[0])):
            if r or k:
                print(f"   {a:<14} rimosse={r:<6} rimaste={k}")
    if discrepancies:
        print()
        print("prime discrepanze:")
        for d in discrepancies[:10]:
            print(f"   {d}")
        print("\nESITO: [V2] NON verificata su questo dataset.")
        return 1
    print("\nESITO: nessuna discrepanza -> la condizione [V2] e' verificata empiricamente.")
    if checks == 0:
        print("[avviso] nessun veto esercitato dalle RFD rimosse: il test e' vacuo su questo dataset.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
