#!/usr/bin/env python3
"""Inventory + log parsing for the RENUVER experiment archive."""
import os, re, json, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/RENUVER"
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/results/analisi"
os.makedirs(OUT, exist_ok=True)

def listdir(d):
    return sorted(f for f in os.listdir(os.path.join(ROOT, d))
                  if not f.startswith("._") and f != ".DS_Store")

# ---------- filename key:  <name>_<thr>H<heu>  ----------
KEYRE = re.compile(r"^(?P<base>.+)_(?P<thr>\d+)H(?P<heu>\d+)$")

def keyof(fname, prefix):
    stem = fname
    if prefix and stem.startswith(prefix):
        stem = stem[len(prefix):]
    for ext in (".csv", ".txt"):
        if stem.endswith(ext):
            stem = stem[: -len(ext)]
    m = KEYRE.match(stem)
    if not m:
        return None
    return (m.group("base"), int(m.group("thr")), int(m.group("heu")))

logs = {}
for f in listdir("Logs"):
    k = keyof(f, "log_")
    if not k:
        print("UNPARSED LOG:", f); continue
    logs[k] = f

pops = {}
for f in listdir("Populated"):
    k = keyof(f, "output_")
    if not k:
        print("UNPARSED POP:", f); continue
    pops[k] = f

ress = {}
for f in listdir("Results"):
    k = keyof(f, "output_")
    if not k:
        print("UNPARSED RES:", f); continue
    ress[k] = f

print(f"logs={len(logs)} populated={len(pops)} results={len(ress)}")
print("keys only in logs   :", len(set(logs) - set(pops)), sorted(set(logs) - set(pops))[:5])
print("keys only in pops   :", len(set(pops) - set(logs)), sorted(set(pops) - set(logs))[:5])
print("keys only in results:", len(set(ress) - set(logs)), sorted(set(ress) - set(logs))[:5])

# ---------- parse logs ----------
def INT(s):
    """Intero contenuto nella riga; None se il campo e' vuoto (run interrotti: i log di
    restaurant_1555_1, restaurant_259_1 e restaurant_518_1 non riportano tempo e memoria)."""
    d = re.sub(r"[^\d-]", "", s)
    return int(d) if d not in ("", "-") else None
logrows = []
for (base, thr, heu), f in sorted(logs.items()):
    txt = open(os.path.join(ROOT, "Logs", f), encoding="utf-8", errors="replace").read()
    d = {"base": base, "thr": thr, "heu": heu, "file": f}
    for line in txt.splitlines():
        line = line.strip()
        if not line: continue
        if line.startswith("#RFD after remove:"):
            d["rfd_after"] = INT(line.split(":")[1])
        elif line.startswith("Time required for pre processing:"):
            d["t_pre_ms"] = INT(line.split(":")[1])
        elif line.startswith("Total execution time"):
            d["t_exec_ms"] = INT(line.replace("Total execution time", "").strip())
        elif line.startswith("#Null cells:"):
            d["null_cells"] = INT(line.split(":")[1])
        elif line.startswith("#Cells not filled:"):
            d["not_filled"] = INT(line.split(":")[1])
        elif line.startswith("Memory Consumption:"):
            d["mem_mb"] = INT(line.split(":")[1])
        elif line.startswith("Removing key RFD"):
            d["removed_key"] = True
        else:
            d.setdefault("unparsed", []).append(line)
    vuoti = sorted(k for k, v in d.items() if v is None)
    if vuoti:
        d["senza_valore"] = vuoti                     # campi assenti nel log, non persi
    logrows.append({k: v for k, v in d.items() if v is not None})

json.dump(logrows, open(os.path.join(OUT, "logs.json"), "w"), indent=1)
print("\n=== LOG ROWS:", len(logrows))
missing = [r for r in logrows if "not_filled" not in r]
print("logs without #Cells not filled:", len(missing))
for r in missing[:10]: print("   ", r)

# ---------- aggregate logs ----------
print("\n=== LOG STATS by base family ===")
fam = collections.defaultdict(list)
for r in logrows:
    fam[re.sub(r"_\d+$", "", r["base"])].append(r)
for k, v in sorted(fam.items()):
    filled = [x["null_cells"] - x["not_filled"] for x in v if "not_filled" in x]
    pre = [x["t_pre_ms"] for x in v if "t_pre_ms" in x]
    ex = [x["t_exec_ms"] for x in v if "t_exec_ms" in x]
    if not v: continue
    print(f"  {k:55s} n={len(v):3d} "
          f"null~{sum(x.get('null_cells',0) for x in v)//max(1,len(v)):6d} "
          f"filled%={100*sum(filled)/max(1,sum(x['null_cells'] for x in v if 'not_filled' in x)):5.1f} "
          f"pre={sum(pre)//max(1,len(pre)):6d}ms exec={sum(ex)//max(1,len(ex)):6d}ms")
