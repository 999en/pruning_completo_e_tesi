#!/usr/bin/env python3
"""Parse RENUVER Results/ files: attribute every imputation to the RFD that produced it,
then cross-reference with Populated/ ground truth."""
import os, re, json, collections, statistics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/RENUVER"
OUT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/results/analisi"
os.makedirs(OUT, exist_ok=True)

def ls(d):
    p = os.path.join(ROOT, d)
    return sorted(f for f in os.listdir(p) if not f.startswith("._") and f != ".DS_Store")

def family(base):
    return re.sub(r"_remodulated_[\d.]+$", "", re.sub(r"_\d+(\.\.)?$", "", base))

# ---- parse one Results line ----
RHS_PAT = re.compile(r"\[(?P<lhs>[^\[\]]*)\]\s*->\s*\((?P<rhs>[^)]+)\)_(?P<thr>[-\d.]+)\s*;\s*(?P<tail>.*)$")
LHS_ITEM = re.compile(r"\(([^)]+)\)_([-\d.]+)")
TUP_ITEM  = re.compile(r"([^\[\],;]+?):([^\[\],]*)")
SIMTUP = re.compile(r"weightedSimilarity=([-\d.Ee+]+),\s*fieldIndex=(-?\d+)")

def parse_result_line(line):
    line = line.rstrip("\n")
    if not line.strip(): return None
    parts = line.split(";")
    if len(parts) < 3: return None
    try:
        row = int(parts[0])
    except ValueError:
        return None
    if ":" not in parts[1]: return None
    attr, _, real = parts[1].partition(":")
    attr = attr.strip(); real = real.strip()
    rest = ";".join(parts[2:])
    m = RHS_PAT.search(rest)
    if not m: return None
    lhs = [(c.strip(), float(t)) for c, t in LHS_ITEM.findall(m.group("lhs"))]
    rhs = m.group("rhs").strip(); rhs_thr = float(m.group("thr"))
    tail = m.group("tail").strip()
    wsim = None
    ms = SIMTUP.search(rest)
    if ms:
        wsim = float(ms.group(1))
    # candidate tuple = the bracketed list before the LHS
    tuplist = rest.split(";")[0]
    cand = {}
    if tuplist.startswith("["):
        for c, v in TUP_ITEM.findall(tuplist.strip("[]")):
            cand[c.strip()] = v.strip()
    return dict(row=row, attr=attr, real=real, lhs=tuple(sorted(lhs)), rhs=rhs, rhs_thr=rhs_thr,
                wsim=wsim, tail=tail, exact=(tail == "exact"),
                score=(None if tail == "exact" else (float(tail) if re.match(r"^-?[\d.]+$", tail) else None)),
                ncand=len(cand))

# ---- Populated ground truth ----
def parse_populated(path):
    truth = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            line = line.rstrip("\n").rstrip("\r")
            if not line: continue
            if i == 0 and line.lower().startswith("riga"): continue
            p = line.split(";")
            if len(p) < 4: continue
            truth[(p[0].strip(), p[1].strip())] = (p[2], p[3])
    return truth

NUM = re.compile(r"^-?\d+(\.\d+)?$")
def ok(a, b):
    if a == b: return True
    if NUM.match(a) and NUM.match(b):
        try: return abs(float(a) - float(b)) < 1e-9
        except ValueError: return False
    return False

# ---- index populated by (base, thr) ----
pop_index = {}
for f in ls("Populated"):
    stem = f[:-4]
    if stem.startswith("output_"): stem = stem[7:]
    m = re.match(r"^(?P<base>.+)_(?P<thr>\d+)H(?P<heu>\d+)$", stem)
    if m: pop_index[(m["base"], int(m["thr"]))] = f; continue
    m = re.match(r"^results_(?P<thr>\d+)_(?P<base>.+)$", stem)
    if m: pop_index[(m["base"], int(m["thr"]))] = f

# ---- main pass ----
recs = []
for f in ls("Results"):
    stem = f[:-4]
    if stem.startswith("output_"): stem = stem[7:]
    m = re.match(r"^(?P<base>.+)_(?P<thr>\d+)H(?P<heu>\d+)$", stem)
    if not m: continue
    base, thr = m["base"], int(m["thr"])
    truth = None
    pf = pop_index.get((base, thr))
    if pf:
        truth = parse_populated(os.path.join(ROOT, "Populated", pf))
    for line in open(os.path.join(ROOT, "Results", f), encoding="utf-8", errors="replace"):
        r = parse_result_line(line)
        if not r: continue
        r.update(base=base, thr=thr, family=family(base), file=f)
        t = truth.get((str(r["row"]), r["attr"])) if truth else None
        r["known"] = t is not None
        r["gt"] = t[0] if t else None
        r["imputed"] = t[1] if t else None
        r["correct"] = (ok(t[0], t[1]) if t else None)
        recs.append(r)

print(f"righe Results parsate: {len(recs)}")
bad = [r for r in recs if r["lhs"] is None]
print(f"righe non parsate: {sum(1 for r in recs if not r['lhs'])}")

covered = [r for r in recs if r["known"]]
print(f"di cui agganciabili a una cella iniettata (ground truth): {len(covered)}")
print(f"non agganciate (celle pre-esistenti o mismatch): {len(recs)-len(covered)}")
print(f"corrette: {sum(1 for r in covered if r['correct'])}  errate: {sum(1 for r in covered if r['correct'] is False)}")
print(f"match 'exact': {sum(1 for r in recs if r['exact'])}  via SimilarityTuple: {sum(1 for r in recs if not r['exact'])}")

# score / correctness correlation on the similarity path
sim = [r for r in covered if r["wsim"] is not None]
print(f"\n--- correlazione weightedSimilarity vs correttezza (n={len(sim)}) ---")
buckets = collections.defaultdict(lambda: [0,0])
for r in sim:
    w = r["wsim"]
    b = "0.0" if w == 0 else ("(0,1]" if w <= 1 else ("(1,5]" if w <= 5 else ("(5,20]" if w <= 20 else ">20")))
    buckets[b][1] += 1
    if r["correct"]: buckets[b][0] += 1
for b in ["0.0","(0,1]","(1,5]","(5,20]",">20"]:
    if b in buckets:
        c, n = buckets[b]
        print(f"  wsim {b:<7} n={n:>5}  corrette={c:>5}  accuratezza={100*c/n:>5.1f}%")

print(f"\n--- 'exact' path ---")
ex = [r for r in covered if r["exact"]]
print(f"  n={len(ex)}  corrette={sum(1 for r in ex if r['correct'])}  "
      f"accuratezza={100*sum(1 for r in ex if r['correct'])/max(1,len(ex)):.1f}%")

# ---- per-RFD statistics ----
print("\n" + "="*118)
print("STATISTICHE PER RFD (chiave: RHS + LHS con soglie) — solo celle con ground truth")
print("="*118)
rfdstat = collections.defaultdict(lambda: dict(n=0, c=0, fams=set(), rhs=set(), lhs=set(), wsims=[]))
for r in covered:
    key = (r["rhs"], r["rhs_thr"], r["lhs"])
    s = rfdstat[key]
    s["n"] += 1; s["c"] += 1 if r["correct"] else 0
    s["fams"].add(r["family"]); s["rhs"].add(r["rhs"]); s["lhs"].add(r["lhs"])
    if r["wsim"] is not None: s["wsims"].append(r["wsim"])

tot_n = sum(s["n"] for s in rfdstat.values())
tot_c = sum(s["c"] for s in rfdstat.values())
print(f"RFD distinte usate: {len(rfdstat)}   imputazioni: {tot_n}   corrette: {tot_c} "
      f"({100*tot_c/max(1,tot_n):.1f}%)")

print("\n-- Top 25 RFD per numero di utilizzi --")
print(f"{'RHS':<10}{'thrR':>6}{'n':>6}{'corr':>6}{'acc%':>7}  LHS")
for k, s in sorted(rfdstat.items(), key=lambda kv: -kv[1]["n"])[:25]:
    lhs = ", ".join(f"{c}@{t:g}" for c, t in k[2])
    print(f"{k[0]:<10}{k[1]:>6g}{s['n']:>6}{s['c']:>6}{100*s['c']/s['n']:>7.1f}  [{lhs}]")

print("\n-- RFD usate piu' di 3 volte con accuratezza 0% (candidate al pruning) --")
z = [(k,s) for k,s in rfdstat.items() if s["n"]>=3 and s["c"]==0]
print(f"   conteggio: {len(z)}  imputazioni totali coinvolte: {sum(s['n'] for _,s in z)}")
for k, s in sorted(z, key=lambda kv: -kv[1]["n"])[:15]:
    lhs = ", ".join(f"{c}@{t:g}" for c, t in k[2])
    print(f"   {k[0]:<9} thrR={k[1]:<5g} n={s['n']:<4} [{lhs}]")

print("\n-- RFD 'single-use' (usate 1 volta) --")
one = [(k,s) for k,s in rfdstat.items() if s["n"]==1]
print(f"   conteggio: {len(one)}  di cui corrette: {sum(1 for _,s in one if s['c'])}")

json.dump([{k: (v if not isinstance(v, set) else list(v)) for k, v in r.items()} for r in recs],
          open(os.path.join(OUT, "results_parsed.json"), "w"), indent=1, default=str)
print(f"\n[scritto {OUT}/results_parsed.json]")
