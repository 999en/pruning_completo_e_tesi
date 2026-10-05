#!/usr/bin/env python3
"""Build pruned variants of an RFD file and run RENUVER on each, measuring time/cost/quality.

Injection mechanism: RENUVER (FillingAlgorithm constructor) looks for
    <cwd>/NoKeyRFD/<rfdFileName>
and uses it INSTEAD of <cwd>/RFD/<rfdFileName> when present.
So we drop a pruned file with the identical basename into NoKeyRFD/.
"""
import os, re, sys, json, shutil, subprocess, collections, statistics, time

SRC   = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/RENUVER"
SCR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/.scratch"
LAB   = os.path.join(SCR, "lab")
OUT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/results/analisi"
NULLS = {"?", "", "null", "NULL", "NA", "nan", "NaN"}
os.makedirs(OUT, exist_ok=True)

def is_null(v): return v in NULLS

def read_rfd(path):
    lines = [l.rstrip("\n") for l in open(path, encoding="utf-8", errors="replace")]
    lines = [l for l in lines if l.strip()]
    header = lines[0].split(";")
    return header, lines[0], lines[1:]

def parse_row(header, line):
    c = line.split(";")
    if len(c) < len(header): c = c + ["?"] * (len(header) - len(c))
    rhs = c[0].strip()
    if rhs not in header: return None
    ri = header.index(rhs)
    lhs = {}
    rhs_thr = None
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
    lines = [l.rstrip("\n") for l in open(path, encoding="utf-8", errors="replace") if l.strip()]
    attrs = lines[0].split(";")
    rows = []
    for l in lines[1:]:
        c = l.split(";")
        rows.append({a: (c[i].strip() if i < len(c) else "") for i, a in enumerate(attrs)})
    return attrs, rows

# ---------------------------------------------------------------- variants
def v_coverage(parsed, nullcells, attrs):
    """P2: keep only RFDs applicable to >=1 null cell (all LHS columns non-null in that row)."""
    ok = []
    for p in parsed:
        keep = False
        for (ri, a) in nullcells:
            if a != p["rhs"]: continue
            row = nullcells.rowmap[ri]
            if all(not is_null(row[c]) for c in p["lhs"] if c in attrs):
                keep = True; break
        ok.append(keep)
    return ok

def v_lhs_cap(parsed, cap):
    return [len(p["lhs"]) <= cap for p in parsed]

def v_dom_safe(parsed):
    """Remove r if some r' has LHS superset of r's, thresholds <= on shared attrs, rhs_thr <= r's,
    and r' != r.  Then candidates(r') subset-of candidates(r) -> r adds no candidate."""
    idx = collections.defaultdict(list)
    for i, p in enumerate(parsed): idx[p["rhs"]].append(i)
    keep = [True] * len(parsed)
    for rhs, group in idx.items():
        for i in group:
            ri = parsed[i]
            si = set(ri["lhs"])
            for j in group:
                if i == j: continue
                rj = parsed[j]
                sj = set(rj["lhs"])
                if not si <= sj: continue                   # j must constrain at least as much
                if len(sj) == len(si):
                    # identical attribute set: need j strictly tighter or equal on all, and rhs <=
                    if any(rj["lhs"][a] > ri["lhs"][a] for a in si): continue
                    if rj["rhs_thr"] > ri["rhs_thr"]: continue
                    if (rj["rhs_thr"], tuple(sorted(rj["lhs"].items()))) >= (ri["rhs_thr"], tuple(sorted(ri["lhs"].items()))):
                        continue                             # avoid mutual removal; keep the "smaller" one
                else:
                    if any(rj["lhs"][a] > ri["lhs"][a] for a in si): continue
                    if rj["rhs_thr"] > ri["rhs_thr"]: continue
                keep[i] = False
                break
    return keep

def v_dom_aggr(parsed):
    """Remove r if some r' has LHS subset of r's with thresholds <=, rhs_thr <= r's."""
    idx = collections.defaultdict(list)
    for i, p in enumerate(parsed): idx[p["rhs"]].append(i)
    keep = [True] * len(parsed)
    for rhs, group in idx.items():
        for i in group:
            ri = parsed[i]; si = set(ri["lhs"])
            for j in group:
                if i == j: continue
                rj = parsed[j]; sj = set(rj["lhs"])
                if not sj <= si: continue
                if any(rj["lhs"][a] > ri["lhs"][a] for a in sj): continue
                if rj["rhs_thr"] > ri["rhs_thr"]: continue
                if sj == si and rj["rhs_thr"] == ri["rhs_thr"]: 
                    if j > i: continue
                keep[i] = False; break
    return keep

class NullCells(list):
    pass

# ---------------------------------------------------------------- lab runner
def setup_lab():
    for d in ("Dataset", "RFD", "TupleIniziali", "Results", "Populated", "Logs", "NoKeyRFD"):
        os.makedirs(os.path.join(LAB, d), exist_ok=True)
    shutil.copy(os.path.join(SRC, "RENUVER_EDBT.jar"), LAB)
    return LAB

def clear_out():
    for d in ("Results", "Populated", "Logs", "NoKeyRFD"):
        p = os.path.join(LAB, d)
        if os.path.isdir(p):
            for f in os.listdir(p): os.remove(os.path.join(p, f))

def run_one(coltypes, dsfile, sep, rfdfile, thr, heu, pruned_lines=None, header=None, timeout=3600):
    clear_out()
    if pruned_lines is None:
        # baseline: restore the pristine RFD file, and make sure no pruned copy lingers
        shutil.copy(os.path.join(SRC, "RFD", rfdfile), os.path.join(LAB, "RFD", rfdfile))
    else:
        body = header + "\n" + "\n".join(pruned_lines) + "\n"
        with open(os.path.join(LAB, "RFD", rfdfile), "w", encoding="utf-8") as fh:
            fh.write(body)
        # also place in NoKeyRFD so that RENUVER definitely uses the pruned set
        with open(os.path.join(LAB, "NoKeyRFD", rfdfile), "w", encoding="utf-8") as fh:
            fh.write(body)
    t0 = time.time()
    try:
        p = subprocess.run(["java", "-jar", "RENUVER_EDBT.jar", coltypes, dsfile, sep, rfdfile, str(thr), str(heu)],
                           cwd=LAB, capture_output=True, text=True, timeout=timeout)
        rc, outp, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        rc, outp, err = -9, "", "TIMEOUT"
    wall = time.time() - t0
    log = os.path.join(LAB, "Logs", f"log_{dsfile}_{thr}H{heu}.txt")
    pop = os.path.join(LAB, "Populated", f"output_{dsfile}_{thr}H{heu}.csv")
    res = os.path.join(LAB, "Results", f"output_{dsfile}_{thr}H{heu}.txt")
    rec = dict(wall_s=round(wall, 1), rc=rc, stderr=err.strip()[:300])
    if os.path.exists(log) and os.path.getsize(log):
        for line in open(log, encoding="utf-8", errors="replace"):
            line = line.strip()
            def n(s):
                m = re.search(r"(-?\d+)", s); return int(m.group(1)) if m else None
            if   line.startswith("#RFD after remove:"): rec["rfd"] = n(line.split(":",1)[1])
            elif line.startswith("Time required for pre"): rec["pre_ms"] = n(line.split(":",1)[1])
            elif line.startswith("Total execution time"): rec["exec_ms"] = n(line)
            elif line.startswith("#Null cells:"): rec["null"] = n(line.split(":",1)[1])
            elif line.startswith("#Cells not filled:"): rec["notfilled"] = n(line.split(":",1)[1])
            elif line.startswith("Memory"): rec["mem"] = n(line.split(":",1)[1])
    rec["n_results"] = 0
    if os.path.exists(res):
        rec["n_results"] = sum(1 for _ in open(res, encoding="utf-8", errors="replace"))
    # accuracy vs ground truth
    ti = os.path.join(LAB, "TupleIniziali", dsfile)
    truth = {}
    if os.path.exists(ti):
        for line in open(ti, encoding="utf-8", errors="replace"):
            q = line.rstrip("\n").split(";")
            if len(q) >= 3: truth[(q[0].strip(), q[1].strip())] = q[2].strip()
    nf = nc = nw = 0
    if os.path.exists(pop) and os.path.getsize(pop):
        for i, line in enumerate(open(pop, encoding="utf-8", errors="replace")):
            q = line.rstrip("\n").split(";")
            if i == 0 and q[0].lower().startswith("riga"): continue
            if len(q) < 4: continue
            gt = q[2].strip(); im = q[3].strip()
            if im in ("?", ""):
                nf += 1; continue
            if gt == im or (re.match(r"^-?\d+(\.\d+)?$", gt) and re.match(r"^-?\d+(\.\d+)?$", im)
                            and abs(float(gt) - float(im)) < 1e-9): nc += 1
            else: nw += 1
    rec.update(n_filled=nc+nw, n_correct=nc, n_wrong=nw, n_notfilled=nf)
    return rec
