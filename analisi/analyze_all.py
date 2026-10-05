#!/usr/bin/env python3
"""RENUVER archive: full analysis of Logs / Populated / Results / RFD."""
import os, re, json, collections, statistics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/RENUVER"
OUT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/results/analisi"
os.makedirs(OUT, exist_ok=True)

def ls(d):
    p = os.path.join(ROOT, d)
    return sorted(f for f in os.listdir(p) if not f.startswith("._") and f != ".DS_Store")

def family(base):
    b = re.sub(r"\.\.?csv$", "", base)              # strip extension
    b = re.sub(r"_remodulated_[\d.]+", "", b)       # remodulated marker
    b = re.sub(r"_\d+$", "", b)                     # strip run index
    return b

# ============================================================ 1. LOGS
def parse_log(txt):
    d = {}
    for line in txt.splitlines():
        line = line.strip()
        if not line: continue
        def num(s): 
            m = re.search(r"(-?\d+)", s); return int(m.group(1)) if m else None
        if   line.startswith("#RFD after remove:"):  d["rfd_after"]  = num(line.split(":",1)[1])
        elif line.startswith("Time required for pre"): d["t_pre_ms"]  = num(line.split(":",1)[1])
        elif line.startswith("Total execution time"):  d["t_exec_ms"] = num(line)
        elif line.startswith("#Null cells:"):          d["null_cells"] = num(line.split(":",1)[1])
        elif line.startswith("#Cells not filled:"):    d["not_filled"] = num(line.split(":",1)[1])
        elif line.startswith("Memory Consumption:"):   d["mem_mb"]     = num(line.split(":",1)[1])
    return d

K_H = re.compile(r"^(?P<base>.+)_(?P<thr>\d+)H(?P<heu>\d+)$")
logs, pops, ress = [], [], []
for f in ls("Logs"):
    stem = f[:-4] if f.endswith(".txt") else f
    if stem.startswith("log_"): stem = stem[4:]
    m = K_H.match(stem)
    if m:
        rec = parse_log(open(os.path.join(ROOT,"Logs",f),encoding="utf-8",errors="replace").read())
        rec.update(base=m["base"], thr=int(m["thr"]), heu=int(m["heu"]), file=f)
    else:
        stem2 = stem[:-4] if stem.endswith(".csv") else stem
        rec = {"base": stem2, "thr": None, "heu": 0, "file": f, "empty": True}
    rec["family"] = family(rec["base"])
    logs.append(rec)

for f in ls("Populated"):
    stem = f[:-4] if f.endswith(".csv") else f
    if stem.startswith("output_"): stem = stem[7:]
    m = K_H.match(stem)
    if m: pops.append(dict(base=m["base"], thr=int(m["thr"]), heu=int(m["heu"]), file=f))
    else:
        m2 = re.match(r"^results_(?P<thr>\d+)_(?P<base>.+)$", stem)
        if m2: pops.append(dict(base=m2["base"], thr=int(m2["thr"]), heu=0, file=f))
        else:  print("POP? ", f)

for f in ls("Results"):
    stem = f[:-4] if f.endswith(".txt") else f
    if stem.startswith("output_"): stem = stem[7:]
    m = K_H.match(stem)
    if m: ress.append(dict(base=m["base"], thr=int(m["thr"]), heu=int(m["heu"]), file=f))

for r in logs + pops + ress:
    r["family"] = family(r["base"])

print(f"LOGS={len(logs)} POPULATED={len(pops)} RESULTS={len(ress)}")

# ============================================================ 2. POPULATED -> accuracy
def parse_populated(path):
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            line = line.rstrip("\n").rstrip("\r")
            if not line: continue
            if i == 0 and line.lower().startswith("riga"): continue
            parts = line.split(";")
            if len(parts) < 4: continue
            row, attr, real, imp = parts[0], parts[1], parts[2], ";".join(parts[3:])
            rows.append((row, attr, real, imp))
    return rows

NUM = re.compile(r"^-?\d+(\.\d+)?$")
def close(a, b):
    if a == b: return True
    if NUM.match(a) and NUM.match(b):
        try:
            x, y = float(a), float(b)
            return abs(x - y) < 1e-9
        except ValueError: return False
    return False

pop_stats = []
detail = {}
for r in sorted(pops, key=lambda x: (x["family"], x["base"], x["thr"])):
    path = os.path.join(ROOT, "Populated", r["file"])
    rows = parse_populated(path)
    n = len(rows)
    filled = [x for x in rows if x[3] not in ("?", "")]
    correct = [x for x in filled if close(x[2], x[3])]
    wrong = [x for x in filled if not close(x[2], x[3])]
    st = dict(r, n_injected=n, n_filled=len(filled), n_correct=len(correct), n_wrong=len(wrong),
              coverage=len(filled)/n if n else 0,
              precision=len(correct)/len(filled) if filled else None,
              accuracy=len(correct)/n if n else 0)
    pop_stats.append(st)
    detail[r["file"]] = rows

json.dump([{k: v for k, v in s.items()} for s in pop_stats], open(os.path.join(OUT,"populated.json"),"w"), indent=1)

# aggregate
agg = collections.defaultdict(lambda: dict(n=0, f=0, c=0, w=0, runs=0))
for s in pop_stats:
    a = agg[(s["family"], s["thr"])]
    a["n"] += s["n_injected"]; a["f"] += s["n_filled"]; a["c"] += s["n_correct"]
    a["w"] += s["n_wrong"]; a["runs"] += 1

print("\n" + "="*110)
print("ACCURATEZZA PER FAMIGLIA x SOGLIA  (celle iniettate = ground truth)")
print("="*110)
print(f"{'famiglia':<46}{'thr':>4}{'run':>5}{'iniettate':>10}{'imputate':>10}{'corrette':>10}{'err':>6}{'cover%':>8}{'prec%':>7}{'acc%':>7}")
for (fam, thr), a in sorted(agg.items(), key=lambda kv: (kv[0][0], kv[0][1] or 0)):
    print(f"{fam:<46}{str(thr):>4}{a['runs']:>5}{a['n']:>10}{a['f']:>10}{a['c']:>10}{a['w']:>6}"
          f"{100*a['f']/max(1,a['n']):>8.1f}{100*a['c']/max(1,a['f']):>7.1f}{100*a['c']/max(1,a['n']):>7.1f}")

# ============================================================ 3. LOGS aggregates
print("\n" + "="*110)
print("TEMPI E CARICO PER FAMIGLIA x SOGLIA (solo log non vuoti)")
print("="*110)
lagg = collections.defaultdict(list)
for r in logs:
    if r.get("null_cells") is None: continue
    lagg[(r["family"], r["thr"])].append(r)
print(f"{'famiglia':<46}{'thr':>4}{'n':>4}{'rfd_dopo':>10}{'null':>8}{'non_imp':>9}{'pre_ms':>9}{'exec_ms':>9}{'mem_MB':>8}")
for (fam, thr), v in sorted(lagg.items(), key=lambda kv: (kv[0][0], kv[0][1] or 0)):
    m = lambda k: statistics.mean([x[k] for x in v if x.get(k) is not None]) if any(x.get(k) is not None for x in v) else 0
    print(f"{fam:<46}{str(thr):>4}{len(v):>4}{m('rfd_after'):>10.0f}{m('null_cells'):>8.0f}{m('not_filled'):>9.0f}"
          f"{m('t_pre_ms'):>9.0f}{m('t_exec_ms'):>9.0f}{m('mem_mb'):>8.0f}")

empty = [r for r in logs if r.get("empty")]
print(f"\nLog vuoti (nessuna statistica): {len(empty)}  es: {[r['file'] for r in empty[:3]]}")

# ============================================================ 4. RFD FILES
print("\n" + "="*110)
print("FILE RFD")
print("="*110)
rfd_files = [f for f in ls("RFD") if f.endswith(".csv")]
rfd_info = {}
for f in rfd_files:
    lines = open(os.path.join(ROOT,"RFD",f), encoding="utf-8", errors="replace").read().splitlines()
    lines = [l for l in lines if l.strip()]
    if not lines: continue
    header = lines[0].split(";")
    rows = [l.split(";") for l in lines[1:]]
    by_rhs = collections.Counter(r[0] for r in rows)
    lhs_sizes = collections.Counter(sum(1 for x in r[1:] if x not in ("?", "")) for r in rows)
    rhs_thr = collections.Counter(r[header.index(r[0])] if False else None for r in rows)
    # RHS threshold = value in the column of its own attribute name
    rhs_thr = collections.Counter()
    for r in rows:
        nm = r[0]
        if nm in header:
            rhs_thr[r[header.index(nm)]] += 1
    rfd_info[f] = dict(n=len(rows), cols=len(header)-1, by_rhs=dict(by_rhs),
                       lhs_sizes=dict(sorted(lhs_sizes.items())), rhs_thr=dict(sorted(rhs_thr.items(), key=lambda kv: float(kv[0]) if kv[0] not in("?","") else -1)))
    print(f"{f:<50} RFD={len(rows):>6}  attributi={len(header)-1:>3}  "
          f"LHS_size_medio={statistics.mean([int(k) for k,v in lhs_sizes.items() for _ in range(v)]):>4.1f}  "
          f"RHS_distinti={len([k for k,v in by_rhs.items() if v]):>3}")
json.dump(rfd_info, open(os.path.join(OUT,"rfd_info.json"),"w"), indent=1)

print("\n--- Dettaglio RFD per attributo RHS (bridges: soglie 3 vs 15) ---")
for f in ["output_false_3_bridges.csv","output_false_15_bridges.csv","output_false_3_restaurant.csv","output_false_15_restaurant.csv"]:
    if f in rfd_info:
        info = rfd_info[f]
        print(f"\n{f}  (tot {info['n']})")
        for k, v in sorted(info["by_rhs"].items(), key=lambda kv: -kv[1]):
            print(f"    RHS={k:<12} n={v:>6}  ({100*v/info['n']:>5.1f}%)")

print("\n--- distribuzione soglia RHS (bridges) ---")
for f in ["output_false_3_bridges.csv","output_false_15_bridges.csv"]:
    if f in rfd_info:
        print(f"{f}: {rfd_info[f]['rhs_thr']}")
