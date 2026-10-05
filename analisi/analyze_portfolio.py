#!/usr/bin/env python3
"""Threshold portfolio analysis: is one threshold enough, or are they complementary?"""
import os, re, json, collections

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/RENUVER"
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/results/analisi"
NULLS = {"?", ""}

def ls(d):
    return sorted(f for f in os.listdir(os.path.join(SRC, d)) if not f.startswith("._") and f != ".DS_Store")

def read_pop(path):
    res = {}
    for i, line in enumerate(open(path, encoding="utf-8", errors="replace")):
        q = line.rstrip("\n").split(";")
        if i == 0 and q[0].lower().startswith("riga"): continue
        if len(q) < 4: continue
        res[(q[0].strip(), q[1].strip())] = (q[2].strip(), q[3].strip())
    return res

# index populated by (base, thr)
idx = {}
for f in ls("Populated"):
    stem = f[:-4]
    if stem.startswith("output_"): stem = stem[7:]
    m = re.match(r"^(?P<base>.+)_(?P<thr>\d+)H(?P<heu>\d+)$", stem)
    if m: idx[(m["base"], int(m["thr"]))] = f; continue
    m = re.match(r"^results_(?P<thr>\d+)_(?P<base>.+)$", stem)
    if m: idx[(m["base"], int(m["thr"]))] = f

runs = collections.defaultdict(dict)      # base -> thr -> {cell: (gt, imp)}
for (base, thr), f in idx.items():
    runs[base][thr] = read_pop(os.path.join(SRC, "Populated", f))

def ok(a, b):
    if b in NULLS: return False
    if a == b: return True
    try: return abs(float(a) - float(b)) < 1e-9
    except ValueError: return False

print("="*112)
print("PORTFOLIO DI SOGLIE: complementarita' per singolo run (celle iniettate)")
print("="*112)
print(f"{'run':<24}{'celle':>6}{'thr':>5}  " + "".join(f"{'t'+str(t):>7}" for t in (3,6,9,12,15)) + f"{'UNIONE':>8}{'nessuna':>9}")
union_tot = collections.Counter()
for base in sorted(runs):
    per = runs[base]
    if not per: continue
    thrs = sorted(per)
    cells = set()
    for t in thrs: cells |= set(per[t])
    # only injected cells (present in all threshold runs)
    common = set.intersection(*[set(per[t]) for t in thrs]) if thrs else set()
    if not common: continue
    counts = {}
    for t in thrs:
        counts[t] = sum(1 for c in common if ok(*per[t][c]))
    uni = sum(1 for c in common if any(ok(*per[t][c]) for t in thrs))
    none = sum(1 for c in common if not any(ok(*per[t][c]) for t in thrs))
    union_tot[(base.split('_')[0])] += 0
    row = f"{base:<24}{len(common):>6}{len(thrs):>5}  " + "".join(f"{counts.get(t,0):>7}" for t in (3,6,9,12,15))
    row += f"{uni:>8}{none:>9}"
    print(row)

print("\n" + "="*112)
print("AGGREGATO PER DATASET: quante celle sono risolte SOLO da soglie alte (>3) o SOLO da soglie basse (<=3)?")
print("="*112)
agg = collections.defaultdict(lambda: collections.Counter())
for base in sorted(runs):
    per = runs[base]
    thrs = sorted(per)
    common = set.intersection(*[set(per[t]) for t in thrs]) if thrs else set()
    if not common: continue
    fam = re.sub(r"_[\d.]+$", "", base)
    for c in common:
        sol = {t for t in thrs if ok(*per[t][c])}
        agg[fam]["cells"] += 1
        if sol:
            agg[fam]["solved"] += 1
            if sol <= {3}: agg[fam]["solo_bassa"] += 1
            if sol >= {9, 12, 15}: agg[fam]["solo_alta"] += 1
            agg[fam]["sum_sol"] += len(sol)
for fam, a in sorted(agg.items()):
    print(f"  {fam:<24} celle={a['cells']:>6}  risolte da >=1 soglia={a['solved']:>6} "
          f"({100*a['solved']/a['cells']:>5.1f}%)  solo thr<=3={a['solo_bassa']:>5}  "
          f"solo thr>=9={a['solo_alta']:>5}  media soglie risolventi={a['sum_sol']/max(1,a['solved']):.2f}")
