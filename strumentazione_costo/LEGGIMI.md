# Strumentazione del costo computazionale

Materiale che sostiene la sezione **«Costo computazionale»** del capitolo 2 della tesi
(tabella `tab:cost` e figura `fig:cost`): la ripartizione del tempo di esecuzione fra
**generazione dei candidati** e **verifica dei veti**, e la misura di quante volte il controllo
dei veti scandisce il dataset.

---

## 1. Perché serve una build separata

Il sistema è distribuito senza sorgenti, quindi non si può sapere *dove* vada il tempo guardando
il codice. La via seguita è stata:

1. **decompilare** le classi applicative dell'archivio;
2. **ricompilare** i sorgenti ottenuti in una build separata (`RENUVER_clean.jar`);
3. **verificare l'equivalenza** di quella build rispetto all'originale, confrontando gli output
   (`prova_equivalenza.sh`);
4. **strumentare** la build equivalente con la tecnica dei *wrapper* (`instrument.py`),
   ottenendo `RENUVER_instr.jar`, che scrive i contatori nel file `Logs/`;
5. **misurare** su due configurazioni (`esegui_strumentato.sh`).

L'eseguibile dell'archivio **non è mai stato modificato**: `RENUVER/RENUVER_EDBT.jar` ha impronta
MD5 `c7b9238d6631c64fadd47ebfae00db8e`, la stessa del file consegnato. I due JAR di questa
cartella sono **file distinti**, prodotti dalla ricostruzione e usati solo per la misura:

| file | che cos'è | impronta MD5 (12) |
|---|---|---|
| `RENUVER_clean.jar` | ricostruzione dai sorgenti decompilati, senza alcuna modifica di comportamento | `3758ddb9bcc7` |
| `RENUVER_instr.jar` | la stessa ricostruzione con i wrapper di cronometraggio | `65cecf562a55` |

---

## 2. La misura

| configurazione | procedura | chiamate | tempo | quota |
|---|---|---|---|---|
| `bridges_70_1`, soglia 15 | generazione dei candidati | 531 | 1,4 s | 0,8 % |
| | verifica dei veti | 151 | 158,4 s | 99,2 % |
| | *di cui scansione del dataset* | *354 809* | *158,3 s* | *99,0 %* |
| `bridges_14_1`, soglia 9 | generazione dei candidati | 293 | 1,5 s | 14,4 % |
| | verifica dei veti | 8 | 9,1 s | 85,6 % |
| | *di cui scansione del dataset* | *18 360* | *9,1 s* | *85,4 %* |

I log completi di quella misura sono in `esiti/log_strumentato_*.txt`: sono gli stessi numeri
citati nel capitolo 2. Il metodo di strumentazione è documentato in
`esiti/estratto_strumentazione.txt`.

**Che cosa è riproducibile e che cosa no.** I *conteggi* (531, 151, 293, 8, 354 809, 18 360) sono
proprietà strutturali dell'esecuzione e si riproducono identici su qualunque macchina. I *tempi*
dipendono dall'hardware: cambiano i millisecondi e le percentuali di qualche decimo, non la
conclusione (la verifica dei veti domina).

---

## 3. Come rieseguire

```bash
bash strumentazione_costo/prova_equivalenza.sh    # ~2 minuti
bash strumentazione_costo/esegui_strumentato.sh   # ~5 minuti
```

Il primo comando esegue l'originale e la ricostruzione sulla stessa configurazione in cartelle
isolate e confronta i file prodotti: `Populated/` (celle imputate) e `Results/` (esito per cella)
devono risultare **byte-identici**; il file `Logs/` contiene i tempi e la memoria dell'esecuzione e
quindi differisce (nella misura della fase: `Memory Consumption` 310 MB contro 280 MB).

Il secondo esegue la build strumentata sulle due configurazioni del capitolo 2 e stampa il blocco
`STRUMENTAZIONE` scritto nel log. Entrambi scrivono nell'area di lavoro `.scratch/costo/` e non
toccano né l'archivio né i file consegnati.

Servono solo Java 8 o superiore (i JAR sono compilati per la versione 52 del formato `class`).
**Le due esecuzioni non vanno lanciate in parallelo**: la cartella di lavoro del sistema è
condivisa al suo interno e due run simultanei si sovrascriverebbero gli output (per questo gli
script usano cartelle separate e vanno eseguiti uno alla volta).

---

## 4. Che cosa non è incluso

- **Il JDK portatile** usato per ricompilare (circa 350 MB): si scarica a parte, non serve per
  rieseguire nulla di questa cartella.
- **Gli alberi dei sorgenti decompilati** (`src_fix`, `src_instr`): si rigenerano con un
  decompilatore (è stato usato `cfr`) a partire da `RENUVER/RENUVER_EDBT.jar`.
- **I decompilatori** (`cfr.jar`, `procyon.jar`): scaricabili pubblicamente.

`instrument.py` è incluso come **documentazione della tecnica** adoperata: per eseguirlo servono i
sorgenti decompilati, quindi non parte da solo in questa cartella.
