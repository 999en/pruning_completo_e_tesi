#!/usr/bin/env python3
"""
merge_results.py — unisce piu' JSON prodotti da benchmark.py in un unico file.

Le campagne di Fase 6 girano una invocazione per soglia (per passare a `score-argmin` un
`--maxthr` appaiato ad args[4], che cambia con la soglia). Questo script ricompone i pezzi in un
unico JSON, senza duplicati e con la stessa convenzione di ordinamento di benchmark.py
(soglia -> dataset -> run -> variante).

    python3 pruning/merge_results.py --out results/results_scoreargmin_glass.json \
        results/results_scoreargmin_glass_t3.json results/results_scoreargmin_glass_t9.json ...
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import ROOT


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("inputs", nargs="+")
    args = ap.parse_args(argv)

    recs, seen, dup = [], set(), 0
    var_order = {}
    for path in args.inputs:
        if not os.path.exists(path):
            sys.exit(f"[errore] file mancante: {path}")
        for r in json.load(open(path)):
            key = (r.get("variant"), r["dataset"], r["run"], r["threshold"])
            if key in seen:
                dup += 1
                continue
            seen.add(key)
            var_order.setdefault(r.get("variant"), len(var_order))
            recs.append(r)
    recs.sort(key=lambda r: (r["threshold"], r["dataset"], r["run"],
                            var_order[r.get("variant")]))
    dest = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
    with open(dest, "w") as fh:
        json.dump(recs, fh, indent=1)

    print(f"uniti {len(args.inputs)} file -> {dest}")
    print(f"  record: {len(recs)}  duplicati scartati: {dup}")
    by = collections.Counter((r.get("variant"), r["threshold"]) for r in recs)
    for (v, t) in sorted(by, key=lambda x: (var_order[x[0]], x[1])):
        print(f"  {v:6s} soglia {t:<3d} {by[(v, t)]:>3d} configurazioni")


if __name__ == "__main__":
    main()
