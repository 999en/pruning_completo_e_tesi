#!/usr/bin/env bash
# =============================================================================================
# esegui_strumentato.sh — riesegue la misura del costo computazionale (capitolo 2 della tesi).
#
# Esegue l'eseguibile STRUMENTATO sulle due configurazioni citate nella tabella del capitolo 2
# (bridges_70_1 a soglia 15 e bridges_14_1 a soglia 9) e stampa il blocco di strumentazione
# scritto nel file Logs/.
#
# L'eseguibile originale RENUVER/RENUVER_EDBT.jar NON viene toccato: si usa una build separata
# (RENUVER_instr.jar), ricostruita dai sorgenti decompilati e instrumentata con la tecnica dei
# wrapper descritta in instrument.py. La prova che la ricostruzione si comporta come l'originale
# e' in prova_equivalenza.sh.
#
# Durata: circa cinque minuti (la prima configurazione ne richiede quattro).
# Uso:    bash strumentazione_costo/esegui_strumentato.sh
# =============================================================================================
set -u
cd "$(dirname "$0")"
STRUM="$PWD"
RADICE="$(cd .. && pwd)"
LAVORO="$RADICE/.scratch/costo"
CT="D,C,D,D,D,D,D,B,B,D,D,D,D"

if ! command -v java >/dev/null 2>&1; then
    echo "[errore] java non trovato: serve un JRE 8 o superiore"; exit 1
fi
echo "java: $(java -version 2>&1 | head -1)"
echo "eseguibile strumentato: RENUVER_instr.jar  md5 $(md5sum "$STRUM/RENUVER_instr.jar" | cut -c1-12)"
echo "eseguibile originale  : RENUVER_EDBT.jar   md5 $(md5sum "$RADICE/RENUVER/RENUVER_EDBT.jar" | cut -c1-12)"
echo

esegui() {
    local ds="$1" thr="$2" tag="$3" d
    d="$LAVORO/INSTR_$tag"
    if [ ! -f "$RADICE/RENUVER/Dataset/$ds" ]; then
        echo "### $ds: dataset assente (serve il pacchetto completo)"; return 1
    fi
    rm -rf "$d"
    mkdir -p "$d"/{Dataset,RFD,TupleIniziali,Populated,Results,Logs}
    cp "$RADICE/RENUVER/Dataset/$ds" "$d/Dataset/$ds"
    cp "$RADICE/RENUVER/TupleIniziali/$ds" "$d/TupleIniziali/$ds" 2>/dev/null || true
    cp "$RADICE/RENUVER/RFD/output_false_${thr}_bridges.csv" "$d/RFD/rfd.csv"
    echo "### $ds  soglia $thr   (cartella isolata, nessuna esecuzione in parallelo)"
    local t0; t0=$(date +%s)
    ( cd "$d" && java -jar "$STRUM/RENUVER_instr.jar" "$CT" "$ds" ";" "rfd.csv" "$thr" 0 \
        >stdout.txt 2>stderr.txt )
    local rc=$?
    echo "    rc=$rc   durata $(( $(date +%s) - t0 ))s"
    if [ -f "$d/Logs/log_${ds}_${thr}H0.txt" ]; then
        sed -n '/STRUMENTAZIONE/,/Memory Consumption/p' "$d/Logs/log_${ds}_${thr}H0.txt" \
            | sed 's/^/    /'
    else
        echo "    log assente: esecuzione non riuscita"; tail -3 "$d/stderr.txt" | sed 's/^/    /'
    fi
    echo
}

esegui bridges_70_1.csv 15 b70
esegui bridges_14_1.csv 9  b14

cat <<'NOTA'
Che cosa dicono i numeri
------------------------
  * i CONTEGGI (n=531, n=151, n=293, n=8 e le 354 809 scansioni) sono proprieta' strutturali
    dell'esecuzione: si riproducono identici su qualunque macchina;
  * i TEMPI dipendono dall'hardware: nella misura della tesi la verifica dei veti assorbe
    il 99,2% del tempo su bridges_70_1 @15 e l'85,6% su bridges_14_1 @9; su un'altra macchina
    cambiano i millisecondi, non la ripartizione;
  * il confronto con i log della fase e' in esiti/log_strumentato_*.txt.
NOTA
