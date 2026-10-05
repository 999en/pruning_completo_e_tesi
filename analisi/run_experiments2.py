#!/usr/bin/env python3
"""Extended (slow) pruning experiment matrix."""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prune import setup_lab, run_config, OUT

CONFIGS = [
    # family,      dsfile,             rfdfile,                          thr, variants
    ("bridges", "bridges_14_1.csv", "output_false_15_bridges.csv", 15, ["orig","p2cov","p3sub","p3super","combo"]),
    ("bridges", "bridges_14_2.csv", "output_false_15_bridges.csv", 15, ["orig","p2cov","p3sub","combo"]),
    ("bridges", "bridges_14_3.csv", "output_false_15_bridges.csv", 15, ["orig","p2cov","p3sub","combo"]),
    ("bridges", "bridges_70_1.csv", "output_false_15_bridges.csv", 15, ["orig","p2cov","p3sub","combo"]),
    ("glass",   "glass_22_1.csv",   "output_false_15_glass.csv",   15, ["orig","p2cov","p3sub","combo"]),
    ("restaurant", "restaurant_259_1.csv", "output_false_9_restaurant.csv", 9, ["orig","p2cov","p3sub","combo"]),
    ("restaurant", "restaurant_52_1.csv",  "output_false_15_restaurant.csv", 15, ["orig","p2cov","p3sub","combo"]),
]

if __name__ == "__main__":
    setup_lab()
    allres = []
    t0 = time.time()
    for c in CONFIGS:
        try:
            allres += run_config(*c)
        except Exception as e:
            print(f"!! config {c[0]}/{c[1]} failed: {type(e).__name__}: {e}", flush=True)
        json.dump(allres, open(os.path.join(OUT, "experiment2.json"), "w"), indent=1)
        print(f"[{time.time()-t0:.0f}s] salvati {len(allres)} record", flush=True)
    print("DONE", flush=True)
