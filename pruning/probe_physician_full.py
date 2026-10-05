"""Sonda limitata sulla configurazione piena della famiglia Physician.

Le configurazioni non remodulate hanno 103 592 righe e fino a 13 467 celle da imputare: la tesi
afferma che una singola esecuzione non è compatibile con una campagna, e questa sonda serve a
sostituire la stima con una misura. Il file `Results/` viene scritto **in modo incrementale**,
una riga per cella imputata: contarne le righe durante l'esecuzione fornisce la velocità di
avanzamento, e quindi la proiezione del tempo totale.

L'esecuzione viene interrotta dopo `--timeout` secondi. Non modifica l'archivio: lavora nella
copia di laboratorio (`.scratch/bench_lab`) e scrive il proprio esito in
`results/probe_physician_full.json`.

Uso:  python3 pruning/probe_physician_full.py [--timeout 1200] [--poll 30]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402

DS = "Physician_Compare_National_13467_1.csv"
RFD = "output_false_3_Physician_Compare_National.csv"
COLTYPES = "D," * 12 + "D"
MAXTHR = 3
CELLS = 13467


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--timeout", type=int, default=1200, help="secondi prima dell'interruzione")
    ap.add_argument("--poll", type=int, default=30, help="intervallo di campionamento in secondi")
    ap.add_argument("--out", default=os.path.join(paths.RESULTS, "probe_physician_full.json"))
    args = ap.parse_args(argv)

    lab = paths.LAB
    for d in ("Dataset", "RFD", "TupleIniziali", "Results", "Populated", "Logs"):
        os.makedirs(os.path.join(lab, d), exist_ok=True)
    shutil.copy(os.path.join(paths.RENUVER, "RENUVER_EDBT.jar"), os.path.join(lab, "RENUVER_EDBT.jar"))
    shutil.copy(os.path.join(paths.RENUVER, "Dataset", DS), os.path.join(lab, "Dataset", DS))
    shutil.copy(os.path.join(paths.RENUVER, "TupleIniziali", DS), os.path.join(lab, "TupleIniziali", DS))
    shutil.copy(os.path.join(paths.RENUVER, "RFD", RFD), os.path.join(lab, "RFD", RFD))

    res = os.path.join(lab, "Results", f"output_{DS}_{MAXTHR}H0.txt")
    pop = os.path.join(lab, "Populated", f"output_{DS}_{MAXTHR}H0.csv")
    for path in (res, pop):
        if os.path.exists(path):
            os.remove(path)                      # misura pulita: nessun residuo di run precedenti

    print(f"comando: java -jar RENUVER_EDBT.jar {COLTYPES} {DS} ; {RFD} {MAXTHR} 0")
    print(f"celle da imputare: {CELLS}; interruzione dopo {args.timeout}s\n")
    t0 = time.time()
    proc = subprocess.Popen(
        ["java", "-jar", "RENUVER_EDBT.jar", COLTYPES, DS, ";", RFD, str(MAXTHR), "0"],
        cwd=lab, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    samples = []
    while True:
        time.sleep(args.poll)
        elapsed = time.time() - t0
        lines = sum(1 for _ in open(res, encoding="utf-8", errors="replace")) if os.path.exists(res) else 0
        samples.append({"t": round(elapsed, 1), "righe_results": lines})
        rate = lines / elapsed if elapsed > 0 else 0.0
        print(f"  t={elapsed:7.1f}s  righe Results={lines:6d}  velocità={rate:6.2f} righe/s"
              f"  proiezione={CELLS / rate / 3600:7.2f} h" if rate > 0 else
              f"  t={elapsed:7.1f}s  righe Results={lines:6d}  (nessun avanzamento misurabile)")
        if proc.poll() is not None:
            break
        if elapsed >= args.timeout:
            proc.kill()
            proc.wait()
            break

    elapsed = time.time() - t0
    rc = proc.returncode
    lines = sum(1 for _ in open(res, encoding="utf-8", errors="replace")) if os.path.exists(res) else 0
    log_path = os.path.join(lab, "Logs", f"log_{DS}_{MAXTHR}H0.txt")
    log_size = os.path.getsize(log_path) if os.path.exists(log_path) else 0
    rate = lines / elapsed if elapsed > 0 else 0.0
    out = {
        "dataset": DS, "rfd": RFD, "maxthr": MAXTHR, "celle_da_imputare": CELLS,
        "timeout_s": args.timeout, "elapsed_s": round(elapsed, 1), "rc": rc,
        "righe_results": lines, "log_bytes": log_size,
        "velocita_righe_s": round(rate, 3),
        "proiezione_ore": round(CELLS / rate / 3600, 2) if rate > 0 else None,
        "campioni": samples,
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    print(f"\nesito: rc={rc}  tempo={out['elapsed_s']}s  righe Results={lines}  log={log_size} byte")
    if rate > 0:
        print(f"proiezione per {CELLS} celle: {out['proiezione_ore']} ore")
    print(f"scritto {os.path.relpath(args.out, paths.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
