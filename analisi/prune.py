#!/usr/bin/env python3
"""Pruning strategies + experiment driver (fast, vectorised dominance)."""
import os, re, sys, json, shutil, subprocess, collections, time, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/RENUVER"
SCR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/.scratch"
LAB = os.path.join(SCR, "lab")
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/results/analisi"
NULLS = {"?", "", "null", "NULL", "NA", "nan", "NaN"}
COLTYPES = {"bridges": "D,C,D,D,D,D,D,B,B,D,D,D,D",
            "restaurant": "D,D,D,D,D,D",
            "glass": "D,D,D,D,D,D,D,D,D,D,D"}
os.makedirs(OUT, exist_ok=True)

is_null = lambda v: v in NULLS

def read_rfd(path):
    L = [l.rstrip("\n") for l in open(path, encoding="utf-8", errors="replace")]
    L = [l for l in L if l.strip()]
    return L[0].split(";"), L[0], L[1:]

def parse_row(header, line):
    c = line.split(";")
    if len(c) < len(header): c = c + ["?"] * (len(header) - len(c))
    rhs = c[0].strip()
    if rhs not in header: return None
    ri = header.index(rhs); lhs = {}; rhs_thr = None
    for i, a in enumerate(header):
        if i == 0: continue
        v = c[i].strip()
        if v == "?": continue
        try: t = float(v)
        except ValueError: continue
        if i == ri: rhs_thr = t
        else: lhs[a] = t
    if rhs_thr is None: return None
    return dict(rhs=rhs, rhs_thr=rhs_thr, lhs=lhs)

def read_dataset(path):
    L = [l.rstrip("\n") for l in open(path, encoding="utf-8", errors="replace") if l.strip()]
    attrs = L[0].split(";")
    rows = [dict(zip(attrs, (c.strip() for c in l.split(";")))) for l in L[1:]]
    return attrs, rows

# ------------------------------------------------------------------ masks
def mask_coverage(parsed, nullcells, attrs, dsrows):
    ok = []
    by_attr = collections.defaultdict(list)
    for ri, a in nullcells: by_attr[a].append(ri)
    for p in parsed:
        keep = False
        for ri in by_attr.get(p["rhs"], ()):
            row = dsrows[ri]
            if all((c in attrs) and not is_null(row[c]) for c in p["lhs"]):
                keep = True; break
        ok.append(keep)
    return ok

def mask_lhs_cap(parsed, cap): return [len(p["lhs"]) <= cap for p in parsed]

def _sig(p): return (p["rhs_thr"], tuple(sorted(p["lhs"].items())))

def mask_dom_exact(parsed):
    """Exact dominance among RFDs with the SAME RHS and the SAME LHS attribute set."""
    b = collections.defaultdict(list)
    for i, p in enumerate(parsed): b[(p["rhs"], frozenset(p["lhs"]))].append(i)
    keep = [True] * len(parsed)
    for k, idxs in b.items():
        if len(idxs) < 2: continue
        for i in idxs:
            for j in idxs:
                if i == j: continue
                ri, rj = parsed[i], parsed[j]
                if any(rj["lhs"][c] > ri["lhs"][c] for c in ri["lhs"]): continue
                if rj["rhs_thr"] > ri["rhs_thr"]: continue
                if _sig(rj) >= _sig(ri): continue
                keep[i] = False; break
    return keep

def mask_dom_super(parsed, max_extra=1):
    """Approximate: r removed if some r' has an LHS attribute set that is a superset of r's
    by at most `max_extra` attributes, thresholds <= on the shared attributes, and rhs_thr <= r's."""
    b = collections.defaultdict(list)
    for i, p in enumerate(parsed): b[(p["rhs"], frozenset(p["lhs"]))].append(i)
    keys = collections.defaultdict(list)
    for (rhs, S) in b: keys[rhs].append(S)
    keep = [True] * len(parsed)
    for i, r in enumerate(parsed):
        S = frozenset(r["lhs"])
        found = False
        for T in keys[r["rhs"]]:
            if not (S <= T) or len(T) - len(S) > max_extra or T == S: continue
            for j in b[(r["rhs"], T)]:
                q = parsed[j]
                if any(q["lhs"][c] > r["lhs"][c] for c in S): continue
                if q["rhs_thr"] > r["rhs_thr"]: continue
                found = True; break
            if found: break
        if found: keep[i] = False
    return keep

def mask_dom_sub(parsed, max_extra=1):
    """Approximate opposite direction (LHS subset) - the more aggressive rule."""
    b = collections.defaultdict(list)
    for i, p in enumerate(parsed): b[(p["rhs"], frozenset(p["lhs"]))].append(i)
    keys = collections.defaultdict(list)
    for (rhs, S) in b: keys[rhs].append(S)
    keep = [True] * len(parsed)
    for i, r in enumerate(parsed):
        S = frozenset(r["lhs"])
        found = False
        for T in keys[r["rhs"]]:
            if not (T <= S) or len(S) - len(T) > max_extra or T == S: continue
            for j in b[(r["rhs"], T)]:
                q = parsed[j]
                if any(q["lhs"][c] > r["lhs"][c] for c in T): continue
                if q["rhs_thr"] > r["rhs_thr"]: continue
                found = True; break
            if found: break
        if found: keep[i] = False
    return keep

def mask_rhs0(parsed):
    """Drop RFDs whose RHS threshold is 0 (exact FDs) and whose LHS is a key-like single column."""
    return [not (p["rhs_thr"] == 0.0 and len(p["lhs"]) <= 1) for p in parsed]

# ------------------------------------------------------------------ lab
def setup_lab():
    for d in ("Dataset", "RFD", "TupleIniziali", "Results", "Populated", "Logs", "NoKeyRFD"):
        os.makedirs(os.path.join(LAB, d), exist_ok=True)
    shutil.copy(os.path.join(SRC, "RENUVER_EDBT.jar"), LAB)

def clear_out():
    for d in ("Results", "Populated", "Logs", "NoKeyRFD"):
        p = os.path.join(LAB, d)
        if os.path.isdir(p):
            for f in os.listdir(p):
                fp = os.path.join(p, f)
                if os.path.isfile(fp): os.remove(fp)

def run_one(family, dsfile, rfdfile, thr, lines=None, header=None, timeout=5400):
    clear_out()
    if lines is None:
        shutil.copy(os.path.join(SRC, "RFD", rfdfile), os.path.join(LAB, "RFD", rfdfile))
    else:
        with open(os.path.join(LAB, "RFD", rfdfile), "w", encoding="utf-8") as fh:
            fh.write(header + "\n" + "\n".join(lines) + "\n")
    t0 = time.time()
    try:
        p = subprocess.run(["java", "-jar", "RENUVER_EDBT.jar", COLTYPES[family], dsfile, ";",
                            rfdfile, str(thr), "0"], cwd=LAB, capture_output=True, text=True, timeout=timeout)
        rc, err = p.returncode, p.stderr
    except subprocess.TimeoutExpired:
        rc, err = -9, "TIMEOUT"
    wall = time.time() - t0
    rec = dict(wall_s=round(wall, 1), rc=rc, stderr=err.strip().splitlines()[0][:200] if err.strip() else "")
    log = os.path.join(LAB, "Logs", f"log_{dsfile}_{thr}H0.txt")
    if os.path.exists(log) and os.path.getsize(log):
        for line in open(log, encoding="utf-8", errors="replace"):
            line = line.strip()
            n = lambda s: int(re.search(r"(-?\d+)", s).group(1)) if re.search(r"(-?\d+)", s) else None
            if   line.startswith("#RFD after remove:"): rec["rfd_after"] = n(line.split(":", 1)[1])
            elif line.startswith("Time required for pre"): rec["pre_ms"] = n(line.split(":", 1)[1])
            elif line.startswith("Total execution time"): rec["exec_ms"] = n(line)
            elif line.startswith("#Null cells:"): rec["null"] = n(line.split(":", 1)[1])
            elif line.startswith("#Cells not filled:"): rec["notfilled"] = n(line.split(":", 1)[1])
            elif line.startswith("Memory"): rec["mem"] = n(line.split(":", 1)[1])
    pop = os.path.join(LAB, "Populated", f"output_{dsfile}_{thr}H0.csv")
    nf = nc = nw = 0
    if os.path.exists(pop) and os.path.getsize(pop):
        for i, line in enumerate(open(pop, encoding="utf-8", errors="replace")):
            q = line.rstrip("\n").split(";")
            if i == 0 and q[0].lower().startswith("riga"): continue
            if len(q) < 4: continue
            gt, im = q[2].strip(), q[3].strip()
            if im in ("?", ""): nf += 1; continue
            if gt == im: nc += 1
            else:
                try:
                    nc += 1 if abs(float(gt) - float(im)) < 1e-9 else 0
                    nw += 0 if abs(float(gt) - float(im)) < 1e-9 else 1
                except ValueError: nw += 1
    rec.update(n_filled=nc + nw, n_correct=nc, n_wrong=nw, n_notfilled=nf)
    return rec

def run_config(family, dsfile, rfdfile, thr, variants):
    for f in (f"Dataset/{dsfile}", f"TupleIniziali/{dsfile}"):
        s = os.path.join(SRC, f)
        if os.path.exists(s): shutil.copy(s, os.path.join(LAB, f))
    header, hline, raw = read_rfd(os.path.join(SRC, "RFD", rfdfile))
    attrs, dsrows = read_dataset(os.path.join(SRC, "Dataset", dsfile))
    parsed, raws = [], []
    for l in raw:
        p = parse_row(header, l)
        if p is not None: parsed.append(p); raws.append(l)
    nullcells = [(ri, a) for ri, r in enumerate(dsrows) for a in attrs if is_null(r[a])]
    masks = {}
    for v in variants:
        if v == "orig": continue
        t0 = time.time()
        if v == "p2cov": masks[v] = mask_coverage(parsed, nullcells, attrs, dsrows)
        elif v == "p3exact": masks[v] = mask_dom_exact(parsed)
        elif v == "p3super": masks[v] = mask_dom_super(parsed, 1)
        elif v == "p3sub": masks[v] = mask_dom_sub(parsed, 1)
        elif v == "p4lhs4": masks[v] = mask_lhs_cap(parsed, 4)
        elif v == "prhs0": masks[v] = mask_rhs0(parsed)
        elif v == "combo":
            if "p2cov" not in masks: masks["p2cov"] = mask_coverage(parsed, nullcells, attrs, dsrows)
            if "p3exact" not in masks: masks["p3exact"] = mask_dom_exact(parsed)
            if "p4lhs4" not in masks: masks["p4lhs4"] = mask_lhs_cap(parsed, 4)
            masks[v] = [a and b and c for a, b, c in zip(masks["p2cov"], masks["p3exact"], masks["p4lhs4"])]
        print(f"    [mask {v}: {sum(masks[v])}/{len(parsed)} tenute, {time.time()-t0:.1f}s]", flush=True)
    tag = f"{family}/{dsfile}/{rfdfile}/thr{thr}"
    print(f"\n#### {tag}  RFD={len(parsed)}  celle_nulle={len(nullcells)}", flush=True)
    out = []
    for v in variants:
        if v == "orig":
            rec = run_one(family, dsfile, rfdfile, thr)
            nkept = len(parsed)
        else:
            kept = [l for l, k in zip(raws, masks[v]) if k]
            nkept = len(kept)
            rec = run_one(family, dsfile, rfdfile, thr, lines=kept, header=hline)
        rec.update(variant=v, n_rfd=nkept, n_rfd_all=len(parsed), config=tag,
                   family=family, dsfile=dsfile, thr=thr)
        out.append(rec)
        print(f"  {v:<9} rfd={nkept:>6} pre={rec.get('pre_ms',0):>7}ms exec={rec.get('exec_ms',0):>8}ms "
              f"wall={rec['wall_s']:>6}s null={rec.get('null')} notf={rec.get('notfilled')} "
              f"filled={rec['n_filled']} corr={rec['n_correct']} err={rec['n_wrong']} rc={rec['rc']}",
              flush=True)
    return out
