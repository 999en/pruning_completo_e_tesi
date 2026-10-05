#!/usr/bin/env bash
# =====================================================================================
# verifica_rapida.sh — controllo end-to-end del pacchetto in due o tre minuti.
#
#   1. versioni di Java e Python
#   2. impronta dell'eseguibile originale
#   3. verifica dei numeri della relazione e analisi statistica (nessuna esecuzione)
#   4. potatura garantita del file di regole di Bridges a soglia 9
#   5. esecuzione del sistema senza e con il file potato
#   6. confronto degli output e riepilogo
#
# Va eseguito dalla radice del pacchetto:  bash verifica_rapida.sh
# I file prodotti finiscono in .scratch/verifica_rapida/ (area di lavoro): la cartella
# RENUVER/ e i file consegnati non vengono toccati.
# Nella versione leggera (senza dataset) i passi 4-6 vengono saltati con un messaggio.
# =====================================================================================
set -u

DATASET="bridges_14_1.csv"
PREFISSO="bridges_14"   # nome del dataset senza il suffisso della ripetizione
SOGLIA=9
RFD="output_false_9_bridges.csv"
ATTESO_MD5="c7b9238d6631c64fadd47ebfae00db8e"
LAVORO=".scratch/verifica_rapida"

echo "=============================================================="
echo " Verifica rapida del pacchetto — semantic pruning per RENUVER"
echo "=============================================================="
echo

# ---------------------------------------------------------------- 1. ambiente
echo "[1/6] Ambiente"
if command -v java >/dev/null 2>&1; then
    echo "      Java:   $(java -version 2>&1 | head -1)"
else
    echo "      Java:   ASSENTE — installare un JRE (openjdk-17-jre o superiore)"; exit 1
fi
if command -v python3 >/dev/null 2>&1; then
    echo "      Python: $(python3 --version)"
else
    echo "      Python: ASSENTE — installare Python 3.10 o superiore"; exit 1
fi
echo

# ---------------------------------------------------------------- 2. integrita'
echo "[2/6] Integrità dell'eseguibile"
if [ -f "RENUVER/RENUVER_EDBT.jar" ]; then
    MD5=$(md5sum RENUVER/RENUVER_EDBT.jar | cut -d' ' -f1)
    if [ "$MD5" = "$ATTESO_MD5" ]; then
        echo "      impronta MD5 corretta: $MD5"
    else
        echo "      ATTENZIONE: impronta $MD5 diversa da quella attesa ($ATTESO_MD5)"
    fi
else
    echo "      eseguibile assente in RENUVER/"; exit 1
fi
echo

# ---------------------------------------------------------------- 3. numeri
echo "[3/6] Verifica dei numeri e analisi statistica (nessuna esecuzione del sistema)"
python3 pruning/audit_report.py 2>&1 | tail -2
echo "      controlli di regressione sui valori di p pubblicati:"
python3 pruning/stats_effects.py 2>&1 | grep -E "→ [0-9]+/[0-9]+ PASS" | head -1 | sed 's/^/     /' 
echo

# ---------------------------------------------------------------- 4-6. esecuzione
if [ ! -f "RENUVER/Dataset/$DATASET" ]; then
    echo "[4/6] Esecuzione saltata: il dataset RENUVER/Dataset/$DATASET non è presente."
    echo "      Il pacchetto è la versione leggera, che non include i dataset e il materiale di"
    echo "      ground truth. Per eseguire il sistema copiare RENUVER/Dataset/ e RENUVER/TupleIniziali/"
    echo "      dall'archivio originale, oppure usare il pacchetto completo."
    echo
    echo "Verifica conclusa (solo controlli offline)."
    exit 0
fi

mkdir -p "$LAVORO"
echo "[4/6] Potatura garantita del file di regole (strategia veto-cover, politica protect)"
python3 pruning/pruning.py \
    --rfd "RENUVER/RFD/$RFD" \
    --dataset "RENUVER/Dataset/$DATASET" \
    --ground-truth "RENUVER/TupleIniziali/$DATASET" \
    --output "$LAVORO/rfd_potato.csv" \
    --strategy veto-cover --veto-policy protect --report 2>&1 | tail -12
echo

echo "[5/6] Esecuzione del sistema nelle due configurazioni (può richiedere un paio di minuti)"
python3 pruning/benchmark.py \
    --datasets "$PREFISSO" --runs 1 --thresholds "$SOGLIA" \
    --variants "VC=veto-cover:protect" \
    --out "$LAVORO/verifica_rapida.json" >/dev/null 2>&1
if [ ! -s "$LAVORO/verifica_rapida.json" ] || [ "$(python3 -c "import json;print(len(json.load(open('$LAVORO/verifica_rapida.json'))))" 2>/dev/null)" = "0" ]; then
    echo "      esecuzione non riuscita: rilanciare il comando senza redirezione per vedere l'errore"
    exit 1
fi
echo "      esecuzione completata; risultati in $LAVORO/verifica_rapida.json"
echo

echo "[6/6] Confronto degli output"
python3 - "$LAVORO/verifica_rapida.json" <<'PY'
import collections, json, os, sys

percorso = sys.argv[1]
if not os.path.exists(percorso):
    sys.exit("      file di risultato assente")
recs = json.load(open(percorso, encoding="utf-8"))
by = collections.defaultdict(dict)
for r in recs:
    by[(r["threshold"], r["dataset"], r["run"])][r["variant"]] = r
print(f"      {'configurazione':<28}{'RFD':>8}{'rid. %':>9}{'imputate':>10}{'corrette':>10}{'esito':>12}")
for k, v in sorted(by.items()):
    a, b = v.get("A"), v.get("VC")
    if not a or not b:
        continue
    esito = "identico" if (a.get("correct") == b.get("correct") and
                           a.get("imputed") == b.get("imputed") and
                           a.get("wrong") == b.get("wrong")) else "DIVERSO"
    print(f"      {k[1] + ' @' + str(k[0]) + ' run' + str(k[2]):<28}"
          f"{a['rfd_in']:>8}{100 * b['rfd_reduction']:>9.1f}"
          f"{a['imputed']:>10}{a['correct']:>10}{esito:>12}")
print()
print("      Atteso: riduzione del 17,1 % (8 961 → 7 430 regole) e output identico alla")
print("      configurazione di partenza: stesse celle imputate, stesse corrette.")
PY

echo
echo "Verifica conclusa."
