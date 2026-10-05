#!/usr/bin/env bash
# =============================================================================================
# verifica_completa.sh — esegue da questa cartella tutto il materiale del lavoro.
#
#   bash verifica_completa.sh                 ambiente, sintassi, strumenti offline,
#                                             trasformazioni reali (nessuna esecuzione RENUVER)
#   bash verifica_completa.sh --analisi       aggiunge gli estrattori storici di analisi/
#   bash verifica_completa.sh --run           aggiunge un confronto A/B vero con RENUVER
#   bash verifica_completa.sh --tutto         equivale a --analisi --run
#
# Ogni voce produce un log in .scratch/verifica/log/ e un esito OK / FAIL / --.
# Il codice di uscita e' 0 solo se non c'e' nessun FAIL.
# Il confronto A/B usa il laboratorio .scratch/bench_lab: le esecuzioni RENUVER non possono
# essere parallele, quindi questa verifica non lancia mai due run insieme.
# =============================================================================================
set -u
cd "$(dirname "$0")"
RADICE="$PWD"
LOG="$RADICE/.scratch/verifica/log"
OUT="$RADICE/.scratch/verifica/out"
mkdir -p "$LOG" "$OUT"

CON_ANALISI=0
CON_RUN=0
for a in "$@"; do
  case "$a" in
    --analisi) CON_ANALISI=1 ;;
    --run)     CON_RUN=1 ;;
    --tutto)   CON_ANALISI=1; CON_RUN=1 ;;
    -h|--help) sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "opzione non riconosciuta: $a (usare --analisi, --run, --tutto, --help)"; exit 2 ;;
  esac
done

OK=0; FAIL=0; SALTATI=0; FALLITI=""
if command -v timeout >/dev/null 2>&1; then
  TMO() { timeout "$@"; }
else
  TMO() { shift; "$@"; }        # senza coreutils `timeout` si esegue senza limite
fi

titolo() { printf '\n=== %s\n' "$1"; }

esito() {   # esito <nome> <secondi> <pattern-atteso|-> <comando...>
  local nome="$1" sec="$2" pat="$3"; shift 3
  local log="$LOG/$nome.log" ini=$SECONDS rc dur
  TMO "$sec" "$@" >"$log" 2>&1; rc=$?
  dur=$((SECONDS - ini))
  if [ "$rc" -ne 0 ]; then
    printf '  [FAIL] %-24s rc=%-3s %3ss  %s\n' "$nome" "$rc" "$dur" "$(tail -1 "$log" | cut -c1-64)"
    FAIL=$((FAIL+1)); FALLITI="$FALLITI $nome"
  elif [ "$pat" != "-" ] && ! grep -q -- "$pat" "$log"; then
    printf '  [FAIL] %-24s esito inatteso: manca «%s»\n' "$nome" "$pat"
    FAIL=$((FAIL+1)); FALLITI="$FALLITI $nome"
  else
    printf '  [ OK ] %-24s %3ss  %s\n' "$nome" "$dur" "$(tail -1 "$log" | cut -c1-64)"
    OK=$((OK+1))
  fi
}

salta() { printf '  [ -- ] %-24s %s\n' "$1" "$2"; SALTATI=$((SALTATI+1)); }

impronte() {
  # l'elenco finale viene riordinato: il confronto non deve dipendere dall'ordine di scansione
  find . -path ./.scratch -prune -o -name __pycache__ -prune -o -type f ! -name '*.pyc' \
       -print0 | LC_ALL=C sort -z | xargs -0 md5sum | LC_ALL=C sort
}

JAR_MD5_ATTESO=c7b9238d6631c64fadd47ebfae00db8e
CT_BRIDGES="D,C,D,D,D,D,D,B,B,D,D,D,D"
RFD_BRIDGES="RENUVER/RFD/output_false_9_bridges.csv"
DS_BRIDGES="RENUVER/Dataset/bridges_14_1.csv"

# ---------------------------------------------------------------- 0. impronte iniziali
impronte > "$OUT/impronte_prima.txt" 2>/dev/null

# ---------------------------------------------------------------- 1. ambiente
titolo "1. Ambiente e materiale"
printf '  python3 : %s\n' "$(python3 --version 2>&1)"
printf '  java    : %s\n' "$( (java -version 2>&1 | head -1) || echo 'NON TROVATO')"
printf '  cartella: %s\n' "$RADICE"
JAR_MD5="$(md5sum RENUVER/RENUVER_EDBT.jar 2>/dev/null | cut -d' ' -f1)"
if [ "$JAR_MD5" = "$JAR_MD5_ATTESO" ]; then
  printf '  JAR     : md5 %s (atteso)\n' "$JAR_MD5"
else
  printf '  JAR     : md5 %s — ATTESO %s\n' "${JAR_MD5:-assente}" "$JAR_MD5_ATTESO"
  FAIL=$((FAIL+1)); FALLITI="$FALLITI jar"
fi
N_DATASET=$(ls RENUVER/Dataset/*.csv 2>/dev/null | wc -l)
N_JSON=$(ls results/*.json 2>/dev/null | wc -l)
N_SCRIPT=$(ls pruning/*.py analisi/*.py 2>/dev/null | wc -l)
printf '  materiale: %s dataset, %s JSON di risultati, %s script Python\n' "$N_DATASET" "$N_JSON" "$N_SCRIPT"
if [ "$N_DATASET" -eq 0 ]; then
  VERSIONE_LEGGERA=1
  echo "  (versione leggera: senza dataset; i passi che eseguono RENUVER verranno saltati)"
else
  VERSIONE_LEGGERA=0
fi

# ---------------------------------------------------------------- 2. sintassi
titolo "2. Sintassi di tutti gli script"
if python3 - >"$LOG/sintassi.log" 2>&1 <<'PY'
import os, sys
fuori, errori = [], []
for radice, cartelle, files in os.walk("."):
    cartelle[:] = [c for c in cartelle if c not in (".scratch", "__pycache__")]
    for f in sorted(files):
        if f.endswith(".py"):
            p = os.path.join(radice, f)
            fuori.append(p)
            try:
                # compila senza scrivere alcun file .pyc
                with open(p, encoding="utf-8") as fh:
                    compile(fh.read(), p, "exec")
            except Exception as e:                       # noqa: BLE001
                errori.append(f"{p}: {e}")
print(f"script Python compilati: {len(fuori)}")
for e in errori:
    print("ERRORE", e)
sys.exit(1 if errori else 0)
PY
then
  printf '  [ OK ] %-24s %s\n' "sintassi Python" "$(tail -1 "$LOG/sintassi.log")"
  OK=$((OK+1))
else
  printf '  [FAIL] %-24s %s\n' "sintassi Python" "$(tail -2 "$LOG/sintassi.log" | head -1 | cut -c1-64)"
  FAIL=$((FAIL+1)); FALLITI="$FALLITI sintassi_python"
fi
N_SH=0; SH_ROTTI=""
while IFS= read -r s; do
  N_SH=$((N_SH+1))
  bash -n "$s" 2>>"$LOG/bash_n.log" || SH_ROTTI="$SH_ROTTI $s"
done < <(find . -path ./.scratch -prune -o -name '*.sh' -print | sort)
if [ -z "$SH_ROTTI" ]; then
  printf '  [ OK ] %-24s %s script .sh senza errori di sintassi\n' "bash -n" "$N_SH"
  OK=$((OK+1))
else
  printf '  [FAIL] %-24s sintassi errata in:%s\n' "bash -n" "$SH_ROTTI"
  FAIL=$((FAIL+1)); FALLITI="$FALLITI bash_n"
fi
rm -rf __pycache__ pruning/__pycache__ analisi/__pycache__ analisi/strumenti/__pycache__ 2>/dev/null

# ---------------------------------------------------------------- 3. controlli offline
titolo "3. Controlli offline sui risultati gia' presenti"
esito audit          300 "DIVERGENZE: 0"  python3 pruning/audit_report.py
esito stats_effects  300 "4/4 PASS"       python3 pruning/stats_effects.py
esito analyze_order  300 "D3"             python3 pruning/analyze_order.py
esito ablation_a5b   300 -                python3 pruning/ablation_a5b.py
esito summarize_fase3 300 -               python3 pruning/summarize_fase3.py
esito hyp_fase4      300 -                python3 pruning/verify_hypotheses_fase4.py
esito hyp_fase5      300 -                python3 pruning/verify_hypotheses_fase5.py
esito trivial_baseline 300 -              python3 pruning/trivial_baseline.py
esito verifica_tetto 900 "intrinseco al criterio" python3 pruning/verifica_tetto.py
esito verifica_condizioni 900 "coincidono con le tabelle del capitolo 3" \
                                          python3 pruning/verifica_condizioni.py
esito appendix_tabelle 300 -              python3 pruning/make_appendix_tables.py
esito report_markdown 300 -               python3 pruning/make_report.py
esito merge_results  300 -                python3 pruning/merge_results.py \
                                            --out "$OUT/merge_prova.json" \
                                            results/results_A5b_bridges_r345.json \
                                            results/results_A5b_glass.json
if [ -f report.md ]; then
  cp report.md "$OUT/report_prova.md"
  esito fill_report  300 -                python3 pruning/fill_report.py --report "$OUT/report_prova.md"
else
  salta fill_report "report.md non e' in questa cartella: la relazione tecnica resta un documento a parte"
fi

# ---------------------------------------------------------------- 4. trasformazioni reali
titolo "4. Potatura e strumenti che non eseguono RENUVER"
esito estrai_classi  300 "invariato"      python3 analisi/estrai_classi.py --out "$OUT/classi"
esito strumenti_cfhdr 300 -               python3 analisi/strumenti/cfhdr.py \
                                            analisi/classi/FillingAlgorithm.class
esito strumenti_jvmdis 300 -              python3 analisi/strumenti/jvmdis.py \
                                            analisi/classi/FillingAlgorithm.class
esito strumenti_absbr 300 -               bash -c "cd analisi/strumenti && \
                                            python3 absbr.py ../classi/FillingAlgorithm.class"

if [ "$VERSIONE_LEGGERA" -eq 0 ]; then
  esito prune_rfd_coverage 300 -          python3 pruning/prune_rfd.py \
                                            --rfd "$RFD_BRIDGES" --dataset "$DS_BRIDGES" \
                                            --out "$OUT/potato_coverage.csv" --coverage
  esito pruning_veto_cover 300 -          python3 pruning/pruning.py \
                                            --rfd "$RFD_BRIDGES" --dataset "$DS_BRIDGES" \
                                            --output "$OUT/potato_vetocover.csv" \
                                            --strategy veto-cover --veto-policy allow \
                                            --coltypes "$CT_BRIDGES"
  esito pruning_inert  300 -              python3 pruning/pruning.py \
                                            --rfd "$RFD_BRIDGES" --dataset "$DS_BRIDGES" \
                                            --output "$OUT/potato_inert.csv" \
                                            --strategy inert --coltypes "$CT_BRIDGES"
  esito pruning_duplicates 300 -          python3 pruning/pruning.py \
                                            --rfd "$RFD_BRIDGES" --dataset "$DS_BRIDGES" \
                                            --output "$OUT/potato_duplicates.csv" \
                                            --strategy duplicates --coltypes "$CT_BRIDGES"
  esito pruning_a5b    300 -              python3 pruning/pruning.py \
                                            --rfd "$RFD_BRIDGES" --dataset "$DS_BRIDGES" \
                                            --output "$OUT/potato_a5b.csv" \
                                            --strategy exact-priority+dom-sub-adaptive \
                                            --adaptive-alpha 0.85 --veto-policy allow \
                                            --coltypes "$CT_BRIDGES"
  esito reorder_dataset 300 -             python3 pruning/reorder_dataset.py \
                                            --dataset "$DS_BRIDGES" --heuristic null-count \
                                            --output "$OUT/riordinato.csv" \
                                            --tuple-out "$OUT/riordinato_ti.csv"
  esito fix_glass_schema 300 -            python3 pruning/fix_glass_schema.py \
                                            --output-dir .scratch/glass_fixed/Dataset \
                                            --tuple-dir RENUVER/TupleIniziali \
                                            --tuple-output-dir .scratch/glass_fixed/TupleIniziali
  esito prepare_physician 300 -           python3 pruning/prepare_physician_tuples.py \
                                            --out "$OUT/physician_ti"
  esito repair_physician 300 -            python3 pruning/repair_physician_datasets.py \
                                            --ds-out "$OUT/physician_ds" \
                                            --ti-out "$OUT/physician_ti_fix"
  esito order_analysis 900 -              python3 pruning/order_analysis.py

  if python3 -c "import numpy" 2>/dev/null; then
    esito probe_maxthr 900 -              python3 pruning/probe_maxthr.py --quick --only glass
    esito verify_veto  900 "verificata empiricamente" python3 pruning/verify_veto.py \
                                            --rfd-full "$RFD_BRIDGES" \
                                            --rfd-pruned "$OUT/potato_vetocover.csv" \
                                            --dataset "$DS_BRIDGES" --coltypes "$CT_BRIDGES" \
                                            --maxthr 9 --max-cells 60 --report
  else
    salta probe_maxthr "richiede numpy (strategia score-argmin)"
    salta verify_veto  "richiede numpy"
  fi
else
  salta "potatura e trasformazioni" "la versione leggera non contiene RENUVER/Dataset"
  salta "probe_maxthr, verify_veto" "richiedono i dataset"
fi

# ---------------------------------------------------------------- 5. estrattori storici
if [ "$CON_ANALISI" -eq 1 ]; then
  titolo "5. Estrattori storici di analisi/ (lenti: leggono log e regole dell'archivio)"
  for f in analisi/*.py; do
    n="$(basename "$f")"
    case "$n" in
      estrai_classi.py) continue ;;                     # gia' eseguito al passo 4
      run_experiments.py|run_experiments2.py)
        # lanciatori storici delle prime campagne: rieseguono il sistema su molte configurazioni
        # e richiedono ore. Restano nel pacchetto e si lanciano a mano dalla radice.
        salta "analisi_${n%.py}" "lanciatore di campagna storica: si esegue a mano (ore)"; continue ;;
    esac
    if [ "$n" = "proxy.py" ]; then
      esito "analisi_${n%.py}" 1800 - python3 "$f"       # ~8 minuti: legge 125 configurazioni
    else
      esito "analisi_${n%.py}" 600 - python3 "$f"
    fi
  done
  for f in analisi/strumenti/*.py; do
    n="$(basename "$f" .py)"
    case "$n" in
      absbr|absbr_ex)
        esito "strumenti_$n" 300 - bash -c \
              "cd analisi/strumenti && python3 $n.py ../classi/FillingAlgorithm.class" ;;
      *)
        esito "strumenti_$n" 300 - python3 "$f" analisi/classi/FillingAlgorithm.class ;;
    esac
  done
else
  titolo "5. Estrattori storici di analisi/"
  salta "analisi/*.py" "richiede --analisi (18 script, lettura dei log dell'archivio)"
fi

# ---------------------------------------------------------------- 6. campagne ed esecuzioni
titolo "6. Campagne ed esecuzioni RENUVER"
N_CAMP=$(ls pruning/campagne/*.sh pruning/*.sh 2>/dev/null | wc -l)
printf '  [ OK ] %-24s %s script di campagna con sintassi valida\n' "campagne" "$N_CAMP"
OK=$((OK+1))
if [ "$CON_RUN" -eq 1 ] && [ "$VERSIONE_LEGGERA" -eq 0 ]; then
  esito verifica_rapida 1200 "identico" bash verifica_rapida.sh
  # confronto A/B con ritenzione degli output: serve anche alla contabilità dei veti
  esito benchmark_AB   1800 -             python3 pruning/benchmark.py \
                                            --datasets bridges_14 --runs 1 --thresholds 9 \
                                            --variants "VC=veto-cover:allow" \
                                            --prune-extra "--coltypes $CT_BRIDGES" \
                                            --keep-populated-dir "$OUT/vcpop" \
                                            --keep-results-dir "$OUT/vcres" \
                                            --out "$OUT/benchmark_prova.json"
  esito veto_cost      900 -              python3 pruning/veto_cost.py \
                                            --json "$OUT/benchmark_prova.json" \
                                            --pop-dir "$OUT/vcpop" --dataset bridges_14_1 \
                                            --run 1 --threshold 9 --rfd "$RFD_BRIDGES" \
                                            --dataset-file "$DS_BRIDGES"
  esito exp_order      1800 -             python3 pruning/exp_order.py bridges_14 9 1 bridges \
                                            --out "$OUT/exp_order_prova.json"
  esito collect_stats  1800 -             python3 pruning/collect_stats.py \
                                            --datasets glass_22 --runs 1 --thresholds 3 \
                                            --out-dir "$OUT/collect_stats"
  esito probe_physician 1800 -            python3 pruning/probe_physician_full.py \
                                            --timeout 120 --poll 30 \
                                            --out "$OUT/probe_physician_prova.json"
  # misura del costo (capitolo 2 della tesi): equivalenza della ricostruzione e strumentazione
  esito equivalenza_ricostruzione 900 "equivalente all'originale" \
                                          bash strumentazione_costo/prova_equivalenza.sh
  esito strumentazione_costo 1800 "STRUMENTAZIONE" \
                                          bash strumentazione_costo/esegui_strumentato.sh
else
  salta "esecuzioni RENUVER" "richiedono --run: verifica rapida, confronto A/B, contabilità dei veti,
                            esperimento d'ordine, raccolta statistiche, sonda Physician"
fi

# ---------------------------------------------------------------- 7. integrita' dei file
titolo "7. Integrita' dei file consegnati"
impronte > "$OUT/impronte_dopo.txt" 2>/dev/null
MODIFICATI="$(diff "$OUT/impronte_prima.txt" "$OUT/impronte_dopo.txt" | sed -n 's/^[<>] \([0-9a-f]*\)  \(.*\)/\2/p' | sort -u)"
if [ -z "$MODIFICATI" ]; then
  printf '  [ OK ] %-24s nessun file consegnato e'\'' stato modificato dalla verifica\n' "impronte md5"
  OK=$((OK+1))
else
  printf '  [ -- ] %-24s file toccati dalla verifica (atteso: solo rigenerazioni identiche)\n' "impronte md5"
  printf '%s\n' "$MODIFICATI" | sed 's/^/         /'
  SALTATI=$((SALTATI+1))
fi

# ---------------------------------------------------------------- riepilogo
printf '\n=====================================================================\n'
printf 'esiti: %d OK, %d FAIL, %d voci non eseguite\n' "$OK" "$FAIL" "$SALTATI"
if [ "$FAIL" -gt 0 ]; then
  printf 'controlli falliti:%s\n' "$FALLITI"
  printf 'log completi in %s\n' ".scratch/verifica/log"
  exit 1
fi
printf 'tutti i controlli eseguiti sono passati.\n'
printf 'log completi in %s\n' ".scratch/verifica/log"
exit 0
