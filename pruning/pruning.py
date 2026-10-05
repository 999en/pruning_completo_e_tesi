#!/usr/bin/env python3
"""
pruning.py — Semantic Pruning esterno per RENUVER.

Pre-processa un file di RFD e ne produce una versione ridotta, senza toccare RENUVER_EDBT.jar.
Il file ridotto ha lo stesso formato e lo stesso header dell'originale.

    python3 pruning.py \
        --rfd      RENUVER/RFD/output_false_15_bridges.csv \
        --dataset  RENUVER/Dataset/bridges_70_1.csv \
        --ground-truth RENUVER/TupleIniziali/bridges_70_1.csv \
        --output   RENUVER/RFD/pruned_output_false_15_bridges.csv \
        --strategy veto-dominance,dom-sub,inert,duplicates \
        --veto-policy protect \
        --report


=====================================================================================
PERCHE' QUESTO PRUNER E' "VETO-AWARE"
=====================================================================================
In RENUVER una RFD ha DUE ruoli distinti, entrambi implementati nello stesso oggetto:

  (G) GENERAZIONE — in `getCandidatesForField` le RFD del cluster delimitano quali tuple
      possono candidarsi a donare il valore, e competono fra loro per il punteggio minore.

  (V) VETO — in `isFaultless` OGNI RFD di `allRfd` il cui LHS contiene l'attributo che si sta
      imputando puo' RIFIUTARE l'imputazione, se esiste una tupla che concorda sul LHS e viola
      il RHS. Effetto collaterale permanente: i candidati in disaccordo vengono disattivati
      (`careAbout = false`).

Rimuovere una RFD non toglie quindi solo un generatore: puo' togliere un vincolo di coerenza,
e il sistema accetta di piu' — spesso a torto. Misurato su Restaurant: -2 RFD => +22 imputazioni,
+23 errori.

-------------------------------------------------------------------------------------
CONDIZIONI ESATTE (dimostrate sul bytecode, non euristiche)
-------------------------------------------------------------------------------------
Sia  NullCols = { colonne che contengono almeno un "?" nel dataset }.
Una cella puo' essere imputata solo se il suo attributo sta in NullCols: quindi
`populated.getKey()` in isFaultless appartiene sempre a NullCols.

  [V1] "NON PUO' FARE VETO"
       LHS(r) INTERSECATO NullCols = vuoto
       => nessuna colonna del LHS puo' mai coincidere con l'attributo imputato
       => r non entra mai nel ramo di rifiuto di isFaultless.
       (Verificato: e' una condizione necessaria e sufficiente.)

  [V2] "VETO IMPLICATO DA UN'ALTRA RFD"  (preserva il veto anche rimuovendo r)
       esiste r'' con:
           LHS(r'') SOTTOINSIEME di LHS(r)   (r'' vincola su MENO colonne: scatta piu' spesso)
           soglia(r'',c) >= soglia(r,c)      per ogni c in LHS(r'')   (soglie piu' LARGHE)
           soglia_RHS(r'') <= soglia_RHS(r)                            (RHS piu' STRETTO)
       Dimostrazione: se r scatta, esiste una tupla s che concorda con t su TUTTO LHS(r) e viola
       la soglia RHS di r. Essendo LHS(r'') sottoinsieme di LHS(r), s concorda anche su LHS(r'')
       (le soglie di r'' sono piu' larghe); ed essendo soglia_RHS(r'') <= soglia_RHS(r), la
       violazione di r e' anche una violazione di r''. Dunque r che scatta implica r'' che
       scatta: il veto di r e' ridondante e r e' rimovibile.
       ATTENZIONE alla direzione: il copritore ha il LHS PIU' PICCOLO. La direzione opposta
       (copritore con LHS sovrainsieme, soglie piu' strette) e' quella della variante storica
       `veto-dominance`, deprecata: non e' quella implementata da `veto-cover`.

  [V3] "PROVABILMENTE INERTE"  => rimozione sicura al 100%
       LHS(r) INTERSECATO NullCols = vuoto   (non puo' fare veto, [V1])
       E  RHS(r) NON in NullCols             (la sua colonna non e' mai mancante, quindi
                                              non entra mai in `rfdForRHS`: non genera mai)

  ATTENZIONE — la classe [V3] e' quasi vuota: su Bridges solo ID e RIVER non sono mai nulli,
  per cui [V3] rimuove lo 0,1-0,7% delle RFD. NON esiste un pruning non banale che sia
  contemporaneamente sicuro su generazione e veto. Da qui la necessita' di misurare.

-------------------------------------------------------------------------------------
STRATEGIE DISPONIBILI (--strategy, lista separata da virgole, applicate in sequenza)
-------------------------------------------------------------------------------------
  duplicates      righe RFD byte-identiche                              [sicura]
  inert           condizione [V3]                                       [provabilmente sicura]
  veto-cover      condizione [V2] - ogni veto rimosso e' implicato da una RFD che sopravvive.
                  MISURATO: output IDENTICO al baseline in 20/20 configurazioni, riduzione 12-21%.
                  E' l'unica strategia esatta.
  coverage        nessuna cella nulla del dataset puo' attivarla
                  MISURATO: esatto sulla generazione, nessuna regressione, riduzione 21-46%.
  dom-sub         esiste r' con LHS(r') SOTTOINSIEME stretto di LHS(r),
                  soglie(r') <= soglie(r) sulle condivise, soglia_RHS(r') <= soglia_RHS(r)
                  Rimuove le RFD PIU' SPECIFICHE. Aggressiva: NON preserva i veti.
                  MISURATO: riduzione 67-90%, tempi 2,6-13x migliori, -8,4..-9,8% di corrette.
                  E' il miglior compromesso valore/rischio.
  dom-sub-strict  come dom-sub ma con soglie STRETTAMENTE piu' piccole su tutte le condivise
                  MISURATO: PEGGIORE di dom-sub (-14..-17% di corrette) pur rimuovendo meno.
  dom-exact       dominanza fra RFD con lo STESSO insieme di attributi LHS
  rhs-thr         soglia RHS > --max-rhs-thr                             [mira alla precisione]
  lhs-cap         |LHS| > --max-lhs
  used            RFD mai usata come vincitrice in nessun run di training
                  (data-driven; usare --exclude per il leave-one-out)
                  MISURATO: riduzione 92-99% ma DISTRUGGE la precisione (fino a -15 punti),
                  perche' rimuove i vincoli di coerenza di isFaultless -> sconsigliata.
  empirical       RFD con >= --min-uses usi e accuratezza < --min-acc nel training
  hybrid          pipeline: duplicates,inert,veto-cover,dom-sub,used,empirical
                  MISURATO: la peggiore (-23 punti di accuracy) -> sconsigliata.
  veto-dominance  DEPRECATA: implementa la direzione di implicazione INVERTITA
                  (richiede soglie piu' strette invece che piu' larghe). Usare veto-cover.

-------------------------------------------------------------------------------------
RISULTATI MISURATI SU BRIDGES (125 configurazioni, 5 livelli di missing x 5 run x 5 soglie)
-------------------------------------------------------------------------------------
  veto-cover      riduzione 12-21% | output IDENTICO al baseline in 20/20 configurazioni
                  -> e' l'unica strategia esatta: usarla quando non si puo' perdere nulla
  coverage        riduzione 21-46% | nessuna regressione
  dom-sub         riduzione 67-90% | tempi 2,6-13x migliori | -8,4..-9,8% di imputazioni corrette
                  -> miglior compromesso; perdita di accuratezza -3,1..-4,3 punti percentuali
  dom-sub-strict  riduzione 61-67% | PEGGIORE di dom-sub (-14..-17% di corrette)
  used            riduzione 92-99% | DISTRUGGE la precisione (fino a -15 punti) perche' rimuove
                  i vincoli di coerenza di isFaultless -> sconsigliata
  hybrid          riduzione 99%+   | la peggiore (-23 punti di accuracy) -> sconsigliata
  veto-dominance  DEPRECATA (direzione di implicazione invertita): usare veto-cover

-------------------------------------------------------------------------------------
POLITICA SUI VETI (--veto-policy)
-------------------------------------------------------------------------------------
  protect   (default) ogni RFD che soddisfa [V1] viene RIPRISTINATA: il potere di veto resta
            integralmente intatto. Riduzione attesa: piccola.
  allow     nessuna restrizione: si accetta la perdita di veti. Massima riduzione, rischio alto.
  budget:F  si rimuovono al piu' una frazione F (0..1) delle RFD portatrici di veto,
            scegliendo prima quelle con esposizione minore (meno celle nulle coperte dal LHS).
"""

from __future__ import annotations

import argparse
import collections
import glob
import os
import re
import sys

NULL_TOKENS = {"?", "", "null", "NULL", "NA", "nan", "NaN", "None"}
STRATEGIES = ["duplicates", "inert", "veto-cover", "veto-dominance", "coverage", "dom-sub",
              "dom-sub-strict", "dom-sub-adaptive", "score-argmin", "exact-priority",
              "precision-priority", "intra-cluster-priority", "dom-exact",
              "rhs-thr", "lhs-cap", "used", "empirical", "hybrid", "auto",
              "classical-cover"]

# `auto` sceglie fra il teorema esatto e l'euristica in base alla quota di celle nulle che
# stanno in tuple con >= 2 nulli. Vedi la nota di progetto sopra `null_multi_share`.
AUTO_THRESHOLD = 0.50


# =====================================================================================
# I/O
# =====================================================================================
def _fmt_alpha(a):
    return f"{a:.2f}".rstrip("0").rstrip(".")


def is_null(v: str) -> bool:
    return v in NULL_TOKENS


def read_lines(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return [l.rstrip("\n").rstrip("\r") for l in fh if l.strip()]


def read_dataset(path, sep=";"):
    lines = read_lines(path)
    header = lines[0].split(sep)
    rows = []
    for l in lines[1:]:
        cells = l.split(sep)
        rows.append({a: (cells[i].strip() if i < len(cells) else "") for i, a in enumerate(header)})
    return header, rows


def parse_rfd_row(header, line):
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


def signature(p):
    """Identita' semantica di una RFD: (RHS, soglia RHS, LHS con soglie)."""
    return (p["rhs"], round(float(p["rhs_thr"]), 9),
            tuple(sorted((c, round(float(t), 9)) for c, t in p["lhs"].items())))


# =====================================================================================
# CONTESTO: colonne nulle e statistiche di training
# =====================================================================================
def collect_null_columns(dataset_paths):
    """NullCols = unione delle colonne con almeno un '?' su tutti i dataset indicati."""
    nullcols, profiles = set(), collections.Counter()
    for path in dataset_paths:
        header, rows = read_dataset(path)
        for r in rows:
            for a in header:
                if is_null(r[a]):
                    nullcols.add(a)
                    profiles[a] += 1
    return nullcols, profiles


def null_multi_share(attrs, rows):
    """Quota di celle nulle che stanno in tuple con >= 2 celle nulle.

    E' il criterio su cui `auto` decide, ed e' una proprieta' del DATASET, non del file RFD.

    Perche' non si usa il numero di RFD (N). La verifica sui dati raccolti mostra che nessuno
    scalare ricavato dal file RFD separa i casi in cui l'euristica `dom-sub-adaptive` conviene
    da quelli in cui danneggia:

        caso          N       RFD residue   esito di A5b
        bridges @9    8 961   1 668         aiuta  (+19 corrette)
        glass   @9   11 648   1 352         nuoce  (-17 corrette)
        bridges @15  18 844   2 379         aiuta  (+26 corrette)
        glass   @15  27 445   1 856         nuoce  (-17 corrette)

    L'ordine per N e' invertito rispetto all'esito (glass @9 ha piu' RFD di bridges @9 e vuole
    il trattamento opposto), e lo stesso vale per la percentuale di riduzione e per il numero
    assoluto di RFD residue: glass @15 ne conserva 1 856 e peggiora, bridges @9 ne conserva
    1 668 e migliora. Non esiste quindi una soglia su N che separi i due regimi.

    Separa invece la quota di celle nulle in tuple multi-nullo, perche' e' quella che determina
    quale dei due rami di `treatNullTuple` domina:

        bridges     76,3%   -> ramo multi-cella dominante   -> l'euristica aiuta
        glass       26,1%   -> ramo mono-cella dominante    -> l'euristica danneggia
        restaurant  12,3%   -> ramo mono-cella dominante    -> l'euristica danneggia

    Ritorna (quota, celle_nulle_totali, celle_in_tuple_multi_nullo).
    """
    tot = multi = 0
    for r in rows:
        n = sum(1 for a in attrs if is_null(r[a]))
        tot += n
        if n >= 2:
            multi += n
    return (multi / tot if tot else 0.0), tot, multi


def load_training_stats(results_dir, populated_dir, family_prefix, exclude=None):
    """Ritrova, dai file Results/ + Populated/ di run GIA' ESEGUITI, per ogni RFD:
           usi totali, imputazioni corrette, di cui 'exact'.
    `exclude` e' una regex sui nomi file da NON usare (leave-one-out)."""
    stats = collections.defaultdict(lambda: {"uses": 0, "correct": 0, "exact": 0})
    if not results_dir or not os.path.isdir(results_dir):
        return stats
    ex = re.compile(exclude) if exclude else None

    truth_cache = {}

    def truth_for(base, thr):
        key = (base, thr)
        if key in truth_cache:
            return truth_cache[key]
        cands = [f"output_{base}_{thr}H0.csv", f"results_{thr}_{base}"]
        t = {}
        for c in cands:
            p = os.path.join(populated_dir or "", c)
            if os.path.exists(p):
                for i, line in enumerate(open(p, encoding="utf-8", errors="replace")):
                    q = line.rstrip("\n").split(";")
                    if i == 0 and q[0].lower().startswith("riga"):
                        continue
                    if len(q) >= 4:
                        t[(q[0].strip(), q[1].strip())] = (q[2].strip(), q[3].strip())
                break
        truth_cache[key] = t
        return t

    RHS_PAT = re.compile(r"\[([^\[\]]*)\]\s*->\s*\(([^)]+)\)_([-\d.]+)\s*;(.*)$")
    for fname in sorted(os.listdir(results_dir)):
        if not fname.endswith(".txt") or fname.startswith("._"):
            continue
        if family_prefix and family_prefix not in fname:
            continue
        if ex and ex.search(fname):
            continue
        m = re.match(r"^output_(?P<base>.+)_(?P<thr>\d+)H\d+\.txt$", fname)
        if not m:
            continue
        base, thr = m["base"], int(m["thr"])
        truth = truth_for(base, thr)
        for line in open(os.path.join(results_dir, fname), encoding="utf-8", errors="replace"):
            mm = RHS_PAT.search(line)
            if not mm:
                continue
            # il campo imputato e' il secondo token
            parts = line.split(";")
            if len(parts) < 2 or ":" not in parts[1]:
                continue
            attr = parts[1].split(":")[0].strip()
            row = parts[0].strip()
            try:
                lhs = {c.strip(): float(t) for c, t in
                       re.findall(r"\(([^)]+)\)_([-\d.]+)", mm.group(1))}
            except ValueError:
                continue
            rhs, rhs_thr = mm.group(2).strip(), float(mm.group(3))
            exact = mm.group(4).strip() == "exact"
            k = (rhs, round(rhs_thr, 9), tuple(sorted((c, round(t, 9)) for c, t in lhs.items())))
            st = stats[k]
            st["uses"] += 1
            if exact:
                st["exact"] += 1
            gt = truth.get((row, attr))
            if gt and gt[1] not in ("?", ""):
                try:
                    ok = gt[0] == gt[1] or abs(float(gt[0]) - float(gt[1])) < 1e-9
                except ValueError:
                    ok = gt[0] == gt[1]
                st["correct"] += 1 if ok else 0
    return stats


# =====================================================================================
# MASCHERE — ogni funzione ritorna una lista di bool (True = TENERE)
# =====================================================================================
def mask_duplicates(parsed, raws, **_):
    seen, keep = set(), []
    for p, raw in zip(parsed, raws):
        s = signature(p)
        keep.append(s not in seen)
        seen.add(s)
    return keep


def mask_inert(parsed, nullcols, **_):
    """[V3] non puo' fare veto E non puo' generare -> rimozione sicura al 100%."""
    return [not (not (set(p["lhs"]) & nullcols) and p["rhs"] not in nullcols) for p in parsed]


def mask_classical_cover(parsed, **_):
    """Ridondanza CLASSICA: X -> A e' superflua se esiste Y -> A con Y sottoinsieme proprio di X.

    E' il criterio della teoria delle dipendenze funzionali (X -> A si deriva da Y -> A per
    augmentazione) applicato letteralmente alle RFD: le soglie vengono ignorate, perche' la
    nozione classica di ridondanza e' dichiarativa e non conosce tolleranze. Serve come termine di
    paragone: mostra che cosa accade quando la direzione delle soglie non viene considerata.
    """
    by_rhs = {}
    for i, p in enumerate(parsed):
        by_rhs.setdefault(p["rhs"], []).append(i)
    keep = [True] * len(parsed)
    for idx in by_rhs.values():
        for i in idx:
            lhs_i = set(parsed[i]["lhs"])
            for j in idx:
                if i == j:
                    continue
                lhs_j = set(parsed[j]["lhs"])
                if lhs_j and lhs_j < lhs_i:
                    keep[i] = False
                    break
    return keep


def mask_veto_cover(parsed, max_extra=3, alive=None, **_):
    """[V2] COPERTURA DEL VETO — l'unica direzione che preserva il potere di veto.

    `r` viene rimossa se esiste `r''` con:
        stesso attributo RHS;
        LHS(r'') SOTTOINSIEME di LHS(r)   (al piu' `max_extra` colonne in meno, non vuoto);
        soglia_{r''}(c) >= soglia_r(c)    per ogni c in LHS(r'')   [soglie PIU' LARGHE];
        soglia_RHS(r'') <= soglia_RHS(r)                            [RHS PIU' STRETTO].

    In tal caso ogni veto di `r` e' implicato da un veto di `r''`: se `r''` rifiuta, allora
    esiste una tupla che concorda su LHS(r'') (quindi anche su LHS(r), che e' piu' grande) e
    viola la soglia RHS di r'' (quindi anche quella, piu' larga, di r).

    Punto fisso: si rimuove `r` solo se almeno un suo copritore sopravvive, altrimenti due RFD
    che si coprono a vicenda sparirebbero entrambe.

    `alive` (lista di bool, opzionale) e' l'insieme CORRENTE delle RFD non ancora rimosse da altre
    strategie. Va passato obbligatoriamente quando `veto-cover` non e' la prima strategia della
    pipeline: la garanzia [V2] vale solo se il copritore sopravvive **alla fine**, e una strategia
    successiva puo' rimuoverlo. Senza `alive` la copertura e' valutata sull'insieme originale e il
    teorema puo' risultare invalido (vedi `veto_covered_indices`)."""
    covered = veto_covered_indices(parsed, max_extra=max_extra, alive=alive)
    return [i not in covered for i in range(len(parsed))]


def veto_covered_indices(parsed, max_extra=3, alive=None):
    """Insieme degli indici rimovibili per [V2] dato l'insieme `alive` delle RFD sopravvissute.

    Ritorna un `set` di indici. E' il nucleo condiviso fra `mask_veto_cover` e la politica sui
    veti: entrambi devono usare la STESSA nozione di "veto coperto", altrimenti il budget viene
    addebitato per rimozioni che il teorema ha gia' dimostrato gratuite.
    """
    if alive is None:
        alive = [True] * len(parsed)
    buckets = collections.defaultdict(list)
    for i, p in enumerate(parsed):
        buckets[(p["rhs"], frozenset(p["lhs"]))].append(i)
    by_rhs = collections.defaultdict(set)
    for rhs, s in buckets:
        by_rhs[rhs].add(s)

    cover = {}
    for i, r in enumerate(parsed):
        S = frozenset(r["lhs"])
        cov = []
        for T in by_rhs[r["rhs"]]:
            if T == S or not (T <= S) or len(S) - len(T) > max_extra or len(T) == 0:
                continue
            for j in buckets[(r["rhs"], T)]:
                if j == i or not alive[j]:
                    continue               # copritore caduto: la garanzia [V2] non vale
                q = parsed[j]
                if any(q["lhs"][c] < r["lhs"][c] for c in T):
                    continue
                if q["rhs_thr"] > r["rhs_thr"]:
                    continue
                cov.append(j)
        if cov:
            cover[i] = cov

    # Nota: il candidato `r` viene valutato anche se NON e' piu' vivo. Serve a classificare
    # come "gratuite" le rimozioni gia' effettuate da altre strategie, che la politica sui veti
    # non deve addebitare al budget. `mask_veto_cover` non le resuscita, perche' il chiamante
    # combina la maschera con AND.
    removable = set(cover)
    changed = True
    while changed:
        changed = False
        for r in list(removable):
            # un copritore vale solo se sopravvive: ne' morto, ne' rimosso da questa potatura
            if all((c in removable) or (not alive[c]) for c in cover[r]):
                removable.discard(r)
                changed = True
    return removable


def mask_dom_sub_strict(parsed, **_):
    """`dom-sub` conservativa: il dominatore deve avere LHS sottoinsieme stretto E soglie
    STRETTAMENTE piu' piccole su tutte le colonne condivise E soglia RHS <=.
    Nessun limite alla differenza di dimensione del LHS."""
    buckets = collections.defaultdict(list)
    for i, p in enumerate(parsed):
        buckets[(p["rhs"], frozenset(p["lhs"]))].append(i)
    by_rhs = collections.defaultdict(set)
    for rhs, s in buckets:
        by_rhs[rhs].add(s)
    keep = [True] * len(parsed)
    for i, r in enumerate(parsed):
        S = frozenset(r["lhs"])
        for T in by_rhs[r["rhs"]]:
            if T == S or not (T <= S) or len(T) == 0:
                continue
            for j in buckets[(r["rhs"], T)]:
                q = parsed[j]
                if any(q["lhs"][c] >= r["lhs"][c] for c in T):    # STRETTAMENTE minore
                    continue
                if q["rhs_thr"] > r["rhs_thr"]:
                    continue
                keep[i] = False
                break
            if not keep[i]:
                break
    return keep


def mask_veto_dominance(parsed, max_extra=2, **_):
    """[V2] r e' rimuovibile se un r'' con LHS SOVRAINSIEME (al piu' max_extra colonne in piu'),
    soglie <= sulle condivise e soglia RHS <= implica il veto di r."""
    buckets = collections.defaultdict(list)
    for i, p in enumerate(parsed):
        buckets[(p["rhs"], frozenset(p["lhs"]))].append(i)
    by_rhs = collections.defaultdict(set)
    for rhs, s in buckets:
        by_rhs[rhs].add(s)
    keep = [True] * len(parsed)
    for i, r in enumerate(parsed):
        S = frozenset(r["lhs"])
        rsig = signature(r)
        for T in by_rhs[r["rhs"]]:
            if T == S or not (S <= T) or len(T) - len(S) > max_extra:
                continue
            for j in buckets[(r["rhs"], T)]:
                q = parsed[j]
                if any(q["lhs"][c] > r["lhs"][c] for c in S):
                    continue
                if q["rhs_thr"] > r["rhs_thr"]:
                    continue
                keep[i] = False
                break
            if not keep[i]:
                break
    return keep


def mask_dom_sub(parsed, max_extra=1, **_):
    """Rimuove r se esiste r' con LHS SOTTOINSIEME stretto, soglie <= sulle condivise,
    soglia RHS <=. Direzione aggressiva: NON preserva i veti."""
    buckets = collections.defaultdict(list)
    for i, p in enumerate(parsed):
        buckets[(p["rhs"], frozenset(p["lhs"]))].append(i)
    by_rhs = collections.defaultdict(set)
    for rhs, s in buckets:
        by_rhs[rhs].add(s)
    keep = [True] * len(parsed)
    for i, r in enumerate(parsed):
        S = frozenset(r["lhs"])
        for T in by_rhs[r["rhs"]]:
            if T == S or not (T <= S) or len(S) - len(T) > max_extra:
                continue
            for j in buckets[(r["rhs"], T)]:
                q = parsed[j]
                if any(q["lhs"][c] > r["lhs"][c] for c in T):
                    continue
                if q["rhs_thr"] > r["rhs_thr"]:
                    continue
                keep[i] = False
                break
            if not keep[i]:
                break
    return keep


def mask_dom_exact(parsed, **_):
    """Dominanza fra RFD con lo STESSO insieme di attributi LHS."""
    buckets = collections.defaultdict(list)
    for i, p in enumerate(parsed):
        buckets[(p["rhs"], frozenset(p["lhs"]))].append(i)
    keep = [True] * len(parsed)
    for _, idxs in buckets.items():
        for i in idxs:
            ri = parsed[i]
            for j in idxs:
                if i == j:
                    continue
                rj = parsed[j]
                if any(rj["lhs"][c] > ri["lhs"][c] for c in ri["lhs"]):
                    continue
                if rj["rhs_thr"] > ri["rhs_thr"]:
                    continue
                if signature(rj) >= signature(ri):
                    continue
                keep[i] = False
                break
    return keep


def mask_coverage(parsed, nullcells_by_attr, dsrows, attrs, **_):
    """Rimuove le RFD che non possono attivarsi su NESSUNA cella nulla.
    Esatto sulla GENERAZIONE; sul veto dipende da --veto-policy."""
    keep = []
    for p in parsed:
        ok = False
        for ri in nullcells_by_attr.get(p["rhs"], ()):
            row = dsrows[ri]
            if all((c in attrs) and not is_null(row[c]) for c in p["lhs"]):
                ok = True
                break
        keep.append(ok)
    return keep


def mask_rhs_thr(parsed, max_rhs_thr=None, **_):
    if max_rhs_thr is None:
        return [True] * len(parsed)
    return [p["rhs_thr"] <= max_rhs_thr for p in parsed]


def mask_lhs_cap(parsed, max_lhs=None, **_):
    if max_lhs is None:
        return [True] * len(parsed)
    return [len(p["lhs"]) <= max_lhs for p in parsed]


def mask_used(parsed, train_stats, **_):
    """Tiene la RFD se e' stata usata almeno una volta nel training (o se non abbiamo dati)."""
    if not train_stats:
        return [True] * len(parsed)
    return [train_stats.get(signature(p), {}).get("uses", 0) > 0 for p in parsed]


# Precisioni di fallback per i cluster senza dati di training (dai dati consolidati:
# il percorso "exact" ha accuratezza 98,7%, quello "similarity" 65,0% — §5.1 del report).
DEFAULT_PRECISION_EXACT = 0.987
DEFAULT_PRECISION_SIMILARITY = 0.650


def cluster_precision_from_stats(train_stats):
    """Conteggi per cluster (rhs, rhs_thr) dai dati di training.

    `train_stats` e' il dizionario prodotto da `load_training_stats()`, con valori
    {"uses": n, "correct": m, "exact": k}. Ritorna {(rhs, rhs_thr): (corrette, usi)}:
    si tengono i conteggi grezzi, non il rapporto, cosi' la stima puo' essere regolarizzata."""
    cluster_correct = collections.defaultdict(int)
    cluster_total = collections.defaultdict(int)
    for sig, st in train_stats.items():
        rhs, rhs_thr = sig[0], sig[1]
        cluster_correct[(rhs, rhs_thr)] += st.get("correct", 0)
        cluster_total[(rhs, rhs_thr)] += st.get("uses", 0)
    return {k: (cluster_correct[k], cluster_total[k]) for k in cluster_total}


def rfd_precision_from_stats(train_stats):
    """Conteggi per singola RFD (firma completa). Ritorna {firma: (corrette, usi)}."""
    return {sig: (st.get("correct", 0), st.get("uses", 0)) for sig, st in train_stats.items()}


def _prior_for(rhs_thr):
    """Prior naturale: la precisione empirica del percorso di appartenenza."""
    return DEFAULT_PRECISION_EXACT if float(rhs_thr) == 0.0 else DEFAULT_PRECISION_SIMILARITY


def _shrink(correct, uses, prior, alpha):
    """Shrinkage bayesiano: (corrette + alpha*prior) / (usi + alpha).
    alpha = 0 -> massima verosimiglianza; alpha -> infinito -> prior puro."""
    if uses == 0:
        return prior
    if not alpha:
        return correct / uses
    return (correct + alpha * prior) / (uses + alpha)


def get_cluster_precision(rhs, rhs_thr, cluster_prec, alpha=0.0):
    """Precisione stimata del cluster, regolarizzata verso il prior del percorso."""
    prior = _prior_for(rhs_thr)
    key = (rhs, round(float(rhs_thr), 9))
    if key not in cluster_prec:
        return prior
    correct, uses = cluster_prec[key]
    return _shrink(correct, uses, prior, alpha)


def get_rfd_precision(p, rfd_prec, alpha=0.0):
    """Precisione stimata della singola RFD, regolarizzata verso il prior del percorso."""
    prior = _prior_for(p["rhs_thr"])
    key = signature(p)
    if key not in rfd_prec:
        return prior
    correct, uses = rfd_prec[key]
    return _shrink(correct, uses, prior, alpha)


def mask_empirical(parsed, train_stats, min_uses=3, min_acc=0.5, **_):
    """Rimuove le RFD con >= min_uses usi e accuratezza < min_acc nel training."""
    if not train_stats:
        return [True] * len(parsed)
    keep = []
    for p in parsed:
        st = train_stats.get(signature(p))
        if not st or st["uses"] < min_uses:
            keep.append(True)
            continue
        acc = st["correct"] / st["uses"] if st["uses"] else 1.0
        keep.append(acc >= min_acc)
    return keep



# =====================================================================================
# REPLICA ESATTA DELLA FUNZIONE DI PUNTEGGIO DI RENUVER (dal bytecode)
# =====================================================================================
# Serve per la strategia `score-argmin`: per sapere quali RFD "vincono" bisogna riprodurre
# `calculatePattern` + la normalizzazione di `getCandidatesForField`, inclusi i suoi difetti.

def _get_digits(x):
    """Replica di getDigits(double): numero di cifre dopo la virgola.
    Riproduce anche il ramo bugiardo della notazione scientifica (cerca '-' invece di 'E')."""
    s = repr(float(x))
    if "E" in s or "e" in s:
        i = s.find("-")
        try:
            return int(s[i + 1:])
        except ValueError:
            return 0
    i = s.find(".")
    return len(s[i:]) - 1 if i >= 0 else 0


def _lev(a, b, thr):
    """Replica di levenshtein3: prefiltro sulla differenza di lunghezza, poi distanza esatta."""
    if a is None or b is None:
        return 2147483647
    if abs(len(a) - len(b)) > int(thr):
        return len(a) + len(b)
    return levenshtein(a, b)


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


def pattern_value(col_type, v1, v2):
    """Replica di calculatePattern per una colonna (valori entrambi non nulli).
    ATTENZIONE: il ramo 'B' nel bytecode e' irraggiungibile (confronto per riferimento),
    quindi una colonna B finisce nel ramo numerico e, se il parse fallisce, in Levenshtein."""
    if col_type == "C":
        if not v1 or not v2:
            return None
        return abs(ord(v1[0]) - ord(v2[0]))
    try:
        return abs(float(v1) - float(v2))
    except ValueError:
        return _lev(v1, v2, 2147483647.0)


def contribution(col_type, pv, thr, maxthr):
    """Replica del blocco di normalizzazione in getCandidatesForField.
    Ritorna (peso, ammesso). `ammesso=False` significa che la RFD viene scartata per quel
    candidato (thresholdPassed non incrementato). pv None = sentinella -1.0 -> RFD abbandonata."""
    if col_type == "B":
        if thr == maxthr:
            if pv == maxthr:
                return 0.0, True
        return None, False                       # ramo B: RFD sempre scartata in pratica
    if col_type == "C":
        if pv is not None and pv <= thr:
            return float(pv), True
        return None, False
    if pv is None:                               # sentinella -1.0 -> break
        return "BREAK", False
    if pv <= thr:
        if thr == 0.0:
            return 0.0, True
        if 0.0 < thr < 1.0:
            return pv * (10.0 ** _get_digits(thr)), True
        return pv / (10.0 ** (len(str(int(thr))) - 1)), True
    return None, False


def rfd_sim(p, vals_t, vals_s, types, maxthr):
    """sim(r, t, s) oppure None se la RFD non ammette il candidato.
    vals_t / vals_s: dict colonna->valore. types: dict colonna->tipo."""
    tot = 0.0
    n = len(p["lhs"])
    if n == 0:
        return None
    for c, thr in p["lhs"].items():
        v1, v2 = vals_t.get(c), vals_s.get(c)
        if is_null(v1) or is_null(v2):
            return None                          # pattern -1.0 -> break
        pv = pattern_value(types.get(c, "D"), v1, v2)
        w, ok = contribution(types.get(c, "D"), pv, thr, maxthr)
        if not ok:
            return None
        tot += w
    return tot / n


def mask_score_argmin(parsed, dsrows, attrs, types, maxthr, family=None, **_):
    """A1 — conserva le RFD che risultano argmin per almeno una coppia (cella nulla, candidato),
    calcolata staticamente sul dataset di input (stato iniziale).

    Limiti dichiarati: non simula lo stato mutato durante l'esecuzione (RENUVER riempie le celle
    mentre procede) ne' la scorciatoia "exact". Il set conservato e' quindi una
    sovra-approssimazione dei veri argmin, che e' la direzione prudente."""
    import numpy as _np
    rows = [[(r.get(a) or "") for a in attrs] for r in dsrows]
    n = len(rows)
    idx = {a: i for i, a in enumerate(attrs)}

    # matrici di distanza per colonna (n x n), NaN dove un valore e' nullo
    D = {}
    for a in attrs:
        m = _np.full((n, n), _np.nan)
        vals = [rows[i][idx[a]] for i in range(n)]
        isnum = [_is_num(v) for v in vals]
        for i in range(n):
            if is_null(vals[i]):
                continue
            for j in range(i + 1, n):
                if is_null(vals[j]):
                    continue
                if isnum[i] and isnum[j] and types.get(a, "D") != "C":
                    d = abs(float(vals[i]) - float(vals[j]))
                elif types.get(a, "D") == "C":
                    d = abs(ord(vals[i][0]) - ord(vals[j][0])) if vals[i] and vals[j] else _np.nan
                else:
                    d = float(levenshtein(vals[i], vals[j]))
                m[i, j] = m[j, i] = d
        D[a] = m

    # coppie (t, s) rilevanti: t ha un null nella colonna RHS, s no
    keepers = set()
    clusters = collections.defaultdict(list)
    for i, p in enumerate(parsed):
        clusters[(p["rhs"], p["rhs_thr"])].append(i)

    for (rhs, rhs_thr), members in clusters.items():
        if rhs not in idx:
            continue
        best = _np.full((n, n), _np.inf)
        bestr = _np.full((n, n), -1, dtype=_np.int64)
        for bi in range(0, len(members), 256):
            chunk = members[bi:bi + 256]
            for i in chunk:
                p = parsed[i]
                acc = _np.ones((n, n), dtype=bool)
                tot = _np.zeros((n, n))
                ok = True
                for c, thr in p["lhs"].items():
                    if c not in idx:
                        ok = False
                        break
                    dd = D[c]
                    t = types.get(c, "D")
                    if t == "B":
                        ok = False
                        break                    # ramo B: RFD sempre scartata
                    if t == "C":
                        good = (~_np.isnan(dd)) & (dd <= thr)
                        tot += _np.where(good, dd, 0.0)
                    else:
                        good = (~_np.isnan(dd)) & (dd <= thr)
                        if thr == 0.0:
                            w = 0.0
                        elif 0.0 < thr < 1.0:
                            w = 10.0 ** _get_digits(thr)
                        else:
                            w = 1.0 / (10.0 ** (len(str(int(thr))) - 1))
                        tot += _np.where(good, dd * w, 0.0)
                    acc &= good
                if not ok or not p["lhs"]:
                    continue
                sim = _np.where(acc, tot / len(p["lhs"]), _np.inf)
                better = sim < best
                best = _np.where(better, sim, best)
                bestr = _np.where(better, i, bestr)
        # conserva l'argmin per le coppie in cui t ha un null nella colonna RHS
        col = idx[rhs]
        nullmask = _np.array([is_null(rows[i][col]) for i in range(n)])
        tgt = _np.array([not is_null(rows[j][col]) for j in range(n)])
        sel = _np.outer(nullmask, tgt)
        good = sel & (best < maxthr) & (bestr >= 0)
        for i in _np.unique(bestr[good]):
            keepers.add(int(i))
    return [i in keepers for i in range(len(parsed))]


def _is_num(s):
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


def mask_dom_sub_adaptive(parsed, dsrows, attrs, alpha=0.85, side="stable", **_):
    """A2 — `dom-sub` applicata solo alle RFD con LHS stabile (o solo a quelle instabili).

    stability[c] = 1 - (righe con c nulla) / (righe totali)
    lhs_stability(r) = media delle stability delle colonne del LHS

    side='stable'   -> pota solo le RFD con lhs_stability >= alpha (LHS affidabile)
    side='unstable' -> pota solo le RFD con lhs_stability <  alpha (LHS spesso incompleto)
    """
    rows = len(dsrows)
    stab = {}
    for a in attrs:
        nn = sum(1 for r in dsrows if is_null(r.get(a, "")))
        stab[a] = 1.0 - nn / rows if rows else 1.0
    dom = mask_dom_sub(parsed, max_extra=1)
    keep = list(dom)
    for i, p in enumerate(parsed):
        if not p["lhs"]:
            continue
        ls = sum(stab.get(c, 1.0) for c in p["lhs"]) / len(p["lhs"])
        if side == "stable":
            keep[i] = dom[i] or not (ls >= alpha)      # pota solo se stabile
        else:
            keep[i] = dom[i] or not (ls < alpha)       # pota solo se instabile
    return keep


def mask_intra_cluster_priority(parsed, **_):
    """A4-bis — non rimuove nulla: segnala un RIORDINO delle RFD DENTRO ogni cluster.

    ATTENZIONE (verificato sul bytecode di `getCandidatesForField`): il ciclo interno
    `for (RFD rfd : selectedRFDs)` scorre TUTTE le RFD del cluster e tiene il minimo stretto,
    senza `break` ne' `return` anticipato. L'unica uscita anticipata e' la scorciatoia exact,
    che pero' scrive il valore della *tupla candidata* nella colonna RHS — e tutte le RFD di
    un cluster condividono la stessa colonna RHS. Ne segue che questo riordino NON puo'
    cambiare il valore imputato. La strategia esiste per falsificare l'ipotesi H13 misurando."""
    return [True] * len(parsed)


def mask_exact_priority(parsed, **_):
    """A4 — non rimuove nulla: segnala solo un RIORDINO del file RFD.
    Le RFD con soglia RHS = 0 vanno per prime, cosi' il cluster a soglia 0 entra per primo
    in `rfdForRHS` e il percorso "exact" viene tentato prima degli altri cluster."""
    return [True] * len(parsed)


# =====================================================================================
# POLITICA SUI VETI
# =====================================================================================
def veto_bearing(parsed, nullcols):
    """True se la RFD puo' partecipare al ramo di rifiuto di isFaultless."""
    return [bool(set(p["lhs"]) & nullcols) for p in parsed]


def exposure(parsed, null_profile):
    """Quante celle nulle ricadono negli attributi del LHS: proxy dell'opportunita' di veto.

    ATTENZIONE: questo proxy e' stato misurato e risulta un CATTIVO predittore del valore di
    veto reale (`pruning/veto_cost.py`). Su `bridges_70` soglia 9 la correlazione di rango fra
    `exposure` e il numero di celle valutate che una RFD rimossa puo' davvero servire e'
    rho = 0,084 su 6 713 RFD rimosse. Usare `servable_counts` al suo posto
    (`--veto-order cells`).
    """
    return [sum(null_profile.get(c, 0) for c in p["lhs"]) for p in parsed]


def servable_counts(parsed, attrs, rows):
    """Quante celle nulle REALI del dataset ogni RFD puo' servire.

    Alternativa a `exposure`: invece del profilo aggregato dei nulli per colonna, usa la
    posizione effettiva delle celle nulle. Una cella `(riga i, colonna C)` e' servibile da una
    RFD `r` se `RHS(r) == C` e tutte le colonne del LHS di `r` sono NON nulle nella riga `i`:
    senza i valori del LHS la condizione non e' valutabile.

    E' un limite superiore — non verifica che esista una riga candidata che soddisfi le soglie —
    ma usa i dati reali invece di una media per colonna, e si calcola con maschere di bit in
    O(|RFD| x |righe|).
    """
    ncol = len(attrs)
    idx_of = {a: i for i, a in enumerate(attrs)}
    nonnull = []
    for r in rows:
        m = 0
        for a in attrs:
            if not is_null(r.get(a, "?")):
                m |= 1 << idx_of[a]
        nonnull.append(m)
    full = (1 << ncol) - 1
    out = []
    for p in parsed:
        ridx = idx_of.get(p["rhs"])
        lm, ok = 0, ridx is not None
        for c in p["lhs"]:
            ci = idx_of.get(c)
            if ci is None:
                ok = False
                break
            lm |= 1 << ci
        if not ok:
            out.append(0)
            continue
        cnt = 0
        for m in nonnull:
            if (m >> ridx) & 1:
                continue                    # la cella in quella colonna non e' nulla
            if lm & (full ^ m) == 0:        # tutte le colonne del LHS sono non nulle
                cnt += 1
        out.append(cnt)
    return out


def apply_veto_policy(keep, parsed, nullcols, policy, null_profile, max_extra=3,
                       order="exposure", dsrows=None, attrs=None):
    """Applica --veto-policy e ritorna (keep, ripristinate, rimosse_portatrici, gratuite).

    Le rimozioni il cui veto e' **provato coperto** da [V2] sull'insieme finale non consumano
    budget: costano zero potere di veto, quindi addebitarle sarebbe una doppia taratura. Prima
    della correzione, su Bridges soglia 9, 1 525 delle 1 531 rimozioni di `veto-cover` erano
    anche never-argmin e finivano per consumare budget che poteva pagare altre rimozioni.

    Il calcolo delle gratuite e' a **un solo passaggio**, sull'insieme `base` = cio' che
    sopravvive a tutte le strategie PRIMA dei ripristini. Non si itera: un punto fisso che
    ricalcolasse la copertura dopo i ripristini sarebbe **circolare**, perche' userebbe RFD
    ripristinate dal budget per giustificare come gratuite le rimozioni che il budget stava
    pagando — e convergerebbe a ripristinare tutto (verificato: la riduzione crollava dal 49,1%
    allo 0,7%). Le RFD vive in `base` restano vive, perche' la politica puo' solo ripristinare:
    quindi la garanzia [V2] su di esse regge.
    """
    keep = list(keep)
    base = list(keep)                       # insieme di riferimento: solo ripristini, mai rimozioni
    vb = veto_bearing(parsed, nullcols)
    if order == "cells" and dsrows is not None and attrs is not None:
        rank_value = servable_counts(parsed, attrs, dsrows)
        what = "celle nulle reali servibili"
    else:
        rank_value = exposure(parsed, null_profile)
        what = "exposure (proxy)"
    removed0 = [i for i, k in enumerate(base) if not k]
    covered = veto_covered_indices(parsed, max_extra=max_extra, alive=base)
    free = {i for i in removed0 if i in covered}
    carriers = [i for i in removed0 if vb[i] and i not in free]
    restored = []
    if policy == "protect":
        restored = carriers
    elif policy.startswith("budget:"):
        frac = float(policy.split(":", 1)[1])
        frac = min(max(frac, 0.0), 1.0)
        allowed = int(round(frac * len(carriers)))
        # si rimuovono prima le RFD con valore MINORE: veto meno probabile.
        # `--veto-order cells` usa le celle nulle reali servibili invece del profilo aggregato.
        ordered = sorted(carriers, key=lambda i: (rank_value[i], -len(parsed[i]["lhs"])))
        restored = ordered[allowed:]
    for i in restored:
        keep[i] = True
    return keep, len(restored), len(carriers) - len(restored), len(free), what


# =====================================================================================
# MAIN
# =====================================================================================
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Semantic pruning esterno e veto-aware di un file RFD per RENUVER.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rfd", required=True, help="file RFD di input")
    ap.add_argument("--dataset", required=True,
                    help="dataset CSV (uno o piu', separati da virgola; ammessi glob). "
                         "Definisce le colonne nulle.")
    ap.add_argument("--ground-truth", default=None, help="file TupleIniziali (validazione)")
    ap.add_argument("--output", required=True, help="file RFD ridotto da scrivere")
    ap.add_argument("--strategy", default="hybrid",
                    help="lista separata da virgole fra: " + ", ".join(STRATEGIES))
    ap.add_argument("--veto-policy", default="protect",
                    help="protect | allow | budget:F  (default protect)")
    ap.add_argument("--coltypes", default=None,
                    help="tipi di colonna separati da virgola, come args0 di RENUVER "
                         "(serve a score-argmin per replicare la formula del punteggio)")
    ap.add_argument("--maxthr", type=int, default=None,
                    help="valore di args[4] passato a RENUVER: e' anche la soglia di accettazione "
                         "del punteggio usata da score-argmin (default = massima soglia del file)")
    ap.add_argument("--precision-alpha", type=float, default=0.0,
                    help="forza dello shrinkage bayesiano sulla stima di precisione dei cluster "
                         "(0 = massima verosimiglianza, come in Fase 4; 3 = bilanciato)")
    ap.add_argument("--adaptive-alpha", type=float, default=0.85,
                    help="soglia di stabilita' del LHS per dom-sub-adaptive (default 0.85)")
    ap.add_argument("--adaptive-side", default="stable", choices=["stable", "unstable"],
                    help="dom-sub-adaptive: pota le RFD con LHS stabile (default) o instabile")
    ap.add_argument("--max-extra", type=int, default=1,
                    help="di quante colonne possono differire i LHS nel confronto di dominanza (default 1)")
    ap.add_argument("--veto-order", default="exposure", choices=["exposure", "cells"],
                    help="come ordinare le RFD da rimuovere sotto --veto-policy budget:F. "
                         "`exposure` (default) usa il profilo aggregato dei nulli per colonna ed e' "
                         "un proxy MISURATO COME CATTIVO (rho ~ 0,08 col valore di veto reale); "
                         "`cells` usa il numero di celle nulle reali che ogni RFD puo' servire.")
    ap.add_argument("--auto-threshold", type=float, default=AUTO_THRESHOLD,
                    help="strategia `auto`: quota di celle nulle in tuple multi-nullo oltre la quale "
                         "si innesca l'euristica A5b invece del teorema `veto-cover` (default %.2f). "
                         "Non e' una soglia sul numero di RFD: vedi la nota in `null_multi_share`."
                         % AUTO_THRESHOLD)
    ap.add_argument("--max-rhs-thr", type=float, default=None, help="soglia RHS massima accettata")
    ap.add_argument("--max-lhs", type=int, default=None, help="numero massimo di colonne nel LHS")
    ap.add_argument("--results-dir", default=None, help="cartella Results/ per le strategie data-driven")
    ap.add_argument("--populated-dir", default=None, help="cartella Populated/ (ground truth)")
    ap.add_argument("--family", default=None, help="prefisso per filtrare i file di training (es. bridges)")
    ap.add_argument("--exclude", default=None, help="regex sui file di training da escludere (leave-one-out)")
    ap.add_argument("--min-uses", type=int, default=3, help="usi minimi per la strategia empirical")
    ap.add_argument("--min-acc", type=float, default=0.5, help="accuratezza minima per empirical")
    ap.add_argument("--report", action="store_true", help="stampa il report dettagliato")
    args = ap.parse_args(argv)

    # ---- dataset -------------------------------------------------------------------
    ds_paths = []
    for item in args.dataset.split(","):
        item = item.strip()
        hits = sorted(glob.glob(item)) if any(ch in item for ch in "*?[") else [item]
        if not hits:
            sys.exit(f"[errore] nessun dataset trovato per: {item}")
        ds_paths += hits
    if not ds_paths:
        sys.exit("[errore] nessun dataset specificato")

    attrs, dsrows = read_dataset(ds_paths[0])
    nullcells_by_attr = collections.defaultdict(list)
    for ri, row in enumerate(dsrows):
        for a in attrs:
            if is_null(row[a]):
                nullcells_by_attr[a].append(ri)
    nullcols, null_profile = collect_null_columns(ds_paths)

    # ---- validazione schema --------------------------------------------------------
    rfd_lines = read_lines(args.rfd)
    if not rfd_lines:
        sys.exit("[errore] file RFD vuoto")
    header = rfd_lines[0].split(";")
    body = rfd_lines[1:]
    rfd_attrs = header[1:]
    if set(rfd_attrs) - set(attrs):
        sys.exit(f"[errore] il file RFD usa attributi assenti nel dataset: "
                 f"{sorted(set(rfd_attrs) - set(attrs))}\n"
                 f"         RENUVER risolve le colonne per POSIZIONE: con header disallineati "
                 f"scrive nella colonna sbagliata (corruzione silenziosa). Allinea gli schemi.")
    if rfd_attrs != attrs:
        print(f"[avviso] ordine/numero di colonne diverso fra RFD e dataset.\n"
              f"         RFD     : {rfd_attrs}\n         dataset : {attrs}\n"
              f"         RENUVER usa gli indici posizionali: verifica che sia voluto.", file=sys.stderr)

    # ---- ground truth (validazione) -------------------------------------------------
    if args.ground_truth and os.path.exists(args.ground_truth):
        n_gt = len(read_lines(args.ground_truth))
    else:
        n_gt = None

    # ---- parsing -------------------------------------------------------------------
    parsed, raws, unparsed = [], [], 0
    for line in body:
        p = parse_rfd_row(header, line)
        if p is None:
            unparsed += 1
            continue
        parsed.append(p)
        raws.append(line)
    n0 = len(raws)

    # ---- training data -------------------------------------------------------------
    train_stats = {}
    if any(s in args.strategy for s in ("used", "empirical", "hybrid", "precision-priority",
                                        "intra-cluster-priority")):
        train_stats = load_training_stats(args.results_dir, args.populated_dir,
                                         args.family, args.exclude)

    # ---- sequenza di strategie -----------------------------------------------------
    # accetta sia la virgola sia il '+' come separatore (il '+' e' usato da benchmark.py)
    seq = [s.strip() for s in args.strategy.replace("+", ",").split(",") if s.strip()]

    # ---- strategia `auto`: fonde il teorema esatto e l'euristica --------------------
    if "auto" in seq:
        share, n_tot, n_multi = null_multi_share(attrs, dsrows)
        denso = share >= args.auto_threshold
        sub = (["exact-priority", "dom-sub-adaptive"] if denso else ["veto-cover"])
        print("-" * 78)
        if denso:
            print(f"Strategia AUTO: rilevato dataset DENSO (celle nulle in tuple multi-nullo: "
                  f"{n_multi}/{n_tot} = {100*share:.1f}% >= {100*args.auto_threshold:.0f}%) "
                  f"-> innesco A5b (euristica)")
            print(f"                motivo: in questo regime domina il ramo multi-cella di "
                  f"treatNullTuple, dove il pruning aggressivo elimina rumore")
        else:
            print(f"Strategia AUTO: rilevato dataset SPARSO (celle nulle in tuple multi-nullo: "
                  f"{n_multi}/{n_tot} = {100*share:.1f}% < {100*args.auto_threshold:.0f}%) "
                  f"-> innesco veto-cover (teorema esatto)")
            print(f"                motivo: in questo regime domina il ramo mono-cella; il pruning "
                  f"aggressivo toglierebbe copertura, il teorema no")
        print(f"                N (RFD in ingresso) = {len(raws)} — NON usato per la scelta: "
              f"nessuna soglia su N separa i due regimi (vedi null_multi_share)")
        print("-" * 78)
        seq = [s for x in seq for s in (sub if x == "auto" else [x])]

    if "hybrid" in seq:
        seq = ["duplicates", "inert", "veto-dominance", "dom-sub", "used", "empirical"]
    if "precision-priority" in seq and (not args.results_dir or not args.populated_dir):
        sys.exit("[errore] precision-priority richiede --results-dir e --populated-dir")
    unknown_s = [s for s in seq if s not in STRATEGIES]
    if unknown_s:
        sys.exit(f"[errore] strategie sconosciute: {unknown_s}")

    keep = [True] * n0
    log = []
    reorder = {}                       # nome -> chiave di ordinamento (riordini, non rimozioni)

    def apply(name, mask):
        nonlocal keep
        before = sum(keep)
        keep = [a and b for a, b in zip(keep, mask)]
        log.append((name, before - sum(keep), sum(keep)))

    for s in seq:
        if s == "duplicates":
            apply("duplicates  (righe duplicate, sicura)", mask_duplicates(parsed, raws))
        elif s == "inert":
            apply("inert       [V3] non puo' generare ne' fare veto (sicura)", mask_inert(parsed, nullcols=nullcols))
        elif s == "veto-cover":
            # `alive=keep`: la copertura [V2] va valutata sull'insieme CORRENTE. Se una strategia
            # precede `veto-cover` ha gia' rimosso delle RFD, e un copritore rimosso non copre
            # piu' nulla. Senza questo, il teorema verrebbe applicato su un insieme che non esiste.
            apply(f"veto-cover   [V2] veto coperto da un'altra RFD (max_extra={max(args.max_extra, 3)})",
                  mask_veto_cover(parsed, max_extra=max(args.max_extra, 3), alive=keep))
        elif s == "classical-cover":
            apply("classical-cover (ridondanza classica, soglie ignorate)",
                  mask_classical_cover(parsed))
        elif s == "dom-sub-adaptive":
            apply(f"dom-sub-adaptive (alpha={_fmt_alpha(args.adaptive_alpha)}, lati={args.adaptive_side})",
                  mask_dom_sub_adaptive(parsed, dsrows, attrs, alpha=args.adaptive_alpha,
                                        side=args.adaptive_side))
        elif s == "score-argmin":
            ct = (args.coltypes.split(",") if args.coltypes
                  else ["D"] * len(attrs))
            types = {a: (ct[i] if i < len(ct) else "D") for i, a in enumerate(attrs)}
            mt = args.maxthr if args.maxthr is not None else int(max(p["rhs_thr"] for p in parsed))
            apply(f"score-argmin (maxthr={mt})",
                  mask_score_argmin(parsed, dsrows, attrs, types, mt))
        elif s == "exact-priority":
            reorder["exact-priority"] = lambda p: 0 if p["rhs_thr"] == 0.0 else 1
            apply("exact-priority (riordino: RFD a soglia RHS 0 per prime)", [True] * len(parsed))
        elif s == "precision-priority":
            if not train_stats:
                sys.exit("[errore] precision-priority richiede dati di training "
                         "(--results-dir, --populated-dir, --family)")
            cluster_prec = cluster_precision_from_stats(train_stats)
            alpha = args.precision_alpha
            # se `exact-priority` e' gia' stato richiesto, il riordino data-driven lo ingloba
            exact_first = "exact-priority" in reorder

            def _pp_key(p, cp=cluster_prec, a=alpha, ef=exact_first):
                prec = get_cluster_precision(p["rhs"], p["rhs_thr"], cp, alpha=a)
                return ((0 if p["rhs_thr"] == 0.0 else 1) if ef else 0, -prec)

            reorder["precision-priority"] = _pp_key
            reorder["__current_order__"] = _pp_key
            n_zero = sum(1 for k in cluster_prec if k[1] == 0.0)
            apply(f"precision-priority (alpha={_fmt_alpha(alpha)}, {len(cluster_prec)} cluster con "
                  f"dati di cui {n_zero} a soglia RHS 0, exact-first={'si' if exact_first else 'no'})",
                  [True] * len(parsed))
            if args.report:
                scored = sorted(
                    ((a_, t, get_cluster_precision(a_, t, cluster_prec, alpha=alpha))
                     for (a_, t) in cluster_prec), key=lambda x: -x[2])[:6]
                print("  cluster piu' precisi (dopo regolarizzazione): " +
                      ", ".join(f"{a_}@{t:g}={p_:.2f}" for a_, t, p_ in scored))
        elif s == "intra-cluster-priority":
            if not train_stats:
                sys.exit("[errore] intra-cluster-priority richiede dati di training")
            rfd_prec = rfd_precision_from_stats(train_stats)
            alpha = args.precision_alpha
            # rank del cluster nell'ordine ORIGINALE del file: cosi' l'ordine FRA cluster
            # resta identico e si isola l'effetto del riordino DENTRO il cluster.
            order_ref = reorder.get("__current_order__")
            rank = {}
            if order_ref is not None:
                for p in sorted(parsed, key=order_ref):
                    k = (p["rhs"], round(float(p["rhs_thr"]), 9))
                    rank.setdefault(k, len(rank))
            else:
                for p in parsed:
                    k = (p["rhs"], round(float(p["rhs_thr"]), 9))
                    rank.setdefault(k, len(rank))

            def _icp_key(p, rp=rfd_prec, a=alpha, rk=rank):
                k = (p["rhs"], round(float(p["rhs_thr"]), 9))
                return (rk.get(k, 0), -get_rfd_precision(p, rp, alpha=a))

            reorder["intra-cluster-priority"] = _icp_key
            apply(f"intra-cluster-priority (alpha={_fmt_alpha(alpha)}, riordino DENTRO i cluster; "
                  f"nessuna RFD rimossa)", [True] * len(parsed))
        elif s == "dom-sub-strict":
            apply("dom-sub-strict (soglie strettamente migliori su tutte le condivise)",
                  mask_dom_sub_strict(parsed))
        elif s == "veto-dominance":
            apply("veto-dominance [V2] veto implicato da un'altra RFD",
                  mask_veto_dominance(parsed, max_extra=args.max_extra))
        elif s == "coverage":
            apply("coverage    (nessuna cella nulla attivabile)",
                  mask_coverage(parsed, nullcells_by_attr, dsrows, set(attrs)))
        elif s == "dom-sub":
            apply(f"dom-sub     (LHS sottoinsieme, max_extra={args.max_extra})",
                  mask_dom_sub(parsed, max_extra=args.max_extra))
        elif s == "dom-exact":
            apply("dom-exact   (stesso insieme LHS, soglie piu' deboli)", mask_dom_exact(parsed))
        elif s == "rhs-thr":
            apply(f"rhs-thr     (soglia RHS > {args.max_rhs_thr})", mask_rhs_thr(parsed, args.max_rhs_thr))
        elif s == "lhs-cap":
            apply(f"lhs-cap     (|LHS| > {args.max_lhs})", mask_lhs_cap(parsed, args.max_lhs))
        elif s == "used":
            apply("used        (mai usata nel training)", mask_used(parsed, train_stats))
        elif s == "empirical":
            apply(f"empirical   (usi>={args.min_uses} e acc<{args.min_acc:.0%})",
                  mask_empirical(parsed, train_stats, args.min_uses, args.min_acc))

    # ---- politica sui veti ---------------------------------------------------------
    keep, n_restored, n_carriers_removed, n_free, order_what = apply_veto_policy(
        keep, parsed, nullcols, args.veto_policy, null_profile,
        max_extra=max(args.max_extra, 3), order=args.veto_order, dsrows=dsrows, attrs=attrs)

    # ---- scrittura -----------------------------------------------------------------
    pairs = [(raw, p) for raw, p, k in zip(raws, parsed, keep) if k]
    for name, key in reorder.items():
        if name.startswith("__"):
            continue                                   # chiavi di servizio, non riordini
        pairs.sort(key=lambda rp: key(rp[1]))          # sort stabile: preserva l'ordine relativo
        print(f"[riordino] applicato '{name}' a {len(pairs)} righe RFD")
    kept = [raw for raw, _ in pairs]
    out_dir = os.path.dirname(os.path.abspath(args.output))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(rfd_lines[0] + "\n")
        for l in kept:
            fh.write(l + "\n")

    # ---- report --------------------------------------------------------------------
    vb = veto_bearing(parsed, nullcols)
    n_vb = sum(vb)
    print("=" * 78)
    print("SEMANTIC PRUNING — REPORT")
    print("=" * 78)
    print(f"file RFD in ingresso : {args.rfd}")
    print(f"dataset              : {', '.join(os.path.basename(p) for p in ds_paths)}")
    print(f"RFD in ingresso      : {n0}" + (f"  (+{unparsed} righe non interpretabili, scartate)" if unparsed else ""))
    print(f"colonne mai nulle    : {sorted(set(attrs) - nullcols)}")
    print(f"RFD portatrici di veto (LHS interseca colonne nulle): {n_vb} ({100*n_vb/max(1,n0):.1f}%)")
    print(f"RFD provabilmente inerti [V3]                       : "
          f"{sum(1 for p in parsed if not (set(p['lhs']) & nullcols) and p['rhs'] not in nullcols)}")
    print()
    print(f"{'strategia':<58}{'rimosse':>9}{'restano':>9}")
    print("-" * 78)
    for name, rem, left in log:
        print(f"{name:<58}{rem:>9}{left:>9}")
    print("-" * 78)
    print(f"{'politica sui veti: ' + args.veto_policy:<58}"
          f"{'ripristinate ' + str(n_restored):>9}")
    print(f"{'RFD portatrici di veto effettivamente rimosse':<58}{n_carriers_removed:>9}")
    print(f"{'  di cui GRATUITE (veto coperto da [V2] sul set finale)':<58}{n_free:>9}")
    if args.veto_policy.startswith("budget:"):
        print(f"{'  ordinamento del budget: ' + order_what:<58}{'':>9}")
    print()
    print(f"RFD in uscita        : {len(kept)}")
    print(f"RIDUZIONE            : {n0 - len(kept)} ({100*(n0-len(kept))/max(1,n0):.1f}%)")
    if n_gt is not None:
        print(f"celle di ground truth: {n_gt} (nessuna modifica: il pruning non tocca il dataset)")
    print(f"scritto              : {args.output}")

    if args.report:
        # motivazione per categoria: quante RFD di ciascun RHS sono state rimosse
        rem_by_rhs = collections.Counter()
        for p, k in zip(parsed, keep):
            if not k:
                rem_by_rhs[p["rhs"]] += 1
        print("\nRFD rimosse per attributo RHS:")
        for rhs, c in rem_by_rhs.most_common():
            tot = sum(1 for p in parsed if p["rhs"] == rhs)
            print(f"   {rhs:<14} {c:>6} / {tot:>6}  ({100*c/max(1,tot):>5.1f}%)")
        rem_by_size = collections.Counter(len(p["lhs"]) for p, k in zip(parsed, keep) if not k)
        print("\nRFD rimosse per dimensione del LHS:")
        for s in sorted(rem_by_size):
            tot = sum(1 for p in parsed if len(p["lhs"]) == s)
            print(f"   |LHS|={s:<3} {rem_by_size[s]:>6} / {tot:>6}  ({100*rem_by_size[s]/max(1,tot):>5.1f}%)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
