# Materiale della tesi — Semantic pruning degli insiemi di RFD per RENUVER

Cartella di accompagnamento della tesi `tesi_completa.pdf` (dieci capitoli e due appendici).
Contiene il sistema studiato, il potatore sviluppato, i risultati delle campagne e le procedure con
cui verificare quanto la tesi afferma.

---

## 1. Che cosa contiene la cartella

| voce | contenuto |
|---|---|
| `tesi_completa.pdf` | la tesi completa: capitoli 1–10 e appendici A–B |
| `RENUVER/` | il sistema studiato, **non modificato**: eseguibile `RENUVER_EDBT.jar`, dataset, file di regole (`RFD/`), ground truth (`TupleIniziali/`), log e output originali |
| `pruning/` | il potatore: 20 strategie, politiche sui veti, ambiente di valutazione A/B, campagne, verifiche |
| `results/` | i risultati delle campagne in JSON, una voce per esecuzione (65 file, 2 808 esecuzioni) |
| `analisi/` | la ricostruzione del sistema dal bytecode: disassemblaggio commentato, modello dei dati, classi estratte e strumenti di ispezione |
| `strumentazione_costo/` | la misura del costo computazionale del capitolo 2: build ricostruita e strumentata, prova di equivalenza, log della misura |
| `GUIDA_COMPLETA.md` | manuale d'uso: opzioni degli strumenti, campagne, misura del costo, problemi comuni; in appendice ogni comando spiegato argomento per argomento, con esempi |
| `verifica_rapida.sh`, `verifica_completa.sh` | i due script di verifica (vedi §3 e §6) |

---

## 2. Requisiti

Servono **Java 8 o superiore** (l'eseguibile è compilato per la versione 52 del formato `class`) e
**Python 3.10 o superiore**. Gli script usano la sola libreria standard, con una eccezione:
`numpy` serve a due strumenti facoltativi (la strategia `score-argmin` e `pruning/verify_veto.py`);
senza `numpy` tutto il resto funziona.

```bash
java -version            # atteso: openjdk 8 o superiore
python3 --version        # atteso: Python 3.10 o superiore
python3 -c "import numpy" && echo "numpy presente" || echo "numpy assente (facoltativo)"
```

Se mancano:

```bash
sudo apt install default-jre python3        # Debian/Ubuntu
python3 -m pip install numpy                # solo se serve la verifica del veto o score-argmin
```

Non serve alcuna connessione di rete e non viene scaricato nulla. Le esecuzioni del sistema
richiedono circa 1 GB libero e **non possono essere lanciate in parallelo**: la cartella di lavoro
del sistema è condivisa e due esecuzioni simultanee si sovrascriverebbero gli output senza
segnalare errori. Tutti i comandi si eseguono da questa cartella.

---

## 3. Test della potatura garantita (il veto)

La potatura garantita rimuove solo regole il cui veto è implicato da una regola che sopravvive
(condizione `[V2]` della tesi): l'output del sistema deve restare **identico**.

```bash
bash verifica_rapida.sh                    # ~1,5 minuti: potatura, due esecuzioni del sistema, confronto
```

Esito atteso, sul file di regole di Bridges a soglia 9 (8 961 regole):

```
      configurazione                   RFD   rid. %  imputate  corrette       esito
      bridges_14 @9 run1              8961     17.1        10         9    identico
```

Le due tabelle di dati del capitolo 3 (regole inerti, regole coperte, regole che possono fare veto)
si ricalcolano tutte, senza eseguire il sistema, in una quindicina di secondi:

```bash
python3 pruning/verifica_condizioni.py     # 8 configurazioni, 70 388 regole
```

Esito atteso: `tutte e 8 le configurazioni coincidono con le tabelle del capitolo 3`. Il tetto della
potatura garantita (capitolo 4) si ricalcola con `python3 pruning/verifica_tetto.py`: la riduzione
resta piatta allargando la ricerca dei copritori (8 939 → 8 940 rimozioni su otto casi, cioè +1).

Per il controllo numerico complessivo, che copre anche i capitoli dei risultati:

```bash
python3 pruning/audit_report.py            # 67 asserzioni numeriche
python3 pruning/stats_effects.py           # effetti, intervalli di confidenza, correzione di Holm
python3 pruning/analyze_order.py           # esperimento sull'ordine dei cluster
```

Esiti attesi: `controlli: 67   OK: 67   DIVERGENZE: 0`, `4/4 PASS` e i tre confronti dell'ordine.

---

## 4. Test della potatura aggressiva (A5b)

A5b è la combinazione `exact-priority` + `dom-sub-adaptive` (α = 0,85): rimuove molte più regole
della potatura garantita, e su Bridges migliora l'accuratezza.

```bash
python3 pruning/benchmark.py --datasets bridges_14 --runs 1 --thresholds 9 \
    --variants "A5b=exact-priority+dom-sub-adaptive:allow" \
    --prune-extra "--adaptive-alpha 0.85" \
    --out .scratch/prova_A5b.json
```

L'ambiente di valutazione copia l'archivio in `.scratch/bench_lab`, esegue il sistema nella
configurazione di partenza e in quella potata e stampa il confronto appaiato. Esito misurato su
`bridges_14_1`, soglia 9 (circa un minuto; i tempi dipendono dalla macchina, gli altri valori no):

| variante | RFD | riduzione | copertura | precisione | accuratezza | preprocessing |
|---|---|---|---|---|---|---|
| A (partenza) | 8 961 | — | 0,714 | 0,900 | 0,643 | 28,1 s |
| A5b | 1 366 | **84,8 %** | 0,714 | 1,000 | **0,714** | 4,9 s |

Su più configurazioni, per l'ablazione dei due componenti e per i termini di paragone:

```bash
python3 pruning/ablation_a5b.py            # ablazione, griglia completa, confronto multi-dataset
python3 pruning/trivial_baseline.py        # accuratezza di un imputatore banale sulle stesse celle
python3 pruning/make_appendix_tables.py    # tabelle complete dell'appendice B
```

---

## 5. Dove trovare i risultati

- `results/*.json` — una voce per esecuzione: `dataset`, `run`, `threshold`, `variant` (`A` è la
  configurazione di partenza), `rfd_in`, `rfd_out`, `rfd_reduction`, `imputed`, `correct`, `wrong`,
  `coverage`, `accuracy`, `n_exact`, `pre_ms`, `exec_ms`, `rc`. I confronti si fanno in forma
  appaiata.
- `results/stats_effects.json` — dimensioni dell'effetto, intervalli di confidenza, correzione di Holm.
- `results/analisi/` — i dati delle prove fuori griglia (ordinamento, ablazione, riduzione classica,
  famiglia Physician) e le tabelle complete dell'appendice B.
- `.scratch/` — area di lavoro: i log delle verifiche in `.scratch/verifica/log/` e il risultato del
  test A/B di `verifica_rapida.sh` in `.scratch/verifica_rapida/verifica_rapida.json`.
- `GUIDA_COMPLETA.md` — il manuale, con in appendice la spiegazione di ogni comando.

---

## 6. Avvertenze

- **Non lanciare due esecuzioni del sistema in parallelo** (vedi §2).
- Gli **script di campagna** (`pruning/campagne/*.sh`) scrivono in `results/*.json` con gli stessi
  nomi dei file consegnati: prima di eseguirne uno conviene copiare la cartella
  (`cp -r results results_originali`) o cambiare il nome dell'output con `--out`.
- Gli output delle prove vanno in `.scratch/`: i due conteggi globali di `audit_report.py`
  («record totali», «esecuzioni non-baseline») si riferiscono ai file consegnati, e un JSON in più
  nella cartella li fa divergere (lo script elenca comunque i file toccati di recente).
- Per eseguire e controllare **tutta** la strumentazione con un solo comando, compresa la misura
  del costo del capitolo 2:

```bash
bash verifica_completa.sh            # ~5 minuti, nessuna esecuzione del sistema
bash verifica_completa.sh --run      # ~20 minuti, aggiunge le esecuzioni del sistema
bash verifica_completa.sh --tutto    # ~36 minuti, aggiunge anche gli estrattori storici
```
