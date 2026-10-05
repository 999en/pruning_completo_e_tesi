"""Termine di paragone banale per l'imputazione: la moda di colonna.

Il relatore ha chiesto una scala per i numeri assoluti: la tesi riporta accuratezze come 0,15 o
0,23 senza dire se siano poco o molto. Questo script calcola, sulle stesse celle valutate dal
sistema, l'accuratezza di un imputatore banale che sostituisce a ogni valore mancante la moda
della colonna osservata. Non esegue RENUVER: legge i dataset, il materiale di ground truth e i
file di risultato delle campagne già presenti.

Uso:  python3 pruning/trivial_baseline.py
Scrive `results/trivial_baseline.json` e stampa la tabella.
"""
import collections
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402

NULL = {"?", "", "na", "n/a", "null", "nan"}

# configurazioni con schema allineato fra dataset, ground truth e file di regole.
# Glass è escluso: i suoi dataset usano nomi posizionali (difetto D2), e l'abbinamento per nome
# non è definito senza la rinomina documentata nel capitolo sui difetti.
CONFIGS = [
    ("bridges", "bridges_14_1.csv", 9),
    ("bridges", "bridges_28_1.csv", 9),
    ("bridges", "bridges_42_1.csv", 9),
    ("bridges", "bridges_56_1.csv", 9),
    ("bridges", "bridges_70_1.csv", 9),
    ("bridges", "bridges_14_1.csv", 3),
    ("physician", "Physician_Compare_National_remodulated_0.005_13_1.csv", 3),
    ("physician", "Physician_Compare_National_remodulated_0.01_27_1.csv", 3),
]


def read_dataset(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        rows = [line.rstrip("\n").split(";") for line in fh if line.strip()]
    header, body = rows[0], rows[1:]
    return header, body


def modal_values(header, body):
    """Per ogni colonna, il valore più frequente fra quelli osservati (non nulli)."""
    moda = {}
    for i, nome in enumerate(header):
        conta = collections.Counter()
        for r in body:
            if i < len(r):
                v = r[i].strip()
                if v.lower() not in NULL:
                    conta[v] += 1
        moda[nome] = conta.most_common(1)[0][0] if conta else None
    return moda


def read_truth(path):
    celle = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            parti = line.rstrip("\n").split(";", 2)
            if len(parti) < 3:
                continue
            try:
                riga = int(parti[0])
            except ValueError:
                continue
            celle.append((riga, parti[1], parti[2]))
    return celle


def sistema_metrics(famiglia, ds_name, soglia):
    """Metriche della configurazione di partenza, dai file di risultato delle campagne."""
    for f in sorted(glob.glob(os.path.join(paths.RESULTS, "*.json"))):
        try:
            with open(f, encoding="utf-8") as fh:
                recs = json.load(fh)
        except Exception:                                        # noqa: BLE001
            continue
        if not isinstance(recs, list):
            continue
        for r in recs:
            if not isinstance(r, dict) or r.get("variant") != "A" or r.get("rc") != 0:
                continue
            base = ds_name[:-4]
            if "_" in base:
                nome, _, run = base.rpartition("_")
                try:
                    run = int(run)
                except ValueError:
                    nome, run = base, None
            else:
                nome, run = base, None
            if r.get("dataset") == nome and r.get("threshold") == soglia and (
                    run is None or r.get("run") == run):
                return r
    return None


def main():
    esiti = []
    print(f"{'configurazione':<52}{'celle':>7}{'moda':>9}{'sistema':>9}{'copertura':>10}")
    for famiglia, ds_name, soglia in CONFIGS:
        ds_path = os.path.join(paths.RENUVER, "Dataset", ds_name)
        ti_path = os.path.join(paths.RENUVER, "TupleIniziali", ds_name)
        if not (os.path.exists(ds_path) and os.path.exists(ti_path)):
            print(f"  {ds_name:<50} MANCANTE")
            continue
        header, body = read_dataset(ds_path)
        moda = modal_values(header, body)
        verita = read_truth(ti_path)
        if not verita:
            continue
        giuste = sum(1 for _, attr, val in verita if moda.get(attr) == val)
        acc_moda = giuste / len(verita)
        m = sistema_metrics(famiglia, ds_name, soglia)
        acc_sis = m.get("accuracy") if m else None
        cov_sis = m.get("coverage") if m else None
        esiti.append({
            "famiglia": famiglia, "dataset": ds_name, "soglia": soglia,
            "celle": len(verita), "moda_corrette": giuste, "accuratezza_moda": round(acc_moda, 4),
            "accuratezza_sistema": acc_sis, "copertura_sistema": cov_sis,
        })
        print(f"  {ds_name[:-4] + ' @' + str(soglia):<50}{len(verita):>7}{acc_moda:>9.3f}"
              f"{(acc_sis if acc_sis is not None else float('nan')):>9.3f}"
              f"{(cov_sis if cov_sis is not None else float('nan')):>10.3f}")

    # sintesi per famiglia
    print()
    for famiglia in ("bridges", "physician"):
        sub = [e for e in esiti if e["famiglia"] == famiglia and e["accuratezza_sistema"] is not None]
        if not sub:
            continue
        celle = sum(e["celle"] for e in sub)
        acc_moda = sum(e["moda_corrette"] for e in sub) / celle
        acc_sis = sum(e["accuratezza_sistema"] * e["celle"] for e in sub) / celle
        cov_sis = sum(e["copertura_sistema"] * e["celle"] for e in sub) / celle
        print(f"{famiglia:<12} n={len(sub):>2}  celle={celle:>5}  moda={acc_moda:.3f}  "
              f"sistema={acc_sis:.3f}  copertura sistema={cov_sis:.3f}")

    out = os.path.join(paths.RESULTS, "trivial_baseline.json")
    if not esiti:
        # Nessuna configurazione calcolabile: succede nella versione leggera del pacchetto, che
        # non contiene i dataset. Il file di risultato NON viene sovrascritto: contiene i numeri
        # della fase e un elenco vuoto non aggiungerebbe informazione.
        print(f"\n[nessun risultato] i dataset di RENUVER/Dataset/ non sono presenti: "
              f"{os.path.relpath(out, paths.ROOT)} non viene toccato.")
        return 0
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(esiti, fh, indent=1, ensure_ascii=False)
    print(f"\nscritto {os.path.relpath(out, paths.ROOT)}")
    return 0


if __name__ == "__main__":
    main()
