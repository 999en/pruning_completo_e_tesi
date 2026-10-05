# RENUVER `FillingAlgorithm` — dead/support methods, reconstructed from bytecode

> **Riproduzione.** Le classi analizzate sono in `analisi/classi/`: sono l'estrazione delle 13 classi
> applicative dell'archivio, rigenerabile con `python3 analisi/estrai_classi.py` (l'archivio non viene
> modificato: lo script stampa l'impronta MD5 prima e dopo). Gli strumenti citati stanno in
> `analisi/strumenti/`, per esempio
> `python3 analisi/strumenti/jvmdis.py analisi/classi/FillingAlgorithm.class` e
> `python3 analisi/strumenti/absbr_ex.py analisi/classi/FillingAlgorithm.class`.

Scope: `analisi/classi/FillingAlgorithm.class`, `analisi/classi/FillingAlgorithm$NullValueComparator.class`,
`analisi/classi/FillingAlgorithm$TimesInvolvedComparator.class` (extracted JAR, class-file major version 52 = Java 8).
All offsets below are **code-array offsets (pc) inside the named method**, as printed by `absbr.py`
(absolute targets = `pc + raw relative offset`). Constant-pool strings are quoted with `repr`-exact
content (several contain embedded `\n`), verified against the CP table, not the truncated comments.

Established context used without re-derivation: `start(int)` ignores its argument and calls
`sequentialExecution()`; `localSearchExecution`, `getNewGenerations`, `calculateGainInSwap`,
`nullValueBasedOrderExecution`, `timesInvolvedInLHSBasedOrderExecution`, `cloneMap`, `cloneList`,
`countTimeInvolved` have **no callers** in this release.

## 0. Data model facts needed by every method below

| Element | Evidence |
|---|---|
| `Field.key` = column name, `Field.value` = cell value (`"?"` = NULL) | `Field.<init>(String,String)`; `treatNullTuple` tests `Field.getValue().equals("?")` (`ldc_w #382` = `'?'`) |
| `Tuple.fields` = `ObjectArrayList<Field>`; `Tuple.row` 1-based; `Tuple.index` **0-based position in `dataset`** | `getDatasetFromFile`: `iconst_1; istore 9` (row), `iconst_0; istore 10` (index), then `new Tuple(fields, slot9++, slot10++)` + `dataset.add(...)` (pcs 98–211) |
| `Tuple.nullFieldsCount` / `Tuple.nullFields` are *derived* caches, filled by the pre-processing loop | `Tuple.setNullFieldsCount/setNullFields` |
| `Tuple.involvedInLHSCount` — only ever written by `timesInvolvedInLHSBasedOrderExecution` | single `Tuple.setInvolvedInLHSCount` call site, `invokevirtual` at pc 251 |
| `rfdForRHS` : `Object2ObjectLinkedOpenHashMap<String /*RHS column*/, Map<Double /*threshold*/, ArrayList<RFD>>>` | `findBestRFDs` builds `Object2ObjectLinkedOpenHashMap` and `put(Double.valueOf(rfd.getRHS().getThreshold()), ArrayList<RFD>)`; `createMapOnRHS` stores it under `Field.getKey()` |
| `Column.equals` compares **only `name`** (then `getClass`/null checks) | `Column.equals` pcs 26–64: `getfield Column.name` / `String.equals` / `ireturn`; no threshold/index/type compared |
| `RFD.getLHS()` : `ArrayList<Column>` | `RFD.getLHS` |

`sequentialExecution()` baseline (for the divergence sections): banner `#377 'Sequential heuristic selected!'`
→ `startTime = currentTimeMillis()` → loop `i` over `dataset`, rebuild `nullFields` list, `nullCells++` per
`"?"`, then (only if the list is non-empty, `ifle` pc 116) `setNullFieldsCount`, `setNullFields`, and
`list.add(tuple)` → `for (Tuple t : list) treatNullTuple(t, t.getIndex())` → log
`#398 'Total execution time '`, `ms`, `#400 '#Null cells: '`, `#402 '#Cells not filled: '`.

---

## 1. `countTimeInvolved(Field)` → `int`

**Purpose.** Count how many times a column appears in the LHS of the rules known to the object.

**Inputs.** `arg1` = a `Field` (only `getKey()`/the column name is used).
**Outputs.** `int` (slot 2), the raw occurrence count.
**Reads.** `this.allRfd` only. No use of `rfdForRHS`, of the RHS, or of any threshold.

**Exact loop order** (purely nested iteration, no early exit, no filtering):

```
n = 0                                            // pc 0-1
for (RFD r : this.allRfd)                        // pc 2-9 getfield allRfd / iterator
    for (Column c : r.getLHS())                  // pc 25-32  RFD.getLHS() / ArrayList.iterator
        if (c.getName().equals(field.getKey()))  // pc 49-58  Column.getName / Field.getKey / String.equals
            n++;                                 // pc 61 ifeq -> 67 ; pc 64 iinc slot 2 by 1
return n;                                        // pc 87-88 iload_2 / ireturn
```

**Semantics / caveats.**
* Counts **occurrences**, not distinct rules: a column listed twice in one LHS counts twice; two RFDs with
  the same column count twice.
* The keyword `LHS` is literal: `allRfd` at the moment of the call. `start()` removes the "key RFDs" from
  `allRfd` before invoking the execution heuristic (pcs 38–84 of `start`: skip a rule when
  `RHS.threshold != 0` (pc 48) or `isKeyRfd(rfd) != 0` (pc 57), else `keyRFDs.add` + `Iterator.remove`),
  so in the intended call order only
  the non-key RFDs are counted — but the method itself has no such filter.
* Weight/coefficient: none. The value is an unweighted, unsigned integer (≥0).
* **Storage side effect is in the caller, not here**: the caller caches this per column name and copies the
  value into `Field.timesInvolved` (see §7).

**Divergence from `sequentialExecution`.** N/A (no counterpart there).

---

## 2. `cloneMap(...)` → `Object2ObjectLinkedOpenHashMap` and `cloneList(...)` → `ObjectArrayList`

### 2.1 `cloneMap` (private, instance)

```
copy = new Object2ObjectLinkedOpenHashMap();   // pc 0-7
copy.putAll(arg);                              // pc 8-10
return copy;                                   // pc 13-14
```

**Shallow at both levels.** `putAll` copies the *entries*; the value objects (`Map<Double,ArrayList<RFD>>`
buckets, their `ArrayList`s and the `RFD`s) are shared with the original map. Consequences for
`localSearchExecution` (§5), which uses it as a "restore snapshot" of `rfdForRHS`: replacing a bucket in the
copy would not affect the original, but `revaluateKeyRFDs`/`updatePattern` mutate `RFD`s and the buckets that
are shared, so the restore is only partial (§9, ambiguity A6).

### 2.2 `cloneList` (**static**, access 0x9)

```
copy = new ObjectArrayList(arg.size());        // pc 0-11
for (Tuple t : arg) copy.add(t.clone());       // pc 12-38: ObjectArrayList.iterator / Tuple.clone / add
return copy;                                   // pc 48-49
```

**Depth: deep at list+Tuple level, shallow at Field level.**
`Tuple.clone()` (`Tuple.class`) = `new Tuple(fields.clone(), row, index)` + `setNullFields(nullFields.clone())`
+ `setNullFieldsCount(nullFieldsCount)`.
* New container, new `Tuple` objects, new `fields` list and new `nullFields` list objects.
* The **`Field` elements themselves are shared** (`fields.clone()` is a shallow list copy; `Field.clone()`
  exists but is never called anywhere in `FillingAlgorithm`).
* `Tuple.clone()` does **not** copy `involvedInLHSCount` → every clone starts with `involvedInLHSCount == 0`.
* Benign in practice for values: nothing in the class calls `Field.setValue` (only `Field.<init>` and
  `ObjectArrayList.set(i, new Field(...))` occur), so shared `Field` objects are not mutated in place; only
  `Field.timesInvolved` (set by §7, which never clones) is mutable.

Call sites: `cloneList` ×7 and `cloneMap` ×2, **all inside `localSearchExecution`** (pcs 238, 244, 254, 339,
347, 355, 363, 658, 666, 674, 682, 714).

---

## 3. `calculateGainInSwap(Tuple, Tuple)` → `double`

**Purpose.** Score the *current relative order* of two tuples: how much the later tuple would gain from the
earlier one being imputed first, minus the reverse. Used only by `getNewGenerations` (§4).

**Inputs.** `arg1` = the tuple that is currently **earlier** in the order; `arg2` = the tuple currently
**later**. Both must already carry their `nullFields` list and `nullFieldsCount` (set by the pre-processing loop
or by `Tuple.clone`).
**Outputs.** `double` in `[-1, 1]`, dimensionless (a difference of two coverage *fractions*, not a count of cells).
**Reads.** `arg1.getNullFields()`, `arg2.getNullFields()`, their `getNullFieldsCount()`, and the field
`this.rfdForRHS`.

**Exact formula** (slots: `slot3` = `c1`, `slot5` = `c2`, `slot6`/`slot7`/`slot8`… = iterators):

```
c1 = 0.0                                                        // pc 0-1: dconst_0 / dstore_3
for (Field fb : arg2.getNullFields()) {                         // pc 2-6  (aload_2 -> getNullFields)
    Map<Double,ArrayList<RFD>> m = rfdForRHS.get(fb.getKey());  // pc 26-41
    if (m != null) {                                            // pc 43-45: ifnull -> next fb
        for (ArrayList<RFD> bucket : m.values()) {              // pc 48-60
            for (RFD r : bucket) {                              // pc 77-82
                for (Field fa : arg1.getNullFields()) {         // pc 99-106 (aload_1 -> getNullFields)
                    Column col = new Column(fa.getKey(), 0.0, 0, "");   // pc 123-140
                    if (r.getLHS().contains(col)) {             // pc 142-152 ArrayList.contains(Column)
                        c1 += 1.0;                              // pc 155-158 dload_3/dconst_1/dadd/dstore_3
                        break;                                  // pc 159 goto 172 => next RFD
                    }
                }
            }
        }
    }
}
if (c1 != 0.0) c1 = c1 / (double) arg2.getNullFieldsCount();    // pc 202-215: dcmpl/ifeq, i2d, ddiv
c2 = 0.0;                                                       // pc 216-217
/* mirror image with arg1<->arg2 swapped:                                  pc 219-418 */
for (Field fa : arg1.getNullFields()) {                         // pc 219-223
    Map<Double,ArrayList<RFD>> m = rfdForRHS.get(fa.getKey());  // pc 243-258
    if (m != null) {
        for (ArrayList<RFD> bucket : m.values())                // pc 265-277
            for (RFD r : bucket)                                // pc 294-299
                for (Field fb : arg2.getNullFields()) {         // pc 316-323
                    Column col = new Column(fb.getKey(), 0.0, 0, "");   // pc 340-357
                    if (r.getLHS().contains(col)) { c2 += 1.0; break; } // pc 359-378
                }
    }
}
if (c2 != 0.0) c2 = c2 / (double) arg1.getNullFieldsCount();    // pc 421-436
return c1 - c2;                                                 // pc 438-442: dload_3 / dload 5 / dsub / dreturn
```

So, with `N(a)` = `a.getNullFieldsCount()` and `hits(x→y)` = number of RFDs `r` such that
`r.RHS.name ∈ {null columns of y}` and `∃ f ∈ nullFields(x) : r.LHS.name contains f.name`
(counted once per RFD thanks to the `break`):

```
gain(arg1 earlier, arg2 later) = hits(arg1 → arg2)/N(arg2)  −  hits(arg2 → arg1)/N(arg1)
```

**Exact comparison / short-circuit logic**
* `if (m == null)` → the RHS column has no rules at all → skip that null field (`ifnull` pc 45 / pc 262).
* Membership test is **name-only** (`Column.equals`), and the temporary column is built with the literal
  arguments `0.0, 0, ""` (pc 132-137 / pc 349-354), so threshold/type/index are irrelevant.
* `break` after `c1 += 1.0` (pc 159 `goto 172`) and after `c2 += 1.0` (pc 378 `goto 391`): per (null field, RFD)
  pair at most one hit, even if several null columns of the other tuple occur in the same LHS.
* Division guard: the division is executed only when the numerator differs from `0.0` (`dcmpl; ifeq`,
  pc 204-205 and pc 424-425). This avoids `0/0 = NaN` when a tuple has no null field at all (then its hit count
  is also 0, since the hits are discovered *through* that tuple's null fields); note the guard tests the
  numerator, not the divisor, so with the stale-cache situation of §7 (`nullFields` non-empty but
  `nullFieldsCount` never written) a non-zero numerator over a `0` divisor would yield `±Infinity`. This is not
  reachable from the only caller (`localSearchExecution` always sets both caches together).
* Constants: `0.0` (`dconst_0`) and `1.0` (`dconst_1`) only — the unit of a hit is "one RFD", and normalisation
  turns it into a fraction of the tuple's missing cells.

**Interpretation (marked as interpretation, not bytecode).** Write `A = arg1` (currently earlier) and
`B = arg2` (currently later). Then `c1 = enabled(B ← A)/N(B)` and `c2 = enabled(A ← B)/N(A)`, so
`gain = c1 − c2` is, in words, *"how much more the current order (A first) is worth than the swapped order
(B first)"*: `gain > 0` means the current order is preferable, `gain < 0` means the tuple that is currently
later benefits more from the partner and should therefore be moved **after** it (i.e. the greater beneficiary
ends up last, right after its donor). The bytecode facts that constrain this reading are: the first term always
iterates `arg2`'s null fields and normalises by `arg2`'s count (pc 2-6, pc 202-215), the second does the mirror
on `arg1` (pc 219-223, pc 421-436), and the subtraction is `c1 − c2` (pc 438-442); combined with the swap
construction in `getNewGenerations` (child order = parent order with positions `i`, `i+1` exchanged, §4), the
sign convention is fixed unambiguously. This choice is what makes the compiled `gain < 0` accept test of §4
semantically coherent and isolates the actual defect to the final `bestGain > 0` gate.

**Divergence from `sequentialExecution`.** N/A — the sequential heuristic has no ordering score at all; it
never compares tuples.

---

## 4. `getNewGenerations(Object2DoubleMap$Entry, ObjectArrayList, ObjectArrayList)` → `java.util.Map`

**Purpose.** From one parent "generation" (an execution order), produce its best single adjacent-swap child.

**Inputs (slots after `this`):**
* `arg1` (`slot1`) — an entry of the `scores` map built in `localSearchExecution`. `getKey()` is **not** a column
  name: it is a **comma-terminated permutation string of positional indices into the null-tuple list**, e.g.
  `"0,1,2,3,"` (built at `localSearchExecution` pc 167-194). `getDoubleValue()` is *never* read here: the only
  `Object2DoubleMap$Entry` member invoked in the whole body is `getKey` (pc 10); the entry's double value is
  consumed only by the caller's log statements.
* `arg2` (`slot2`) — `knownOrders`: `ObjectArrayList<String>` of order strings already generated/seen
  (seeded with the parent order by the caller); it is both a **dedup filter** and a **sink**
  (`contains` pc 282; `add` pc 296-299).
* `arg3` (`slot3`) — `tupleList`: `ObjectArrayList<Tuple>` holding one clone per dataset tuple that has ≥1 null
  cell, **in dataset order**. The parsed indices index *this* list (`ObjectArrayList.get` pc 72 / pc 86), and
  `calculateGainInSwap` is applied to `tupleList.get(order[i])`, `tupleList.get(order[i+1])` (pc 65-92).

**Outputs.** A `Double2ObjectLinkedOpenHashMap` (declared `java.util.Map`) mapping
`Double bestGain → String childOrder`, i.e. **at most one entry** (there is exactly one `Map.put` site,
pc 378). Not a multi-child collection.

**Initialisation.** `bestGain = Double.MAX_VALUE` (`ldc2_w #549` = raw bits `9218868437227405311` =
`0x7FEFFFFFFFFFFFFF` = `1.7976931348623157e308`, pc 49-52); `bestOrder = ""` (`ldc_w #415` = `''`, pc 54-57).

**Reconstruction.**

```java
Map<Double,String> out = new Double2ObjectLinkedOpenHashMap();                 // pc 0-7
int[] order = Arrays.asList(((String) entry.getKey()).split(","))              // pc 9-24
                   .stream().mapToInt(Integer::parseInt).toArray();            // pc 27-47, invokedynamic #487
double bestGain = Double.MAX_VALUE;                                            // pc 49-52
String bestOrder = "";                                                         // pc 54-57
for (int i = 0; i < order.length - 1; i++) {                                   // pc 59-62, cond pc 306-313
    double gain = calculateGainInSwap(tupleList.get(order[i]),                  // pc 65-92
                                      tupleList.get(order[i+1]));
    if (gain >= 0 || Double.isNaN(gain)) continue;                             // pc 97-101 dcmpg/ifge -> 303
    if (gain >= bestGain) continue;                                            // pc 104-109 dcmpg/ifge -> 303
    String newOrder = "";                                                      // pc 112-115
    for (int j = 0; j < i; j++) newOrder += order[j] + ",";                    // pc 120-157
    newOrder += order[i+1] + ",";                                              // pc 164-195
    newOrder += order[i]   + ",";                                              // pc 197-226
    for (int j = i + 2; j < order.length; j++) newOrder += order[j] + ",";     // pc 228-276
    if (!knownOrders.contains(newOrder)) {                                     // pc 279-285 ifne -> 303
        bestGain  = gain;                                                      // pc 288-290
        bestOrder = newOrder;                                                  // pc 292-294
        knownOrders.add(newOrder);                                             // pc 296-302
    }
}
if (bestGain > 0) {                                                            // pc 316-320 dcmpl #549 / ifle -> 384
    if (!bestOrder.equals("")) {                                               // pc 323-331 ifne -> 384
        System.out.println("Nuovo ordine da analizzare creato: "               // #558
                           + bestOrder + " prevede un vantaggio di " + bestGain);// #560
        out.put(Double.valueOf(bestGain), bestOrder);                          // pc 369-383
    }
}
return out;                                                                    // pc 384-386
```

**Exact loop order.** One linear pass `i = 0 … order.length-2` (adjacent-position swaps only), nothing else;
no recursion, no randomness, deterministic. With a one-element order the body never runs.
`invokedynamic #487` is resolved through bootstrap method #1 = `LambdaMetafactory.metafactory` with
implementation handle `java/lang/Integer.parseInt(String)I`, i.e. `Integer::parseInt`.
`String.split(",")` drops the trailing empty field, so the parent's trailing comma (see §5) is harmless.

**Comparison/threshold logic (exact, byte-verified).**
* Accept branch requires **strictly `gain < 0`**: pc 100 `0x98 dcmpg` + pc 101 `0x9c ifge -> 303`
  (`dcmpg` also yields `1` for `NaN`, so `NaN` is rejected too; `-0.0` compares equal to `0.0` and is rejected).
* Best-so-far requires **strictly `gain < bestGain`**: pc 108 `dcmpg` + pc 109 `ifge -> 303`.
  Ties therefore keep the **earliest** swap index `i`.
* Final gate: pc 319 `0x97 dcmpl` + pc 320 `0x9e ifle -> 384` → the `put` is skipped when `bestGain <= 0`.

**⚠ Decisive internal contradiction — the returned map is always empty.**
The accepted gains are, by construction, `< 0` (pc 101). `bestGain` starts at `+Double.MAX_VALUE` (pc 51) and is
only ever assigned an accepted gain (pc 288-290). Hence at pc 320 either
(a) no swap was accepted → `bestGain == +MAX_VALUE`, `bestOrder == ""` → the `put` is skipped by pc 331, or
(b) at least one swap was accepted → `bestGain < 0` → the `put` is skipped by pc 320.
There is exactly one `Map.put` in the method (grep of the whole method body: a single `#565 Map.put` at pc 378),
so **`getNewGenerations` always returns an empty map**. The intended-positive log line
`#558 'Nuovo ordine da analizzare creato: ' … #560 ' prevede un vantaggio di '` is **unreachable**.
This is a dead-code bug, not a disassembler artefact: the mnemonics were re-checked at byte level
(pc 100/101 = `98 9c`, pc 319/320 = `97 9e`), and the opcode table is the standard one
(`0x97 dcmpl, 0x98 dcmpg, 0x9c ifge, 0x9e ifle`).
Two repairs are conceivable — (i) inverting the accept test to `gain > 0` (the method would then work as
written, but with the *opposite* heuristic: it would move the greater beneficiary **before** its donor, i.e.
`calculateGainInSwap`'s two terms would have to be read as `enabled(A←B)/N(A) − enabled(B←A)/N(B)`), or
(ii) inverting the final gate to `bestGain < 0`. Reading the formula as in §3, (ii) is the
minimal-edit and semantically coherent repair (positive gain = "the current order is better"), so the defect is
most plausibly the single inverted comparison at pc 320. The bytecode alone cannot prove which line was meant;
what it does prove is that as compiled, no child is ever produced.

**Divergence from `sequentialExecution`.** N/A — only reachable from `localSearchExecution`.

---

## 5. `localSearchExecution()` → `ObjectArrayList` (private, dead)

**Purpose.** Banner `#413 'Local search heuristic selected!'` (pc 0-6). Greedy sequential imputation like
`sequentialExecution`, but with (a) an explicit, string-encoded **execution order of the null-containing
tuples**, (b) a **baseline** run of the trivial order and (c) an intended generational local search over
adjacent swaps.

**Inputs.** `this.dataset`, `this.rfdForRHS` (already prepared by `start()`: key RFDs moved out of `allRfd`).
**Outputs.** Returns `ObjectArrayList` (pc 919-921 `aload 9 / areturn`) = a `cloneList` snapshot of the last
executed candidate's dataset (baseline if no candidate ever runs, which per §4 is always the case).
The `dataset` **field** is *restored* to the pre-baseline state before returning (§ below), so the return value
is the only carrier of the imputed rows. Log lines written: `#398`, `ms`, `#400`, `#402` + `slot10`.

**Local slots:** `1` = null-tuple list (clones) / later the restored copy; `2` = order string;
`3` = `k`, the number of null-containing tuples (also the pre-increment counter for the order string);
`4` = `i` (phase 1), then the dataset backup; `5` = null-fields list of row `i`, then the null-tuple-list backup;
`6` = clone of row `i`, then the `rfdForRHS` backup; `7` = `scores` (`Object2DoubleLinkedOpenHashMap`);
`8` = `knownOrders`; `9` = the baseline loop's tuple, then the **return value**;
`10` = `notFilledCells` snapshot; `11` = a `scores` entry; `12` = iterator over `scores`;
`13` = child map from `getNewGenerations`; `14` = best score (`double`); `16` = best order string;
`17` = dataset snapshot; `18` = child order string; `19` = iterator over `children.values()`;
`20` = parsed `int[]` permutation; `21` = position index `p`.

**Phase 1 — pre-processing (identical to `sequentialExecution`), pc 9-231.**
```
slot1 = new ObjectArrayList();  startTime = System.currentTimeMillis();    // pc 9-21
slot2 = "";  slot3 = 0;  slot4 = 0;                                        // pc 24-31
for (i = 0; i < dataset.size(); i++) {                                     // pc 33->222, cond pc 222-231
    nulls = new ObjectArrayList();                                         // pc 36-43
    for (Field f : dataset.get(i).getFields())                             // pc 45-63
        if (f.getValue().equals("?")) { nullCells++; nulls.add(f); }        // pc 80-101 (ldc_w #382 '?')
    dataset.get(i).setNullFieldsCount(nulls.size());                       // pc 122-139
    dataset.get(i).setNullFields(nulls);                                   // pc 142-156
    if (nulls.size() > 0) {                                                // pc 159-164 ifle -> 219
        slot2 = slot2 + (slot3++) + ",";                                   // pc 167-194 (iinc AFTER iload)
        list.add(dataset.get(i).clone());                                  // pc 195-218
    }
}
```
⇒ `slot2 == "0,1,2,…,k-1,"` where position `j` is the `j`-th null-containing tuple **in dataset order**, and
`slot1` holds clones of exactly those tuples (`Tuple.index` inside each clone still points at the dataset row).
`nullCells` is the only global counter updated here; `notFilledCells` is not touched.

**Phase 2 — backups and the baseline generation, pc 234-366.**
```
slot4 = cloneList(this.dataset);            // pc 234-241   pre-execution dataset
slot5 = cloneList(slot1);                   // pc 243-247   pre-execution null-tuple list
slot6 = cloneMap(this.rfdForRHS);           // pc 249-257
scores  = new Object2DoubleLinkedOpenHashMap();   // pc 259-266
knownOrders = new ObjectArrayList(); knownOrders.add(slot2);   // pc 268-283
for (Tuple t : slot1) treatNullTuple(t, t.getIndex());         // pc 284-323  == order "0,1,…,k-1,"
slot9 = cloneList(this.dataset);            // pc 326-342   BASELINE RESULT (the eventual return value)
this.dataset = cloneList(slot4);            // pc 344-350   RESTORE
slot1 = cloneList(slot5);                   // pc 353-358   RESTORE
this.rfdForRHS = cloneMap(slot6);           // pc 359-366   RESTORE
slot10 = this.notFilledCells;               // pc 369-373   baseline score
scores.put(slot2, (double) slot10);         // pc 375-384   key = order string, value = unfilled-cell count
if (slot10 <= 0) goto 830;                  // pc 387      short-circuit: nothing left unfilled -> no search
this.notFilledCells = 0;                    // pc 390-392
```

**Phase 3 — generation loop (worklist), pc 395-736.**
The worklist is `scores` itself, walked with a fastutil linked-map entry iterator
(`object2DoubleEntrySet().iterator()`, pc 395-405; single back-edge pc 729-736; per §4/A3 no entry is ever
added, so it drains after the one baseline entry):
```
for (Entry<String,Double> e : scores) {                                  // insertion order (linked map)
    System.out.println("Parto dalla generazione " + e.getKey()          // #447
                       + " che ha ottenuto score " + e.getDoubleValue()); // #452   (print only)
    Map children = getNewGenerations(e, knownOrders, slot1);              // pc 470-479
    System.out.println("Sono state generate " + children.size()           // #464
                       + " nuovi figli");                                 // #469
    double bestScore = 0.0; String bestOrder = "";                        // pc 516-522
    ObjectArrayList bestDataset = new ObjectArrayList();                  // pc 524-531
    for (String child : (Collection<String>) children.values()) {         // pc 533-547
        int[] perm = Arrays.asList(child.split(",")).stream()
                          .mapToInt(Integer::parseInt).toArray();         // pc 550-593
        for (int p = 0; p < perm.length; p++)                             // pc 595-640
            treatNullTuple(slot1.get(perm[p]), slot1.get(perm[p]).getIndex()); // pc 601-629
        bestOrder   = child;                                              // pc 643-645
        bestScore   = (double) this.notFilledCells;                       // pc 647-652
        bestDataset = cloneList(this.dataset);                            // pc 654-661
        this.dataset = cloneList(slot4);                                  // pc 663-669   restore
        slot1        = cloneList(slot5);                                  // pc 672-677   restore
        this.rfdForRHS = cloneMap(slot6);                                 // pc 678-685   restore
        this.notFilledCells = 0;                                          // pc 688-690
        System.out.println(".\n");                                        // pc 693-699   (ldc_w #501)
        scores.put(bestOrder, bestScore);                                 // pc 702-711
        slot9 = cloneList(bestDataset);                                   // pc 712-717
    }
}
System.out.println("Nessuna nuova generazione creata da analizzare\n"
                 + "Elenco delle generazioni trattate");                  // pc 739-745 (single ldc_w #503)
for (Entry<String,Double> e : scores)                                     // pc 748-827
    System.out.println(e.getKey() + "con score: " + e.getDoubleValue());  // #505
```

**Loop order / exact semantics per phase.**
* The baseline order is the identity permutation of the null-containing tuples in dataset order; it is executed
  once, snapshotted into `slot9`, and then the whole mutated state is rolled back, so every candidate starts
  from the same clean state.
* Candidate execution calls `treatNullTuple(list.get(perm[p]), list.get(perm[p]).getIndex())` — the tuple
  objects stay in the list, the permutation only chooses the visiting sequence; `getIndex()` maps back to the
  `dataset` slot that `treatNullTuple` writes (`dataset.set(index, tuple)`).
* **No best-candidate comparison exists in this method**: a grep for `cmp`/`if*` over the whole body yields only
  the 10 control-flow branches listed above — there is no `dcmp*` anywhere. `bestScore`/`bestOrder`/`bestDataset`
  are simply overwritten by each candidate, so if the child map ever held >1 order, the **last iterated** child
  would win, not the best. The only "comparison" in the whole local search is the gain test inside
  `getNewGenerations` (§4).
* Short-circuits: (a) pc 387 — the entire search is skipped when the baseline left 0 unfilled cells;
  (b) pc 164 — tuples with no null cells never enter the order (they keep `nullFieldsCount = 0` and an empty
  `nullFields` list); (c) §4 makes the child loop body unreachable in practice.
* Because `getNewGenerations` always returns an empty map (§4), the effective behaviour is: run the identity
  order once, print `#464/'Sono state generate 0 nuovi figli'` once, print
  `#503 'Nessuna nuova generazione creata da analizzare\nElenco delle generazioni trattate'` once (it is
  emitted unconditionally after the loop), then one `#505` line `<order> con score: <baseline unfilled cells>`,
  then the three log lines and `return` the baseline snapshot. The `"."` prints (pc 693) never happen, and
  `notFilledCells` ends at `0` (reset at pc 390/688) even though `#402` reports the baseline `slot10`.

**Divergences from `sequentialExecution()`.**
1. Explicit order encoding + rollback snapshots (`cloneList`/`cloneMap`, pcs 234-366, 663-685) — sequential
   mutates `dataset`/`rfdForRHS` once and never restores.
2. Executes the whole order a second time per candidate from a clean state (sequential executes once).
3. `return ObjectArrayList` versus `void`; the imputed `dataset` is deliberately **not** left in the field.
4. `#402 '#Cells not filled: '` is fed `slot10` (the baseline counter, pc 908-910) instead of the field
   (sequential reads `notFilledCells`, pc 296-297).
5. Extra `System.out` tracing (`#413`, `#447`, `#452`, `#464`, `#469`, `#501`, `#503`, `#505`).
6. Same banner/log skeleton otherwise, and the same `startTime`/`nullCells` handling.

---

## 6. `nullValueBasedOrderExecution()` → `void` (private, dead)

**Purpose.** Banner `#600 'Null value heuristic selected!'` (pc 8-14). Same greedy imputation as
`sequentialExecution`, but the tuples are imputed **in descending order of their NULL-cell count**
(most incomplete rows first).

**Ordering logic (exact).**
```
slot1.sort(new FillingAlgorithm$NullValueComparator());   // pc 182-190 (ldc/new #602/#604)
for (Tuple t : slot1) treatNullTuple(t, t.getIndex());    // pc 193-226
```
`NullValueComparator.compare(Tuple a, Tuple b)` = `iconst_m1 * (a.getNullFieldsCount() - b.getNullFieldsCount())`
(pcs 0-11) = `b.count - a.count` ⇒ **descending** by `Tuple.getNullFieldsCount()`.
Sort key = the cached `nullFieldsCount` written by the pre-processing loop, i.e. the number of `"?"` cells in
the row. Ties: the call is `invokevirtual ObjectArrayList.sort(Comparator)`, a method **not declared** by
`ObjectArrayList`/`AbstractObjectList`/`AbstractObjectCollection`/`ObjectList` (verified: no `sort` in any of
them; class-file major 52 = Java 8), so it binds to the Java-8 default `List.sort` =
`toArray(); Arrays.sort(a, c); listIterator-set`. `Arrays.sort(Object[],Comparator)` is TimSort ⇒ **stable**,
so equal-count rows keep their dataset order (inference from the JDK default method, not from local bytecode).

**Structure.** The pre-processing loop is the same instruction layout as `sequentialExecution`'s, at the same
offsets: inner field loop `"?"` test (`ldc_w #382` pc 76, `String.equals` pc 79, `ifeq` pc 82),
`nullCells++` (pc 85-92), `nulls.add(f)` (pc 95-101), inner back-edge (pc 102-109 → abs 59),
`if (nulls.size() > 0)` guard (pc 112-116, `ifle` → abs 168), `setNullFieldsCount` (pc 119-134),
`setNullFields` (pc 137-149), `list.add(tuple)` (pc 152-167), `iinc slot2` (pc 168), outer loop condition
(pc 171-179). Then sort, then the execution loop (`treatNullTuple` at pcs 211-217), then the same three log
lines (`#398`/`ms` at pc 229-263, `#400` at pc 266-290, `#402` + field `notFilledCells` at pc 293-317) and
`return` (pc 320).

**Inputs/outputs.** No parameters; mutates `this.dataset` in place (`treatNullTuple` → `dataset.set(i,…)`),
`nullCells`, `notFilledCells`; returns nothing.

**Divergence from `sequentialExecution()`.** Exactly one added step — the `sort` call (pc 182-190); the rest of
the method matches `sequentialExecution` instruction-for-instruction at identical offsets (only the banner
constant differs, `#600` vs `#377`). The list that is sorted is the null-containing-tuples list built by that
same loop, so rows without nulls never participate in the ordering, and — unlike
`timesInvolvedInLHSBasedOrderExecution` — the `nullFieldsCount` values used as sort keys *are* set
(pc 119-134).

---

## 7. `timesInvolvedInLHSBasedOrderExecution()` → `void` (private, dead)

**Purpose.** Banner `#613 'LHS involving counter heuristic selected!'` (pc 16-22). Same greedy imputation, but
tuples are imputed **in ascending order of `Tuple.involvedInLHSCount`**, where that count is the **maximum**,
over the tuple's null fields, of the number of LHS occurrences of that field's column (see §1).

**Local slots:** `1` = null-tuple list; `2` = `Object2IntLinkedOpenHashMap` memo `columnName → count`;
`3` = `i`, later the tuple in the trace loop and in the execution loop; `4` = nulls of row `i`, later the
iterator over `slot1`; `5` = the current `Field` (pre-processing), later the running **max**;
`6` = iterator over fields (pre-processing), later the `Field` inside the max loop;
`7` = the per-column count (pre-processing), later the iterator inside the max loop.

**Phase 1 — pre-processing fused with the LHS bookkeeping, pc 32-364.**
```
slot1 = new ObjectArrayList(); slot2 = new Object2IntLinkedOpenHashMap();   // pc 0-15
startTime = currentTimeMillis();                                            // pc 25-29
for (i = 0; i < dataset.size(); i++) {                                      // pc 32-34 -> 356-364
    nulls = new ObjectArrayList();                                          // pc 37-44
    for (Field f : dataset.get(i).getFields())                              // pc 46-63
        if (f.getValue().equals("?")) {                                     // pc 80-88 (ldc_w #382 '?')
            nullCells++;                                                    // pc 94-101
            int c;                                                          // pc 104-105  c = 0
            if (slot2.containsKey(f.getKey())) c = slot2.getInt(f.getKey()); // pc 107-128
            else { c = countTimeInvolved(f); slot2.addTo(f.getKey(), c); }   // pc 133-152
            f.setTimesInvolved(c);                                          // pc 153-157
            nulls.add(f);                                                   // pc 160-164
        }                                                                   // cond pc 168-175
    if (nulls.size() > 0) {                                                 // pc 178-183 ifle -> 353
        int max = -1;                                                       // pc 186-187 iconst_m1/istore
        for (Field f : nulls)                                               // pc 189-194 -> 228-235
            if (f.getTimesInvolved() > max) max = f.getTimesInvolved();      // pc 211-226 if_icmple / istore
        dataset.get(i).setInvolvedInLHSCount(max);                          // pc 238-251
        dataset.get(i).setNullFields(nulls);                                // pc 254-267
        System.out.println("The tuple at row " + tuple.getRow()             // #639
            + " has " + nulls.size() + " null value/s.\nIts field appear "  // #644 / #646 (embedded \n)
            + max + " times in LHSs of RFDs.");                             // #648
        slot1.add(dataset.get(i));                                          // pc 337-349
    }
}
```
Note: `addTo(key, c)` is reached only when `containsKey` was false, so the memo behaves as a cache
(`columnName → countTimeInvolved(column)`); the `c` for a repeated column is re-read with `getInt`.
The memo is keyed by **column name**, while `setTimesInvolved(c)` writes onto the *current tuple's* `Field`
object, so for a column that is null in several rows the same value is stamped on each of them.

**Phase 2 — sort + trace, pc 367-453.**
```
slot1.sort(new FillingAlgorithm$TimesInvolvedComparator());   // pc 367-375 (#650/#652)
System.out.println("The order is the sequent:");              // pc 378-384 (#653)
for (Tuple t : slot1)                                         // pc 387-391 -> 446-453
    System.out.println(t + " - null value appears " + t.getInvolvedInLHSCount() + " times"); // #659/#664
```
`TimesInvolvedComparator.compare(Tuple a, Tuple b)` = `a.getInvolvedInLHSCount() - b.getInvolvedInLHSCount()`
(pcs 0-9) ⇒ **ascending**. Same `List.sort`-default ⇒ stable, ties keep dataset order (same inference as §6).

**Phase 3 — execution, pc 456-492.** `for (Tuple t : slot1) treatNullTuple(t, t.getIndex())` (pcs 465-482),
then the three standard log lines (pc 495-583) and `return` (pc 586).

**Divergences from `sequentialExecution()` and from `nullValueBasedOrderExecution()`.**
1. The pre-processing loop is *not* identical: it does **not** call `Tuple.setNullFieldsCount`
   (only `setInvolvedInLHSCount`, `invokevirtual` pc 251, and `setNullFields`, `invokevirtual` pc 267, are
   called), so for every tuple in this path all ordering keys read through `getNullFieldsCount()` remain `0` —
   a divergence that would matter if this method were mixed with the `NullValueComparator` or with
   `calculateGainInSwap`'s denominators.
2. It writes `Tuple.involvedInLHSCount` (the only writer in the class) and `Field.timesInvolved`, and uses a
   per-column memo map that no other method maintains.
3. The ordering key is the **max** over the tuple's null fields (initialised to `-1`, pc 186-187), *not* a sum
   and *not* the value of a single field; ascending sort puts the tuples whose missing columns are least
   involved in rule LHSs first.
4. Otherwise identical: same `"?"` test, same `nullCells` counting, same `list.add` guard, same
   `treatNullTuple(t, t.getIndex())` execution, same `#398`/`#400`/`#402` log block with the field
   `notFilledCells`.

---

## 8. Comparative summary vs `sequentialExecution()`

| | `sequentialExecution` | `nullValueBased` | `timesInvolvedBased` | `localSearchExecution` |
|---|---|---|---|---|
| Banner (`System.out`) | `#377` | `#600` | `#613` | `#413` |
| Pre-processing loop | canonical | identical to canonical | canonical + memo/involved-count, **no** `setNullFieldsCount` | identical to canonical + order string |
| Ordering of null rows | dataset order | `sort(NullValueComparator)` = nullCount **desc.** | `sort(TimesInvolvedComparator)` = involvedInLHSCount **asc.** | identity permutation, then neighbourhood search over adjacent swaps |
| Execution | `treatNullTuple(t, t.getIndex())` | same | same | same, per candidate, from a restored state |
| State after return | `dataset` filled | `dataset` filled | `dataset` filled | `dataset` **rolled back**; filled copy returned |
| Return | `void` | `void` | `void` | `ObjectArrayList` |
| `#402` value | field | field | field | local `slot10` (baseline) |

---

## 9. Explicit ambiguities / limits of the evidence

* **A1 (decisive, not ambiguous).** `getNewGenerations` accepts only `gain < 0` (pc 101) and then requires
  `bestGain > 0` to store it (pc 320): the single `Map.put` (pc 378) is unreachable, so the method always returns
  an empty map and `localSearchExecution`'s whole generation/tracing block degrades to the baseline run. Which
  line was mis-typed cannot be *proven* from the bytecode; the two candidate repairs are discussed in §4, where
  inverting the final gate (pc 320) is the semantically coherent one. This is the single most important finding
  of this reconstruction.
* **A2.** The `#503` string is one constant that contains both
  `'Nessuna nuova generazione creata da analizzare\nElenco delle generazioni trattate'` and is emitted
  unconditionally after the worklist loop (pc 739) — it is *not* an else-branch, so it does not by itself prove
  that no child was generated at runtime (though per A1 that is in fact always the case).
* **A3.** Whether a `scores.put` during the worklist loop would have been observed by the same iterator cannot be
  settled from `FillingAlgorithm` alone. The iterator in use is
  `Object2DoubleLinkedOpenHashMap$EntryIterator` → `MapIterator`, which walks the insertion-ordered `link` chain
  (`MapIterator.nextEntry` reads `this$0.link[curr]` at pcs 28-37 to advance; `object2DoubleEntrySet().iterator()`
  constructs `EntryIterator`; `MapEntrySet.comparator()` returns `null`), and `MapIterator.hasNext/nextEntry`
  contain **no modification-count check** (`modCount` is never referenced), i.e. no fail-fast
  `ConcurrentModificationException`; a newly appended entry would therefore be reached later by the same
  iterator. This is moot given A1; read as an inference, the intended structure was a growing worklist
  (breadth-first over generations) rather than a single pass over a frozen set.
* **A4.** Sort stability for §6/§7 rests on `invokevirtual ObjectArrayList.sort(Comparator)` resolving to the
  Java-8 default `List.sort` (no `sort` declared anywhere in the fastutil `ObjectArrayList`/`AbstractObjectList`/
  `AbstractObjectCollection`/`ObjectList` hierarchy; class-file major 52). The resulting
  `Arrays.sort(Object[], Comparator)` is documented stable; tie behaviour is therefore dataset order. If the
  runtime were a pre-8 JDK this call could not link at all, so the inference is safe.
* **A5.** `calculateGainInSwap`'s two terms are *coverage proxies*, not realised imputations: they never call
  `treatNullTuple`, never check thresholds and never distinguish key RFDs from non-key RFDs (all RFDs of
  `rfdForRHS` are counted, and `rfdForRHS`'s keys are the RHS columns — bucket thresholds are ignored by the
  iteration `Map.values()`).
* **A6.** `cloneMap` is shallow, so `localSearchExecution`'s "restore" of `rfdForRHS`
  (pcs 359-366 / 678-685) restores only the map's structure: the shared `ArrayList<RFD>` buckets and `RFD`
  objects mutated by `revaluateKeyRFDs`/`updatePattern` during a candidate's execution are *not* rolled back.
  The bytecode shows the intent (snapshot/revert) but the snapshot is not a deep copy; the local search would
  therefore not be a clean restart for the rule state, only for the dataset tuples (`cloneList` is deep at
  `Tuple` level).
* **A7.** The parameter name and role of `getNewGenerations`' second list can only be inferred: it is *read* by
  `ObjectArrayList.contains` (pc 282) and *written* by `ObjectArrayList.add` (pc 296) → a dedup/seen-set. Its
  only caller passes `localSearchExecution`'s `slot8`, which is created at pc 268-275 and seeded with the parent
  order at pc 277-283.
* **A8.** `Object2DoubleMap$Entry` is used only through `getKey()` here; the print in `localSearchExecution`
  (pc 456) and in the final listing (pc 806) additionally reads `getDoubleValue()`, which is always the
  `(double) notFilledCells` score written at pc 375 — i.e. the "score" is a *number of unfilled cells*
  (`treatNullTuple` adds 1 per tuple when a single-null tuple fails, pcs 175-182, and adds the number of
  still-missing fields for multi-null tuples, pcs 863-873), lower is better — but it is never compared.
