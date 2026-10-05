#!/usr/bin/env python3
"""Pruning-potential analysis on the RFD files + missingness profile of the datasets."""
import os, re, json, collections, statistics, itertools

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/RENUVER"
OUT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/results/analisi"
os.makedirs(OUT, exist_ok=True)

def ls(d):
    """Elenco dei file di una cartella dell'archivio; lista vuota se la cartella non c'e'
    (nella versione leggera del pacchetto i dataset non sono inclusi)."""
    p = os.path.join(ROOT, d)
    if not os.path.isdir(p):
        print(f"[nota] cartella assente: {os.path.relpath(p, os.path.dirname(ROOT))} "
              f"-> le sezioni che ne dipendono vengono saltate")
        return []
    return sorted(f for f in os.listdir(p) if not f.startswith("._") and f != ".DS_Store")

NULLS = {"?", "", "null", "NULL", "NA", "nan", "NaN"}

# ---------------- load an RFD file ----------------
def load_rfd(path):
    lines = [l for l in open(path, encoding="utf-8", errors="replace").read().splitlines() if l.strip()]
    header = lines[0].split(";")
    attrs = header[1:]                       # attribute names in column order
    rfds = []
    for l in lines[1:]:
        c = l.split(";")
        if len(c) < 1 + len(attrs): 
            c = c + ["?"] * (1 + len(attrs) - len(c))
        rhs = c[0].strip()
        if rhs not in attrs: continue
        rhs_thr = None
        lhs = {}
        for a in attrs:
            v = c[1 + attrs.index(a)].strip()
            if v == "?": continue
            try: t = float(v)
            except ValueError: continue
            if a == rhs: rhs_thr = t
            else: lhs[a] = t
        if rhs_thr is None: continue
        rfds.append(dict(rhs=rhs, rhs_thr=rhs_thr, lhs=lhs,
                         key=(rhs, rhs_thr, tuple(sorted(lhs.items())))))
    return attrs, rfds

# ---------------- dataset helpers ----------------
def load_dataset(path):
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    attrs = lines[0].split(";")
    rows = []
    for l in lines[1:]:
        c = l.split(";")
        rows.append({a: (c[i].strip() if i < len(c) else "") for i, a in enumerate(attrs)})
    return attrs, rows

def is_null(v): return v in NULLS

# ---------------- dominance ----------------
def dominates(r2, r1):
    """True if r2 makes r1 redundant: same RHS, r2 tighter on RHS,
    r2's LHS is a subset of r1's with thresholds <= r1's."""
    if r2["rhs"] != r1["rhs"]: return False
    if r2["rhs_thr"] > r1["rhs_thr"]: return False
    if not set(r2["lhs"]) <= set(r1["lhs"]): return False
    for a, t in r2["lhs"].items():
        if t > r1["lhs"][a]: return False
    return True

def is_strict(r2, r1):
    return dominates(r2, r1) and r2["key"] != r1["key"]

print("="*118)
print("A. STATISTICHE E POTENZIALE DI PRUNING DEI SET DI RFD")
print("="*118)
print(f"{'file':<48}{'RFD':>7}{'RHS0':>7}{'LHS0':>7}{'dup':>6}{'dom%':>7}{'rid%':>7}{'LHSmed':>7}")
summary = {}
for f in [x for x in ls("RFD") if x.endswith(".csv")]:
    path = os.path.join(ROOT, "RFD", f)
    try: attrs, rfds = load_rfd(path)
    except Exception as e:
        print(f"{f:<48} ERRORE {e}"); continue
    n = len(rfds)
    if n == 0: continue
    rhs0 = sum(1 for r in rfds if r["rhs_thr"] == 0.0)
    lhs0 = sum(1 for r in rfds if not r["lhs"])
    keys = collections.Counter(r["key"] for r in rfds)
    dup = sum(v - 1 for v in keys.values() if v > 1)
    # exact-LHS duplicates ignoring the rhs threshold on the same attribute
    sig = collections.Counter((r["rhs"], tuple(sorted(r["lhs"].items()))) for r in rfds)
    duplhs = sum(v - 1 for v in sig.values() if v > 1)

    # dominance: bucket by RHS to keep it tractable
    by_rhs = collections.defaultdict(list)
    for r in rfds: by_rhs[r["rhs"]].append(r)
    ndom = 0
    for rhs, group in by_rhs.items():
        dominated = set()
        for i, r1 in enumerate(group):
            li = len(r1["lhs"])
            for r2 in group:
                if r2 is r1: continue
                lj = len(r2["lhs"])
                if lj > li: continue
                if r2["rhs_thr"] > r1["rhs_thr"]: continue
                if not set(r2["lhs"]) <= set(r1["lhs"]): continue
                if any(r2["lhs"][a] > r1["lhs"][a] for a in r2["lhs"]): continue
                if r2["key"] == r1["key"]: continue
                dominated.add(i); break
        ndom += len(dominated)
    lhsmed = statistics.median([len(r["lhs"]) for r in rfds])
    summary[f] = dict(n=n, rhs0=rhs0, lhs0=lhs0, dup=dup, duplhs=duplhs, dominated=ndom, lhs_median=lhsmed)
    print(f"{f:<48}{n:>7}{rhs0:>7}{lhs0:>7}{duplhs:>6}{100*ndom/n:>7.1f}{100*(ndom+duplhs)/n:>7.1f}{lhsmed:>7.1f}")

json.dump(summary, open(os.path.join(OUT, "pruning_potential.json"), "w"), indent=1)

# ---------------- missingness profile ----------------
print("\n" + "="*118)
print("B. PROFILO DI MISSINGNESS (Dataset/) — quale colonna e' nulla, e quanto spesso")
print("="*118)
bases = collections.defaultdict(list)
for f in ls("Dataset"):
    if not f.endswith(".csv") or f.startswith("Physician"): continue
    m = re.match(r"^(?P<fam>.+?)_(?P<miss>\d+)_(?P<run>\d+)\.\.?\.?csv$", f)
    if not m:
        m2 = re.match(r"^(?P<fam>.+?)_(?P<miss>\d+)_(?P<run>\d+)\.csv$", f)
        if not m2: continue
        m = m2
    bases[m["fam"]].append((int(m["miss"]), int(m["run"]), f))

for fam, files in sorted(bases.items()):
    files.sort()
    _, _, f0 = files[0]
    attrs, rows = load_dataset(os.path.join(ROOT, "Dataset", f0))
    tot = collections.Counter()
    for r in rows:
        for a in attrs:
            if is_null(r[a]): tot[a] += 1
    # injected cells, from TupleIniziali
    tf = os.path.join(ROOT, "TupleIniziali", f0)
    inj = collections.Counter()
    if os.path.exists(tf):
        for l in open(tf, encoding="utf-8", errors="replace").read().splitlines():
            p = l.split(";")
            if len(p) >= 3: inj[p[1].strip()] += 1
    print(f"\n--- {fam}  (file {f0}, {len(rows)} tuple) ---")
    print(f"    {'attributo':<16}{'null pre-esistenti':>20}{'iniettati':>11}{'tot null':>10}")
    for a in attrs:
        print(f"    {a:<16}{tot[a]:>20}{inj.get(a,0):>11}{tot[a]:>10}")

# ---------------- P2: coverage-based pruning potential ----------------
print("\n" + "="*118)
print("C. POTENZIALE DEL PRUNING PER COVERAGE (P2): RFD applicabili a >=1 cella mancante")
print("="*118)
print("   Un RFD e' applicabile a una cella (r,a) se tutte le colonne del suo LHS sono NON nulle in r.")
for fam, rfdfile in [("bridges", "output_false_15_bridges.csv"),
                     ("bridges", "output_false_3_bridges.csv"),
                     ("glass",   "output_false_15_glass.csv"),
                     ("restaurant", "output_false_15_restaurant.csv")]:
    ds = [f for f in ls("Dataset") if f.startswith(fam + "_") and f.endswith(".csv")]
    if not ds: continue
    ds.sort(key=lambda x: (int(re.findall(r"_(\d+)_", x)[0]) if re.findall(r"_(\d+)_", x) else 0))
    f0 = ds[0]
    attrs, rows = load_dataset(os.path.join(ROOT, "Dataset", f0))
    rfdp = os.path.join(ROOT, "RFD", rfdfile)
    if not os.path.exists(rfdp): continue
    _, rfds = load_rfd(rfdp)
    # missing cells = all null cells in the dataset
    cells = [(ri, a) for ri, r in enumerate(rows) for a in attrs if is_null(r[a])]
    # exclude cells whose attribute is ID (never useful) -> keep all, report
    bad = collections.Counter()
    # colonne del LHS che il dataset non possiede: succede a Glass, dove l'archivio ha i nomi
    # anonimizzati (C, D, I, K, ...) mentre il file RFD usa i nomi veri (ID, RI, Na, ...).
    # Una regola con una colonna assente non e' valutabile: non risulta applicabile.
    ignote = collections.Counter(c for r in rfds for c in r["lhs"]
                                 if not rows or c not in rows[0])
    keep = 0
    for r in rfds:
        usable = 0
        for ri, a in cells:
            if a != r["rhs"]: continue
            if all(c in rows[ri] and not is_null(rows[ri][c]) for c in r["lhs"]):
                usable += 1
                if usable >= 1: break
        if usable: keep += 1
        else: bad[r["rhs"]] += 1
    print(f"\n   {fam:<11} {rfdfile:<34} RFD={len(rfds):>6}  applicabili={keep:>6} ({100*keep/len(rfds):>5.1f}%)  "
          f"prunabili={len(rfds)-keep:>6} ({100*(len(rfds)-keep)/len(rfds):>5.1f}%)  celle_nulle={len(cells)}")
    print(f"      prunabili per RHS: {dict(bad.most_common(8))}")
    if ignote:
        print(f"      [nota] {len(ignote)} colonne del LHS assenti dal dataset "
              f"(es. {sorted(ignote)[:3]}): schema non allineato, cfr. §7 della relazione")
