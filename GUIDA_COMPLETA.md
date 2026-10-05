# Guida completa

Manuale d'uso della cartella che accompagna la tesi `tesi_completa.pdf` (dieci capitoli e due
appendici). Per i due test essenziali — potatura garantita e A5b — basta il `README.md`; qui ci sono
le opzioni di tutti gli strumenti, le campagne disponibili, la misura del costo del capitolo 2, la
verifica completa della strumentazione e i problemi comuni. Tutti i comandi si eseguono da questa
cartella.

> In fondo c'è l'**appendice**: ogni comando spiegato argomento per argomento, con un esempio
> completo e l'esito atteso.

---

## 1. Requisiti

| requisito | versione | note |
|---|---|---|
| Java (JRE o JDK) | 8 o superiore | l'eseguibile è compilato per la versione 52 del formato `class` |
| Python | 3.10 o superiore | gli script usano la sola libreria standard |
| `numpy` | facoltativo | serve alla strategia `score-argmin` e a `pruning/verify_veto.py`; senza `numpy` quei due comandi si fermano con un messaggio, tutto il resto funziona |

```bash
java -version
python3 --version
python3 -c "import numpy" && echo "numpy presente" || echo "numpy assente (facoltativo)"
```

Non serve alcuna connessione di rete. **Le esecuzioni del sistema non possono essere parallele**: la
cartella di lavoro è condivisa e due esecuzioni simultanee sovrascrivono gli output senza segnalare
errori. Gli script di campagna le eseguono quindi in sequenza.

---

## 2. I due test essenziali

**Potatura garantita (il veto).** Rimuove solo regole il cui veto è implicato da una regola che
sopravvive: l'output del sistema deve restare identico.

```bash
bash verifica_rapida.sh                    # ~1,5 min: potatura, due esecuzioni, confronto
python3 pruning/verifica_condizioni.py     # ~15 s: le due tabelle del capitolo 3, 8 configurazioni
```

Esiti attesi: `bridges_14 @9 run1  8961  17.1  10  9  identico` e
`tutte e 8 le configurazioni coincidono con le tabelle della tesi`.

**Potatura aggressiva (A5b).** `exact-priority` + `dom-sub-adaptive` con α = 0,85.

```bash
python3 pruning/benchmark.py --datasets bridges_14 --runs 1 --thresholds 9 \
    --variants "A5b=exact-priority+dom-sub-adaptive:allow" \
    --prune-extra "--adaptive-alpha 0.85" --out .scratch/prova_A5b.json
```

Esito misurato su `bridges_14_1` a soglia 9: 8 961 → **1 366 regole** (−84,8 %), copertura
invariata (0,714), accuratezza 0,643 → **0,714**, preprocessing 28,1 s → 4,9 s.

---

## 3. Il potatore: opzioni e uso

Il potatore è indipendente dal sistema: riscrive il file delle regole, lasciando intatti dataset ed
eseguibile.

```bash
python3 pruning/pruning.py \
    --rfd RENUVER/RFD/output_false_9_bridges.csv \
    --dataset "RENUVER/Dataset/bridges_14_1.csv" \
    --output .scratch/rfd_potato.csv \
    --strategy veto-cover --veto-policy protect --report
```

| opzione | significato |
|---|---|
| `--strategy` | una o più strategie separate da virgola, applicate in sequenza (elenco completo con `--help`: 20 strategie) |
| `--veto-policy` | `protect` ripristina ogni regola che può esercitare un veto; `allow` non tutela nulla; `budget:F` consente di rimuovere una frazione `F` delle regole portatrici di veto |
| `--dataset` | serve a calcolare le colonne che presentano valori mancanti (condizioni `[V1]`–`[V3]`); per Glass serve lo schema corretto, che `fix_glass_schema.py` prepara in `.scratch/glass_fixed/` |
| `--max-extra` | ampiezza massima della differenza fra i LHS nella ricerca dei copritori `[V2]` (default 3) |
| `--report` | stampa il dettaglio: regole in ingresso, rimosse per ciascuna strategia, regole rimaste |

Il file scritto ha lo stesso formato dell'input ed è pronto per il sistema. Per una potatura
minimale, senza le strategie veto-consapevoli, c'è `pruning/prune_rfd.py` (ridondanza classica:
copertura, dominanza, duplicati).

---

## 4. Confronto A/B e analisi sui dati raccolti

`pruning/benchmark.py` è l'ambiente di valutazione: copia l'archivio in `.scratch/bench_lab`, esegue
il sistema nella configurazione di partenza, pota il file delle regole una volta per variante,
riesegue il sistema su ogni file potato e calcola le metriche in forma **appaiata** (stessa
configurazione, stessa soglia, stessa ripetizione).

```bash
python3 pruning/benchmark.py \
    --datasets bridges_14 --runs 1 --thresholds 9 \
    --variants "VC=veto-cover:protect,A5b=exact-priority+dom-sub-adaptive:allow" \
    --prune-extra "--adaptive-alpha 0.85" \
    --out .scratch/prova_AB.json
```

Tempi indicativi su una macchina a otto core, Bridges a soglia 9: circa 40 secondi per esecuzione,
perché il sistema impiega quasi tutto il tempo nel proprio preprocessing (controllo di chiave,
quadratico nel numero di righe). Una variante richiede poco più di un minuto.

Sui dati già raccolti, senza eseguire il sistema:

```bash
python3 pruning/stats_effects.py        # dimensioni dell'effetto, IC bootstrap, correzione di Holm
python3 pruning/ablation_a5b.py         # contributo dei due componenti di A5b, griglia completa
python3 pruning/trivial_baseline.py     # termine di paragone banale (moda di colonna)
python3 pruning/make_appendix_tables.py # tabelle complete dell'appendice B
python3 pruning/analyze_order.py        # esperimento sull'ordine dei cluster
python3 pruning/audit_report.py         # 67 asserzioni numeriche
python3 pruning/verifica_tetto.py       # il tetto di [V2] non dipende da max_extra
```

**Quale strumento ricalcola i numeri dei capitoli dei risultati.**

| che cosa si vuole controllare | comando |
|---|---|
| i numeri dei capitoli 3–4 (condizioni, tetto) | `verifica_condizioni.py`, `verifica_tetto.py` |
| l'equivalenza della potatura garantita e i risultati delle campagne | `audit_report.py` (67 asserzioni) |
| i valori di p, gli intervalli, la correzione di Holm | `stats_effects.py` (4 controlli di regressione) |
| l'ablazione dei componenti di A5b | `ablation_a5b.py` |
| l'esperimento sull'ordine dei cluster | `analyze_order.py` |
| il termine di paragone banale | `trivial_baseline.py` |
| le tabelle complete per configurazione | `make_appendix_tables.py` |
| la verifica empirica della condizione `[V2]` | `verify_veto.py` oppure `verify_veto_sweep.sh` |

`audit_report.py` raggruppa i controlli per sezione della relazione tecnica estesa (§1.4, §5.6, …):
quella relazione resta un documento a parte e non è inclusa in questa cartella.

---

## 5. Campagne disponibili

Stanno in `pruning/campagne/` (e in `pruning/`); orchestrano più configurazioni in sequenza.

| script | che cosa misura | durata indicativa |
|---|---|---|
| `pruning/campagne/campaign_A5b_full.sh` | potatura aggressiva su Bridges, griglia completa | alcune ore |
| `pruning/campagne/gentle_glass_restaurant.sh` | taratura conservativa su Glass e Restaurant | un'ora circa |
| `pruning/campagne/consolida_a99.sh` | consolidamento della taratura conservativa (97 configurazioni) | un'ora circa |
| `pruning/campagne/vetocost.sh` | contabilità del costo per cella delle rimozioni | pochi minuti |
| `pruning/verify_veto_sweep.sh` | verifica empirica della copertura del veto | pochi minuti |

**Attenzione**: le campagne scrivono in `results/*.json` con gli **stessi nomi dei file consegnati**.
Prima di eseguirne una conviene copiare la cartella dei risultati:

```bash
cp -r results results_originali
```

oppure cambiare il nome dell'output con `--out` nei singoli comandi di `benchmark.py`.

---

## 6. Misura del costo computazionale (capitolo 2 della tesi)

Il sistema è distribuito senza sorgenti: per sapere dove vada il tempo è stato ricostruito dai
sorgenti decompilati, verificato equivalente all'originale e instrumentato. Il materiale è in
`strumentazione_costo/` (dettagli in `strumentazione_costo/LEGGIMI.md`).

```bash
bash strumentazione_costo/prova_equivalenza.sh    # ~2 min: la ricostruzione è equivalente?
bash strumentazione_costo/esegui_strumentato.sh   # ~5 min: dove va il tempo
```

La prova di equivalenza confronta i file prodotti dall'eseguibile originale e da quello
ricostruito: `Populated/` e `Results/` devono essere **byte-identici** (il file `Logs/` registra
tempi e memoria, quindi differisce). La misura strumentata riproduce la tabella del capitolo 2: la
verifica dei veti assorbe oltre il 99 % del tempo su `bridges_70_1` a soglia 15 e l'85 % su
`bridges_14_1` a soglia 9. I conteggi (531, 151, 293, 8 e le 354 809 scansioni) sono proprietà
strutturali e si riproducono identici; i millisecondi dipendono dalla macchina.

---

## 7. Verifica completa della strumentazione

```bash
bash verifica_completa.sh            # ~5 min, nessuna esecuzione del sistema
bash verifica_completa.sh --analisi  # aggiunge i 19 estrattori storici di analisi/
bash verifica_completa.sh --run      # aggiunge ~20 min di esecuzioni del sistema
bash verifica_completa.sh --tutto    # tutto, ~36 min
```

Controlla, in sette passi: ambiente e impronta dell'eseguibile; sintassi di tutti gli script Python
e delle campagne; i quattordici strumenti offline con l'esito atteso; la potatura applicata davvero
con quattro strategie e le altre trasformazioni; gli estrattori storici (con `--analisi`); le
campagne e le esecuzioni del sistema (con `--run`); infine confronta le impronte MD5 di tutti i file
consegnati prima e dopo, per mostrare che la verifica non altera nulla. Ogni voce stampa `OK`,
`FAIL` o `--` e lascia il log in `.scratch/verifica/log/`.

---

## 8. Come si leggono i file di risultato

Ogni file di `results/*.json` è una lista di esecuzioni; una voce contiene:

| campo | significato |
|---|---|
| `dataset`, `run`, `threshold` | la configurazione (l'unità di analisi) |
| `variant` | `A` è la configurazione di partenza; le altre sono le varianti potate |
| `rfd_in`, `rfd_out`, `rfd_reduction` | regole in ingresso, dopo la potatura, riduzione percentuale |
| `missing_total`, `imputed`, `not_imputed` | celle valutate, imputate, non imputate (copertura) |
| `correct`, `wrong`, `precision`, `accuracy` | imputazioni corrette ed errate e metriche derivate |
| `n_exact`, `n_rfd_used` | imputazioni per via esatta, regole effettivamente impiegate |
| `pre_ms`, `exec_ms`, `total_ms` | tempi: preprocessing del sistema, esecuzione, totale |
| `rc`, `err` | codice di uscita e messaggio di errore, se l'esecuzione non è riuscita |

Le voci con `rc` diverso da zero non entrano nei confronti.

**Dove scrivere le prove.** Gli output delle prove che si eseguono per conto proprio vanno in
`.scratch/` (area di lavoro), non in `results/`: i due conteggi globali di `audit_report.py`
(«record totali», «esecuzioni non-baseline») si riferiscono ai file consegnati, e un JSON in più
nella cartella li fa divergere. Se succede, `audit_report.py` elenca i file toccati di recente.

---

## 9. Problemi comuni

| sintomo | causa e rimedio |
|---|---|
| `java: command not found` | installare un JRE (`sudo apt install default-jre`) |
| `[errore] ... file RFD non trovato` | i comandi vanno eseguiti dalla radice della cartella, non da dentro `pruning/` |
| risultati incoerenti o output sovrascritti | due esecuzioni in parallelo: ripetere in sequenza |
| `IndexOutOfBoundsException` su una configurazione Physician | righe malformate nei dataset d'archivio: documentato nella relazione, capitolo sulle anomalie |
| memoria esaurita su dataset grandi | il sistema carica l'intero dataset: usare le configurazioni ridotte, come fanno le campagne |
| `[errore] la strategia score-argmin richiede numpy` | installare `numpy` o usare una delle altre 19 strategie |
| `[errore] verify_veto.py usa numpy` | installare `numpy`, oppure saltare la verifica del veto: i 67 controlli di `audit_report.py` non ne dipendono |
| `[salto] glass ... manca .scratch/glass_fixed/Dataset/...` | preparare lo schema corretto: `python3 pruning/fix_glass_schema.py --output-dir .scratch/glass_fixed/Dataset --tuple-dir RENUVER/TupleIniziali --tuple-output-dir .scratch/glass_fixed/TupleIniziali` |

---

## 10. Andare oltre i due test

**Percorso consigliato**, in ordine di costo:

| livello | comandi | tempo |
|---|---|---|
| 1. coerenza dei numeri | `audit_report.py`, `stats_effects.py`, `verifica_condizioni.py`, `verifica_tetto.py` | 1 minuto |
| 2. comportamento del sistema | `verifica_rapida.sh`, poi `pruning.py` con `inert`, `veto-cover`, `duplicates` | 10 minuti |
| 3. riproduzione di un risultato | una campagna breve (`vetocost.sh` o una singola famiglia) e confronto con i JSON consegnati | un'ora |
| 4. verifica indipendente delle condizioni | `pruning/verify_veto.py` (richiede `numpy`): sulla configurazione di Bridges a soglia 9 esamina 68 411 terne e non trova discrepanze | facoltativo |
| 5. analisi del sistema | `analisi/estrai_classi.py` e gli strumenti di `analisi/strumenti/` sul bytecode | facoltativo |

**Estendere il lavoro.**

- *Aggiungere una strategia*: in `pruning/pruning.py` le strategie sono funzioni che restituiscono
  una maschera booleana sulle regole (`mask_*`); servono la funzione, la registrazione in
  `STRATEGIES` e un ramo nel dispatch.
- *Cambiare la griglia sperimentale*: `benchmark.py` accetta `--datasets`, `--runs`, `--thresholds`,
  `--variants`, `--prune-extra`.
- *Ricontrollare i numeri* dopo qualunque modifica: `python3 pruning/audit_report.py` segnala le
  divergenze fra relazione e dati.

---

# Appendice — Riferimento dei comandi

Gli stessi comandi di questa guida, spiegati uno per uno: che cosa fa il comando, che cosa
significano i suoi argomenti, un esempio completo e l'esito atteso.

## A.1. `bash verifica_rapida.sh` — il test end-to-end della potatura garantita

**Che cosa fa.** Applica la potatura garantita (`veto-cover`) al file di regole di Bridges a
soglia 9, esegue il sistema **senza** e **con** il file potato in due cartelle isolate, confronta i
due output e stampa la riduzione ottenuta. Prima esegue i due controlli offline sui numeri.

**Parametri.** Nessuno.

**Esempio.**
```bash
bash verifica_rapida.sh
```

**Esito atteso** (circa un minuto e mezzo):
```
      configurazione                   RFD   rid. %  imputate  corrette       esito
      bridges_14 @9 run1              8961     17.1        10         9    identico
```
I risultati finiscono in `.scratch/verifica_rapida/`; nessun file consegnato viene toccato.

---

## A.2. Le verifiche delle affermazioni dei capitoli 3 e 4

### A.2.1 `python3 pruning/verifica_condizioni.py` — le due tabelle di dati del capitolo 3

**Che cosa fa.** Ricalcola, dai file di regole dell'archivio, tutte e otto le configurazioni delle
due tabelle del capitolo 3: quante regole sono **inerti** `[V3]`, quante sono **coperte** `[V2]`,
quante **possono fare veto** `[V1]`, e confronta i valori con quelli stampati nella tesi. Per
Glass prepara da sé i dataset con lo schema corretto in `.scratch/glass_fixed/`.

**Parametri.**
- `--solo FAMIGLIA` — limita il calcolo a una famiglia (`bridges`, `glass`, `restaurant`). Senza
  questo argomento calcola tutte e otto le configurazioni.

**Esempio.**
```bash
python3 pruning/verifica_condizioni.py
python3 pruning/verifica_condizioni.py --solo bridges
```

**Esito atteso** (una quindicina di secondi): `tutte e 8 le configurazioni coincidono con le
tabelle della tesi (70388 regole esaminate)`.

### A.2.2 `python3 pruning/verifica_tetto.py` — il tetto della potatura certificata (capitolo 4)

**Che cosa fa.** Ricalcola quante regole rimuove `veto-cover` al variare del parametro di ricerca
`max_extra`, su otto configurazioni, e confronta il totale con la tabella della relazione. Serve a
mostrare che il tetto della potatura garantita è una proprietà del criterio, non del parametro.

**Parametri.**
- `--valori LISTA` — valori di `max_extra` da confrontare, separati da virgola (default `3,20`).
  Il valore 3 è sempre incluso perché è il riferimento della tabella.

**Esempio.**
```bash
python3 pruning/verifica_tetto.py
python3 pruning/verifica_tetto.py --valori 3,4,5,6,8,10,15,20
```

**Esito atteso** (circa mezzo minuto con i valori di default): totale `8 939 → 8 940`, cioè una
sola rimozione in più su otto casi.

---

## A.3. `python3 pruning/benchmark.py` — il confronto A/B

**Che cosa fa.** È l'ambiente di valutazione: copia l'archivio in `.scratch/bench_lab`, esegue il
sistema sulla configurazione di partenza, pota il file delle regole una volta per ogni variante
richiesta, riesegue il sistema su ciascun file potato, calcola le metriche in forma appaiata e le
stampa; scrive una voce per esecuzione nel file JSON indicato.

**Parametri.**
- `--datasets LISTA` — i dataset da usare, separati da virgola, indicati **senza** estensione e
  **senza** numero di ripetizione (es. `bridges_14`, che vale per `bridges_14_1.csv`).
- `--runs LISTA` — le ripetizioni, separate da virgola (es. `1,2,3`).
- `--thresholds LISTA` — le soglie, separate da virgola (es. `9,15`). La soglia è il valore passato
  al sistema come `args[4]`.
- `--variants LISTA` — le varianti da confrontare, nella forma `nome=strategia:politica`, separate
  da virgola. Più strategie si concatenano con `+`, per esempio
  `A5b=exact-priority+dom-sub-adaptive:allow`. La politica può essere `protect`, `allow` o
  `budget:F`.
- `--prune-extra "ARGOMENTI"` — argomenti aggiuntivi passati testualmente al potatore, per esempio
  `"--adaptive-alpha 0.85"`.
- `--out FILE` — dove scrivere i risultati (JSON). Senza questo argomento i risultati sono solo
  stampati.
- `--family NOME` — famiglia dei dataset (`bridges`, `glass`, `restaurant`, `physician`), oppure
  `auto` per dedurla dai nomi.
- `--dataset-dir CARTELLA`, `--tuple-dir CARTELLA` — cartelle alternative per dataset e ground
  truth (servono a Glass, che nell'archivio ha i nomi di colonna anonimizzati).
- `--text-thr VALORE` — soglia di similarità testuale normalizzata (0..1) oltre la quale
  un'imputazione testuale conta come corretta (per Restaurant si usa 0,8).
- `--coltypes {B,D}` — `B` è la tipizzazione dello script pubblicato nell'archivio, `D` è la
  variante che corregge il difetto del tipo booleano.
- `--reuse-baseline FILE` — riusa i record di baseline già calcolati in un altro JSON, evitando di
  rieseguire la configurazione di partenza.
- `--skip-baseline` — usa il baseline dell'archivio invece di rieseguirlo (solo con `--coltypes B`).
- `--maxthr-offset N` — aggiunge `N` alla soglia passata al sistema per le varianti potate:
  compensa la copertura persa dalla potatura. Il baseline usa sempre la soglia nominale.
- `--keep-populated-dir CARTELLA`, `--keep-results-dir CARTELLA` — copiano gli output di ogni run
  (prefissati dal nome della variante): servono all'analisi per cella dell'impatto dei veti.
- `--checkpoint-every N` — scrive il file di risultato ogni `N` configurazioni, per non perdere il
  lavoro nelle campagne lunghe.

**Esempio** (potatura aggressiva A5b su una configurazione, circa un minuto).
```bash
python3 pruning/benchmark.py --datasets bridges_14 --runs 1 --thresholds 9 \
    --variants "A5b=exact-priority+dom-sub-adaptive:allow" \
    --prune-extra "--adaptive-alpha 0.85" \
    --out .scratch/prova_A5b.json
```

**Esito atteso**, su `bridges_14_1` a soglia 9:

| variante | RFD | riduzione | copertura | precisione | accuratezza | preprocessing |
|---|---|---|---|---|---|---|
| A (partenza) | 8 961 | — | 0,714 | 0,900 | 0,643 | 28,1 s |
| A5b | 1 366 | 84,8 % | 0,714 | 1,000 | 0,714 | 4,9 s |

Con due varianti nello stesso comando (per esempio la garantita e l'aggressiva) il confronto resta
appaiato e le due righe si leggono nella stessa tabella:
```bash
python3 pruning/benchmark.py --datasets bridges_14 --runs 1 --thresholds 9 \
    --variants "VC=veto-cover:protect,A5b=exact-priority+dom-sub-adaptive:allow" \
    --prune-extra "--adaptive-alpha 0.85" --out .scratch/prova_AB.json
```

> **Le esecuzioni non possono essere parallele**: la cartella di lavoro del sistema è condivisa e
> due esecuzioni simultanee sovrascrivono gli output senza segnalare errori.

---

## A.4. `python3 pruning/pruning.py` — il potatore

**Che cosa fa.** Riscrive un file di regole rimuovendone una parte, secondo una o più strategie.
È indipendente dal sistema: non esegue nulla, non tocca dataset né eseguibile, e produce un file
dello stesso formato dell'input, pronto per il sistema.

**Parametri.**
- `--rfd FILE` — il file di regole di input (in `RENUVER/RFD/`).
- `--dataset FILE` — il dataset CSV, o più dataset separati da virgola (ammessi i caratteri
  jolly). Serve a determinare quali colonne presentano valori mancanti: da lì dipendono le
  condizioni `[V1]`–`[V3]`.
- `--output FILE` — dove scrivere il file di regole ridotto.
- `--strategy LISTA` — le strategie da applicare, separate da virgola e applicate in sequenza.
  Le venti disponibili: `duplicates`, `inert`, `veto-cover`, `veto-dominance`, `coverage`,
  `dom-sub`, `dom-sub-strict`, `dom-sub-adaptive`, `score-argmin`, `exact-priority`,
  `precision-priority`, `intra-cluster-priority`, `dom-exact`, `rhs-thr`, `lhs-cap`, `used`,
  `empirical`, `hybrid`, `auto`, `classical-cover`.
- `--veto-policy POLITICA` — che cosa fare delle regole che possono esercitare un veto:
  `protect` (default) le ripristina tutte, `allow` non ne tutela nessuna, `budget:F` ne consente la
  rimozione per una frazione `F`.
- `--coltypes LISTA` — i tipi di colonna separati da virgola, come `args0` del sistema; servono
  alla strategia `score-argmin` per replicare la formula del punteggio.
- `--maxthr N` — il valore che il sistema riceverà come `args[4]`; è anche la soglia di
  accettazione del punteggio di `score-argmin` (default: la soglia massima del file di regole).
- `--max-extra N` — di quante colonne possono differire i LHS nei confronti di dominanza e di
  copertura. Default 1; la ricerca dei copritori `[V2]` usa comunque almeno 3 (cioè `max(N, 3)`),
  perché è il valore con cui sono state condotte le campagne.
- `--precision-alpha V`, `--adaptive-alpha V`, `--adaptive-side {stable,unstable}` — parametri
  delle strategie data-driven: forza dello shrinkage sulla precisione stimata dei cluster, soglia
  di stabilità del LHS e lato su cui applicarla.
- `--veto-order {exposure,cells}` — come ordinare le regole da rimuovere sotto
  `--veto-policy budget:F`: `exposure` usa il profilo aggregato dei nulli per colonna (proxy
  misurato come cattivo), `cells` usa il numero di celle nulle reali che ogni regola può servire.
- `--max-rhs-thr V`, `--max-lhs N` — filtri: soglia RHS massima accettata, numero massimo di
  colonne nel LHS.
- `--results-dir CARTELLA`, `--populated-dir CARTELLA`, `--family NOME`, `--exclude REGEX` — dove
  leggere le statistiche di training (cartelle `Results/` e `Populated/` dell'archivio), come
  filtrare i file per famiglia e quali escludere (leave-one-out).
- `--min-uses N`, `--min-acc V` — soglie della strategia `empirical`.
- `--ground-truth FILE` — file `TupleIniziali` per la validazione.
- `--report` — stampa il dettaglio: regole in ingresso, rimosse per ciascuna strategia, rimaste.

**Esempio** (potatura garantita, la più conservativa).
```bash
python3 pruning/pruning.py \
    --rfd RENUVER/RFD/output_false_9_bridges.csv \
    --dataset "RENUVER/Dataset/bridges_14_1.csv" \
    --output .scratch/rfd_potato.csv \
    --strategy veto-cover --veto-policy protect \
    --coltypes "D,C,D,D,D,D,D,B,B,D,D,D,D" --report
```

**Esito atteso**: `RIDUZIONE: 1531 (17.1%)` su 8 961 regole, con il file di uscita pronto per il
sistema. Sostituendo `--strategy veto-cover` con `inert` o `duplicates` la riduzione scende
(sono le altre due strategie con garanzia dimostrabile); con
`--strategy exact-priority+dom-sub-adaptive --adaptive-alpha 0.85 --veto-policy allow` sale
all'84,8 % su questa configurazione.

---

## A.5. Gli strumenti che leggono i dati già raccolti

Nessuno di questi esegue il sistema: leggono i file di `results/`, i file di regole o i log.

| comando | parametri | che cosa produce |
|---|---|---|
| `python3 pruning/audit_report.py` | nessuno | ricontrolla le **67 asserzioni numeriche** della relazione contro i JSON: atteso `67 OK, 0 DIVERGENZE` (le etichette dei gruppi rimandano alla relazione tecnica estesa, documento a parte) |
| `python3 pruning/stats_effects.py` | nessuno | dimensioni dell'effetto, intervalli di confidenza bootstrap, correzione di Holm: atteso `4/4 PASS` sui controlli di regressione |
| `python3 pruning/ablation_a5b.py` | `--json` (salva anche il JSON dell'ablazione) | contributo dei due componenti di A5b, griglia completa, confronto multi-dataset |
| `python3 pruning/trivial_baseline.py` | nessuno | accuratezza di un imputatore banale (moda di colonna) sulle stesse celle |
| `python3 pruning/make_appendix_tables.py` | `--out FILE.tex` | tabelle complete delle campagne |
| `python3 pruning/analyze_order.py` | `--json FILE`, `--metric {correct,wrong,accuracy}`, `--correct` | i tre confronti dell'esperimento sull'ordine dei cluster |
| `python3 pruning/verify_veto.py` | `--rfd-full`, `--rfd-pruned`, `--dataset`, `--coltypes`, `--maxthr`, `--max-cells`, `--max-values`, `--report` | verifica empirica della condizione `[V2]` (richiede `numpy`) |
| `python3 pruning/prune_rfd.py` | `--rfd`, `--dataset`, `--out`, `--coverage`, `--dominance {none,sub,super,sub+super}`, `--max-lhs`, `--min-rhs-thr`, `--blacklist`, `--report` | la riduzione classica di ridondanza, senza le strategie veto-consapevoli |

**Esempio.**
```bash
python3 pruning/audit_report.py
python3 pruning/verify_veto.py --rfd-full RENUVER/RFD/output_false_9_bridges.csv \
    --rfd-pruned .scratch/rfd_potato.csv --dataset RENUVER/Dataset/bridges_14_1.csv \
    --coltypes "D,C,D,D,D,D,D,B,B,D,D,D,D" --maxthr 9 --report
```

---

## A.6. Le campagne e la misura del costo

**A.6.1 Campagne** (`pruning/campagne/*.sh` e `pruning/*.sh`). Nessun parametro: ogni script contiene
la propria griglia. Si eseguono dalla cartella radice, per esempio
`bash pruning/campagne/vetocost.sh`. Prima di lanciarne una conviene copiare i risultati
(`cp -r results results_originali`), perché i nomi dei file di uscita sono gli stessi di quelli
consegnati.

**A.6.2 Misura del costo** (capitolo 2). Nessun parametro:

| comando | durata | che cosa fa |
|---|---|---|
| `bash strumentazione_costo/prova_equivalenza.sh` | ~2 min | esegue l'eseguibile originale e quello ricostruito sulla stessa configurazione e confronta gli output: `Populated/` e `Results/` devono essere identici |
| `bash strumentazione_costo/esegui_strumentato.sh` | ~5 min | esegue la build strumentata sulle due configurazioni del capitolo 2 e stampa i contatori (531, 151, 293, 8, 354 809 scansioni) |

---

## A.7. `bash verifica_completa.sh` — la verifica di tutta la strumentazione

**Che cosa fa.** Esegue e controlla l'intera cartella in sette passi: ambiente e impronta
dell'eseguibile; sintassi di tutti gli script; strumenti offline con l'esito atteso; potatura e
trasformazioni reali; estrattori storici; campagne ed esecuzioni del sistema; confronto delle
impronte MD5 dei file consegnati prima e dopo la verifica.

**Parametri.** Nessun argomento posizionale; le opzioni si possono combinare.
- `--analisi` — aggiunge i 19 estrattori storici di `analisi/`.
- `--run` — aggiunge le procedure che eseguono il sistema (verifica rapida, confronto A/B,
  contabilità dei veti, esperimento sull'ordinamento, raccolta statistiche, sonda Physician,
  misura del costo).
- `--tutto` — equivale a `--analisi --run`.
- `--help` — stampa le modalità disponibili.

**Esempio.**
```bash
bash verifica_completa.sh --tutto
```

**Esito atteso**: `67 OK, 0 FAIL, 2 non eseguite` e, in fondo, `nessun file consegnato è stato
modificato dalla verifica`. Ogni voce lascia il proprio log in `.scratch/verifica/log/`; il codice
di uscita è 0 solo se non c'è nessun `FAIL`.
