#!/usr/bin/env python3
"""Experiment driver: baseline vs pruned RFD sets."""
import os, re, sys, json, shutil, time, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import (SRC, SCR, LAB, OUT, read_rfd, parse_row, read_dataset, setup_lab,
                 run_one, clear_out, is_null)

setup_lab()

def prep(family, dsfile, rfdfile, thr):
    shutil.copy(os.path.join(SRC, "Dataset", dsfile), os.path.join(LAB, "Dataset", dsfile))
    ti = os.path.join(SRC, "TupleIniziali", dsfile)
    if os.path.exists(ti): shutil.copy(ti, os.path.join(LAB, "TupleIniziali", dsfile))
    header, hline, rows = read_rfd(os.path.join(SRC, "RFD", rfdfile))
    attrs, dsrows = read_dataset(os.path.join(SRC, "Dataset", dsfile))
    parsed = [parse_row(header, l) for l in rows]
    keep_mask = [p is not None for p in parsed]
    parsed = [p for p in parsed if p is not None]
    raw = [l for l, k in zip(rows, keep_mask) if k]
    # null cells (skip attributes absent from the dataset)
    nullcells = [(ri, a) for ri, r in enumerate(dsrows) for a in attrs if is_null(r[a])]
    return header, hline, raw, parsed, attrs, dsrows, nullcells

def variants_for(family, dsfile, rfdfile, thr, parsed, attrs, dsrows, nullcells,
                 blacklist=None, lhs_cap=4, want=("orig","p2cov","p3safe","p3aggr","p4lhs4","p2cov+p3safe")):
    class NC(list): pass
    nc = NC(nullcells); nc.rowmap = dsrows
    masks = {}
    if "p2cov" in want or "p2cov+p3safe" in want:
        m = []
        for p in parsed:
            ok = False
            for (ri, a) in nullcells:
                if a != p["rhs"]: continue
                row = dsrows[ri]
                if all((c in attrs) and (not is_null(row[c])) for c in p["lhs"]):
                    ok = True; break
            m.append(ok)
        masks["p2cov"] = m
    if "p3safe" in want or "p2cov+p3safe" in want: masks["p3safe"] = v_dom_safe(parsed)
    if "p3aggr" in want: masks["p3aggr"] = v_dom_aggr(parsed)
    if "p4lhs4" in want: masks["p4lhs4"] = [len(p["lhs"]) <= lhs_cap for p in parsed]
    if blacklist:
        masks["p6data"] = [not (p["rhs"], p["rhs_thr"], tuple(sorted(p["lhs"].items()))) in blacklist for p in parsed]
    if "p2cov+p3safe" in want:
        masks["p2cov+p3safe"] = [a and b for a, b in zip(masks["p2cov"], masks["p3safe"])]
    if "all" in want:
        acc = [True]*len(parsed)
        for k in ("p2cov","p3safe","p4lhs4","p6data"):
            if k in masks: acc = [a and b for a, b in zip(acc, masks[k])]
        masks["all"] = acc
    return masks

def v_dom_safe(parsed):
    idx = collections.defaultdict(list)
    for i, p in enumerate(parsed): idx[p["rhs"]].append(i)
    keep = [True] * len(parsed)
    for rhs, group in idx.items():
        for i in group:
            ri = parsed[i]; si = set(ri["lhs"]); sig_i = (ri["rhs_thr"], tuple(sorted(ri["lhs"].items())))
            for j in group:
                if i == j: continue
                rj = parsed[j]; sj = set(rj["lhs"])
                if not si <= sj: continue
                if any(rj["lhs"][a] > ri["lhs"][a] for a in si): continue
                if rj["rhs_thr"] > ri["rhs_thr"]: continue
                sig_j = (rj["rhs_thr"], tuple(sorted(rj["lhs"].items())))
                if len(sj) == len(si) and sig_j >= sig_i: continue
                keep[i] = False; break
    return keep

def v_dom_aggr(parsed):
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
                if sj == si and rj["rhs_thr"] == ri["rhs_thr"] and j > i: continue
                keep[i] = False; break
    return keep

COLTYPES = {
    "bridges": "D,C,D,D,D,D,D,B,B,D,D,D,D",
    "restaurant": "D,D,D,D,D,D",
    "glass": "D,D,D,D,D,D,D,D,D,D,D",
}

def experiment(tag, family, dsfile, rfdfile, thr, variants, blacklist=None):
    header, hline, raw, parsed, attrs, dsrows, nullcells = prep(family, dsfile, rfdfile, thr)
    masks = variants_for(family, dsfile, rfdfile, thr, parsed, attrs, dsrows, nullcells, blacklist)
    ct = COLTYPES[family]
    out = []
    print(f"\n######## {tag}: {family} / {dsfile} / {rfdfile} thr={thr}  (RFD={len(parsed)}, null={len(nullcells)}) ########")
    for v in variants:
        if v == "orig":
            rec = run_one(ct, dsfile, ";", rfdfile, thr, 0, pruned_lines=None)
            nkept = len(parsed)
        else:
            m = masks.get(v)
            if m is None: continue
            kept = [l for l, k in zip(raw, m) if k]
            nkept = len(kept)
            rec = run_one(ct, dsfile, ";", rfdfile, thr, 0, pruned_lines=kept, header=hline)
        rec.update(variant=v, n_rfd_in=nkept, n_rfd_all=len(parsed), config=tag)
        out.append(rec)
        print(f"  {v:<12} rfd={nkept:>6} pre={rec.get('pre_ms',0):>7}ms exec={rec.get('exec_ms',0):>8}ms "
              f"wall={rec['wall_s']:>7}s null={rec.get('null')} notfilled={rec.get('notfilled')} "
              f"filled={rec['n_filled']} corr={rec['n_correct']} err={rec['n_wrong']} rc={rec['rc']} {rec['stderr'][:60]}")
    return out

if __name__ == "__main__":
    results = []
    # --- smoke test: verify the NoKeyRFD hook actually changes what RENUVER loads ---
    header, hline, raw, parsed, attrs, dsrows, nullcells = prep("bridges", "bridges_14_1.csv", "output_false_3_bridges.csv", 3)
    smoke = raw[:50]
    rec = run_one(COLTYPES["bridges"], "bridges_14_1.csv", ";", "output_false_3_bridges.csv", 3, 0,
                  pruned_lines=smoke, header=hline)
    print(f"SMOKE TEST NoKeyRFD: inviate 50 RFD -> #RFD lette = {rec.get('rfd')} (atteso <=50) rc={rec['rc']}")
    print(f"   log: pre={rec.get('pre_ms')}ms exec={rec.get('exec_ms')}ms filled={rec.get('n_filled')}")
