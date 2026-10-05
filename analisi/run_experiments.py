#!/usr/bin/env python3
"""Full pruning experiment matrix (slow: run in background)."""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from experiment import experiment, COLTYPES
from lab import OUT

CONFIGS = [
    # tag,                family,      dsfile,                        rfdfile,                            thr, variants
    ("b14_1_t15",  "bridges",    "bridges_14_1.csv",  "output_false_15_bridges.csv", 15,
     ["orig","p2cov","p3safe","p3aggr","p4lhs4","p2cov+p3safe"]),
    ("rest52_1_t15","restaurant","restaurant_52_1.csv","output_false_15_restaurant.csv", 15,
     ["orig","p2cov","p3safe","p3aggr","p4lhs4","p2cov+p3safe"]),
    ("glass22_1_t15","glass",    "glass_22_1.csv",     "output_false_15_glass.csv", 15,
     ["orig","p2cov","p3safe","p3aggr","p4lhs4","p2cov+p3safe"]),
    ("b70_1_t12",  "bridges",    "bridges_70_1.csv",  "output_false_12_bridges.csv", 12,
     ["orig","p2cov","p3safe","p2cov+p3safe"]),
    ("rest259_1_t9","restaurant","restaurant_259_1.csv","output_false_9_restaurant.csv", 9,
     ["orig","p2cov","p3safe","p3aggr","p2cov+p3safe"]),
]

if __name__ == "__main__":
    allres = []
    t0 = time.time()
    for c in CONFIGS:
        tag, family, dsfile, rfdfile, thr, variants = c
        try:
            allres += experiment(tag, family, dsfile, rfdfile, thr, variants)
        except Exception as e:
            print(f"!! config {tag} failed: {e}")
        json.dump(allres, open(os.path.join(OUT, "experiment.json"), "w"), indent=1)
        print(f"[{time.time()-t0:.0f}s] salvato {len(allres)} record")
    print("DONE")
