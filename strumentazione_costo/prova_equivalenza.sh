#!/usr/bin/env bash
# =============================================================================================
# prova_equivalenza.sh — la ricostruzione dai sorgenti decompilati si comporta come l'originale?
#
# E' il controllo che legittima la misura del costo: se il JAR ricostruito non fosse equivalente
# all'originale, i tempi misurati su di esso non direbbero nulla sul sistema distribuito.
#
# Metodo: stessa macchina, stessa configurazione, cartelle di lavoro ISOLATE; l'unica variabile e'
# l'eseguibile. Si confrontano i file prodotti:
#     Populated/output_<dataset>_<soglia>H0.csv     celle imputate
#     Results/output_<dataset>_<soglia>H0.txt       esito per cella
# Questi due devono essere byte-identici. Il file Logs/ contiene i tempi di esecuzione e quindi
# differisce per costruzione: viene mostrato solo per informazione.
#
# Durata: circa due minuti.   Uso: bash strumentazione_costo/prova_equivalenza.sh
# =============================================================================================
set -u
cd "$(dirname "$0")"
STRUM="$PWD"
RADICE="$(cd .. && pwd)"
LAVORO="$RADICE/.scratch/costo/equiv"
DS="bridges_70_1.csv"
RFD="output_false_15_bridges.csv"
THR=15
CT="D,C,D,D,D,D,D,B,B,D,D,D,D"

if ! command -v java >/dev/null 2>&1; then
    echo "[errore] java non trovato: serve un JRE 8 o superiore"; exit 1
fi
if [ ! -f "$RADICE/RENUVER/Dataset/$DS" ]; then
    echo "[errore] serve il pacchetto completo: manca RENUVER/Dataset/$DS"; exit 1
fi

prepara() {
    local d="$1" jar="$2"
    rm -rf "$d"
    mkdir -p "$d"/{Dataset,RFD,TupleIniziali,Populated,Results,Logs}
    cp "$RADICE/RENUVER/Dataset/$DS" "$d/Dataset/$DS"
    cp "$RADICE/RENUVER/TupleIniziali/$DS" "$d/TupleIniziali/$DS" 2>/dev/null || true
    cp "$RADICE/RENUVER/RFD/$RFD" "$d/RFD/$RFD"
    cp "$jar" "$d/RENUVER.jar"
}

for coppia in "ORIGINALE:$RADICE/RENUVER/RENUVER_EDBT.jar" "RICOSTRUITO:$STRUM/RENUVER_clean.jar"; do
    tag="${coppia%%:*}"; jar="${coppia#*:}"; d="$LAVORO/$tag"
    prepara "$d" "$jar"
    echo "### $tag   $(basename "$jar")   md5 $(md5sum "$jar" | cut -c1-12)"
    t0=$(date +%s)
    ( cd "$d" && java -jar RENUVER.jar "$CT" "$DS" ";" "$RFD" "$THR" 0 >stdout.txt 2>stderr.txt )
    echo "    rc=$?   durata $(( $(date +%s) - t0 ))s"
done

echo
echo "==================== CONFRONTO ===================="
esito=0
for f in "Populated/output_${DS}_${THR}H0.csv" "Results/output_${DS}_${THR}H0.txt"; do
    a="$LAVORO/ORIGINALE/$f"; b="$LAVORO/RICOSTRUITO/$f"
    if [ -f "$a" ] && [ -f "$b" ]; then
        ma=$(md5sum "$a" | cut -c1-12); mb=$(md5sum "$b" | cut -c1-12)
        if [ "$ma" = "$mb" ]; then
            echo "  identico   $f   md5 $ma"
        else
            echo "  DIVERSO    $f   originale=$ma  ricostruito=$mb"; esito=1
        fi
    else
        echo "  assente    $f"; esito=1
    fi
done
echo
echo "  (il file Logs/ non entra nel confronto: registra tempi e memoria dell'esecuzione)"
normalizza() { sed -e 's/[0-9]\+ms//g' -e 's/[0-9]\+MB//g' "$1" 2>/dev/null; }
diff <(normalizza "$LAVORO/ORIGINALE/Logs/log_${DS}_${THR}H0.txt") \
     <(normalizza "$LAVORO/RICOSTRUITO/Logs/log_${DS}_${THR}H0.txt") \
     | head -10 | sed 's/^/      /'
echo
if [ "$esito" -eq 0 ]; then
    echo "ESITO: la ricostruzione e' equivalente all'originale sugli output confrontati."
else
    echo "ESITO: differenza negli output: la ricostruzione NON e' equivalente."
fi
echo "Esito registrato nella fase: in esiti/equivalenza.txt"
exit "$esito"
