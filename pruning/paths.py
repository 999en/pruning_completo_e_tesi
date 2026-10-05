#!/usr/bin/env python3
"""
paths.py — risoluzione dei percorsi del progetto, indipendente da dove stanno gli script.

Gli script di `pruning/` devono poter trovare:
    RENUVER/     l'archivio e il JAR (input)
    results/     i JSON prodotti da benchmark.py (output)
    .scratch/    l'area di lavoro (laboratorio, file RFD potati, cache)
    report.md    il documento generato da fill_report.py

La radice viene individuata risalendo le cartelle finche' non si trova `RENUVER/`,
quindi lo spostamento degli script in una sottocartella non rompe nulla.
Si puo' forzare la radice con la variabile d'ambiente PRUNING_ROOT.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _find_root(start):
    env = os.environ.get("PRUNING_ROOT")
    if env and os.path.isdir(os.path.join(env, "RENUVER")):
        return os.path.abspath(env)
    d = start
    for _ in range(6):
        if os.path.isdir(os.path.join(d, "RENUVER")):
            return d
        parent = os.path.dirname(d)
        if parent == d:          # radice del filesystem
            break
        d = parent
    return start                 # fallback: la cartella dello script


ROOT = _find_root(HERE)
RENUVER = os.path.join(ROOT, "RENUVER")
RESULTS = os.path.join(ROOT, "results")
SCRATCH = os.path.join(ROOT, ".scratch")
LAB = os.path.join(SCRATCH, "bench_lab")
PRUNED_DIR = os.path.join(SCRATCH, "pruned")
REPORT = os.path.join(ROOT, "report.md")
BENCH_JSON = os.path.join(RESULTS, "results_benchmark.json")


def ensure_dirs():
    """Crea results/ e l'area di lavoro se mancano."""
    for d in (RESULTS, SCRATCH, LAB, PRUNED_DIR):
        os.makedirs(d, exist_ok=True)


if __name__ == "__main__":
    print(f"HERE     = {HERE}")
    print(f"ROOT     = {ROOT}")
    print(f"RENUVER  = {RENUVER}  ({'ok' if os.path.isdir(RENUVER) else 'MANCANTE'})")
    print(f"results  = {RESULTS}  ({'ok' if os.path.isdir(RESULTS) else 'MANCANTE'})")
    print(f".scratch = {SCRATCH}  ({'ok' if os.path.isdir(SCRATCH) else 'MANCANTE'})")
    print(f"report   = {REPORT}  ({'ok' if os.path.isfile(REPORT) else 'MANCANTE'})")
