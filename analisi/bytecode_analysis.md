# RENUVER — bytecode-level reconstruction of the imputation core

Target: `RENUVER_EDBT.jar` (research prototype, EDBT). Package = default package.
Method: static analysis of the extracted class files (today in `analisi/classi/`) with a minimal
JVM disassembler (`jvmdis.py`, plus `absbr_ex.py` which also dumps the `Code` exception table,
`LineNumberTable`, `LocalVariableTable` and resolves branch targets to absolute `pc`).

> **Riproduzione.** Le classi analizzate sono in `analisi/classi/`: sono l'estrazione delle 13 classi
> applicative dell'archivio, rigenerabile con `python3 analisi/estrai_classi.py` (l'archivio non viene
> modificato: lo script stampa l'impronta MD5 prima e dopo). Gli strumenti citati stanno in
> `analisi/strumenti/`, per esempio
> `python3 analisi/strumenti/jvmdis.py analisi/classi/FillingAlgorithm.class` e
> `python3 analisi/strumenti/absbr_ex.py analisi/classi/FillingAlgorithm.class`.

**The JAR was not executed.** The analysed classes are MD5-identical to the members of
`RENUVER/RENUVER_EDBT.jar`; class-file major version 52 (Java 8); `SourceFile`,
`LocalVariableTable` and `LineNumberTable` attributes are retained and are used below as primary
evidence for the original source shape.

Evidence convention: `pc` = bytecode offset inside the named method; `#N` = constant-pool index as
printed by the disassembler; local-variable names in `code font` are the **real names recovered from
the `LocalVariableTable`**. `cp#N` denotes a raw constant-pool entry verified directly against the
constant pool (e.g. `cp#824 Double 2147483647.0`).

---

## 1. Invocation and control flow

### 1.1 `Main.main(String[])`

```
  4: aload_0 ; arraylength ; bipush 6 ; if_icmpeq -> 23        // exactly 6 args
 11: System.out.println(#31)                                   // USAGE block
 19: System.exit(0)
 23: results          = new PrintWriter(user.dir/Results/output_<args1>_<args4>H<args5>.txt)
104: log              = new PrintWriter(user.dir/Logs/log_<args1>_<args4>H<args5>.txt)
185: populatedDataset = new PrintWriter(user.dir/Populated/output_<args1>_<args4>H<args5>.csv)
267: columnTypes = args[0].split(",")                          // ldc #94 ","
277: fa = new FillingAlgorithm(args[1], args[2], args[3], ";", "?", columnTypes,
                              Integer.parseInt(args[4]), results, log, populatedDataset)
311: fa.start(Integer.parseInt(args[5]))
322: (sum MemoryPoolMXBean peak usage) / 1048576  -> log.println("Memory Consumption: <n>MB")
411: results.close(); log.close(); populatedDataset.close()
```

The usage string (`cp#31`) is:
`"USAGE:\nColumn type comma separated - Dataset filename - split char of dataset's file - rfd filename - boolean equality threshold - Heuristics value\n(All parameter should be separated by a space"`.

So the CLI contract is: `args[0]` = comma-separated column types, `args[1]` = dataset CSV name
(resolved under `Dataset/`), `args[2]` = **dataset** field separator, `args[3]` = RFD CSV name
(resolved under `RFD/`), `args[4]` = `booleanEqualityThreshold` (int), `args[5]` = heuristic selector.
The **RFD separator is hard-coded `";"` and the null marker hard-coded `"?"`** (both passed as
literals at pc 290/292). There is no exit code on success.

### 1.2 `FillingAlgorithm` constructor

`<init>(String datasetPath, String splitChar, String rfdPath, String rfdSplitChar, String rfdNullChar,
String[] columnTypes, int booleanEqualityThreshold, PrintWriter results, PrintWriter log,
PrintWriter populatedDataset)` — parameter names from the `LocalVariableTable`; declares
`throws FileNotFoundException` (constant-pool `Exceptions` attribute `#40`).

| pc | action | field |
|----|--------|-------|
| 4–11 | `nullCells = 0` | `#47` |
| 14–17 | `notFilledCells = 0` | `#49` |
| 20–23 | `booleanEqualityThreshold = arg7` | `#51` |
| 25–28 | `rfdFilePath = arg3` | `#53` |
| 30–33 | `datasetFilePath = arg1` | `#55` |
| 36–44 | `rfdFieldsName = new ObjectArrayList<>()` | `#60` |
| 47–53 | `columnTypes = arg6` (**stored by reference, not copied**) | `#62` |
| 55–58 | `allRfd = getRFDsFromFile(arg4, arg5, arg6)` | `#68` |
| 63–68 | `dataset = getDatasetFromFile(arg1, arg2)` | `#74` |
| 71–79 | `rfdForRHS = new Object2ObjectLinkedOpenHashMap<>()` | `#79` |
| 82–88 | `tupleWithNullValue = new Int2ObjectLinkedOpenHashMap<>()` | `#84` |
| 91–96 | `similarityPatterns = new Object2ObjectLinkedOpenHashMap<>()` | `#86` |
| 104–112 | `keyRFDs = new ArrayList<>()` | `#91` |
| 115–130 | `populatedDataset`, `results`, `log` | `#93/#95/#97` |
| 133–186 | `System.out.println("#Tuple: " + dataset.size())`, then `"#RFD: " + allRfd.size()` | `#107`, `#129` |

### 1.3 `start(int heuristic)`

```
  0: System.currentTimeMillis() -> inizioMappaRFD (local long)
  8: log.println("Removing key RFD...")                                   // #272
 14: for (Iterator i = allRfd.iterator(); i.hasNext();) {
 38:     if (rfd.getRHS().getThreshold() != 0.0) continue;                // dconst_0; dcmpl; ifne
 51:     if (isKeyRfd(rfd) != 0) continue;                                 // ifne
 60:     keyRFDs.add(rfd);
 70:     i.remove();
     }
 95: log.println("#RFD after remove: " + allRfd.size())                   // #305
129: createMapOnRHS();
133: log.println("Time required for pre processing: " + (now - inizio) + "ms")   // #310, #315
155: sequentialExecution();
159: saveOutputFile();
```

**The `heuristic` parameter is never read**: there is no `iload_1`/`iload slot 1` anywhere in the
method (pc 0–163), and pc 155 is an unconditional `invokespecial sequentialExecution`.
`localSearchExecution()`, `nullValueBasedOrderExecution()` and
`timesInvolvedInLHSBasedOrderExecution()` have **no call site anywhere in the JAR**, and no reflection
is used (`Class.forName`/`getMethod`/`invoke` appear nowhere), so the heuristic selector is dead in
this build. The bundled `RENUVER/README.txt` confirms this from the authors' side: *"In this release,
only the sequential heuristic 0 is supported"* — and the shipped sample output
`Results/output_bridges_14_1.csv_3H4.txt` shows `H4`, i.e. a heuristic argument that was ignored.

---

## 2. Pre-processing and key-RFD removal

### 2.1 The key predicate: `isKeyRfd(RFD) : int`

Locals (from the `LocalVariableTable`): `verifiedTuples` (2), `x` (3), `y` (4), `thresholdPassed` (5),
`lhs` (6), `tuple1Field` (8), `tuple2Field` (9), `t1/t2` (10/11), `e` (10), `distance` (11).
Exception table: `try [125,267) catch RuntimeException @270`, `try [421,458) catch RuntimeException @460`.

```java
verifiedTuples = 0;                                          // pc 0-3
for (x = 0; x < dataset.size(); x++) {                       // pc 4 -> cond pc 529/537
    for (y = x + 1; y < dataset.size(); y++) {               // pc 7/12 -> cond pc 514/523
        thresholdPassed = 0;                                 // pc 15-16
        for (Column lhs : rfd.getLHS()) {                    // pc 18/27 -> cond pc 312/319
            Field tuple1Field = dataset.get(x).getFields().get(lhs.getIndex());   // pc 42-67
            Field tuple2Field = dataset.get(y).getFields().get(lhs.getIndex());   // pc 69-95
            if (!tuple1Field.getValue().equals("?") && !tuple2Field.getValue().equals("?")) {
                if (lhs.getType().equals("B")) {                                  // pc 125-136
                    if (lhs.getThreshold() == (double) booleanEqualityThreshold) { // pc 139-150
                        if (tuple1Field.getValue().equals(tuple2Field.getValue()))
                            thresholdPassed++;                                    // pc 169
                    }
                } else if (lhs.getType().equals("C")) {                           // pc 175-186
                    char t1 = tuple1Field.getValue().charAt(0);                   // pc 189-198
                    char t2 = tuple2Field.getValue().charAt(0);                   // pc 200-209
                    if (Math.abs(t1 - t2) <= lhs.getThreshold()) thresholdPassed++;// pc 211-226
                } else {
                    try {                                                         // try [125,267)
                        if (Math.abs(Double.parseDouble(tuple1Field.getValue())
                                   - Double.parseDouble(tuple2Field.getValue()))
                                <= lhs.getThreshold())
                            thresholdPassed++;                                    // pc 235-261
                    } catch (RuntimeException e) {
                        distance = LevensteinDistance.levenshtein3(
                                       tuple1Field.getValue(), tuple2Field.getValue(),
                                       lhs.getThreshold());                       // pc 272-290
                        if (distance >= 0 && (double) distance <= lhs.getThreshold())
                            thresholdPassed++;                                    // pc 292-306
                    }
                }
            }
        }
        if (thresholdPassed == rfd.getLHS().size()) {                             // pc 322-331
            Field tuple1Field = dataset.get(x).getFields().get(rfd.getRHS().getIndex());  // pc 334-361
            Field tuple2Field = dataset.get(y).getFields().get(rfd.getRHS().getIndex());  // pc 363-391
            if (!tuple1Field.getValue().equals("?") && !tuple2Field.getValue().equals("?")) {
                try {
                    if (Math.abs(parseDouble(t1) - parseDouble(t2))
                            > rfd.getRHS().getThreshold())
                        return -1;                                            // pc 449 ifgt -> 458
                    verifiedTuples++;                                         // pc 452
                } catch (RuntimeException e) {
                    distance = LevensteinDistance.levenshtein3(v1, v2,
                                   rfd.getRHS().getThreshold());              // pc 462-482
                    if (distance <= 0) return -1;                             // pc 486 ifle -> 509
                    if ((double) distance > rfd.getRHS().getThreshold())
                        return -1;                                            // pc 500 ifgt -> 509
                    verifiedTuples++;                                         // pc 503
                }
            }
        }
    }
}
return verifiedTuples;                                                    // pc 540
```

Non-obvious claims and their evidence:

* **`B` binding requires threshold equality.** `pc 139: Column.getThreshold(); getfield #51
  booleanEqualityThreshold; i2d; dcmpl; ifne -> 175` — a `B` column whose threshold differs from
  `booleanEqualityThreshold` falls through to the `C` test (false) and then into the **numeric**
  branch (where `parseDouble("M")` throws and the Levenshtein fallback runs).
* **`C` distance is the raw UTF-16 code-unit difference of the first character only.**
  `pc 211-226: iload t1; iload t2; isub; Math.abs(I)I; i2d; getThreshold(); dcmpg; ifgt -> 312`.
  `charAt(0)` on an empty string throws `StringIndexOutOfBoundsException`.
* **The try ranges cover the whole type-dispatch block, not just `parseDouble`**
  (`try [125,267)` starts *at the `"B"` comparison*), so a `StringIndexOutOfBoundsException` from
  `charAt(0)` also lands in the Levenshtein fallback.
* **`iflt` vs `ifle` asymmetry.** The LHS fallback uses `iflt` (pc 294, `distance < 0 → skip`),
  the RHS fallback uses `ifle` (pc 486, `distance <= 0 → return -1`). Since
  `levenshtein3` **never returns a negative value** (§6.2) the `iflt` guards are dead, and the RHS
  `ifle` really means "`distance == 0`" — i.e. an exactly equal RHS *string* after a failed
  `parseDouble` returns `-1`, whereas the numeric sibling path counts equality as agreement.
* **The `-1` returns exit the entire method**, not just the inner loop (`iconst_m1; ireturn` at
  pc 458-459 and pc 509-510).

**Semantics of the return value.** The only caller tests `!= 0` (`start` pc 57 `ifne`). Therefore:

* `0` ⟺ no ordered pair `(x,y)`, `x<y`, reaches `thresholdPassed == rfd.getLHS().size()` ⟺ no two
  distinct tuples agree on *all* LHS columns (a pair never "agrees" on a column where either side is
  `"?"`) ⟺ the LHS behaves like a key ⟹ **classified as a key RFD**.
* `> 0` ⟹ at least one LHS-agreeing pair exists and every such pair also agreed on the RHS.
* `-1` ⟹ some LHS-agreeing pair disagreed on the RHS.

Consequently **the entire RHS half of `isKeyRfd` is behaviourally inert in this release** (`-1` and
`> 0` are both "not a key"); it only costs time and can short-circuit earlier. Note also that `start`
restricts the key test to RFDs with **RHS threshold exactly `0.0`** (`pc 46 dconst_0; dcmpl; ifne`).

### 2.2 `getRFDsFromFile(String splitChar, String nullChar, String[] columnTypes) : ArrayList<RFD>`

```java
ArrayList<RFD> rfdsFound = new ArrayList<>();                                   // pc 0-7
String path = user.dir + File.separator + "NoKeyRFD" + File.separator + rfdFilePath;   // pc 9-51
System.out.println("Searching if NoKeyRFD file actually exists into: " + path);       // pc 53-73 (#222)
path = user.dir + File.separator + "RFD" + File.separator + rfdFilePath;               // pc 76-118  ← UNCONDITIONAL
File f = new File(path);                                                               // pc 120-129
System.out.println("Searching if RFD file eventually exists into: " + path + " then");// pc 131-153 (#226,#228)
Scanner in = new Scanner(f);                                                           // pc 159-168
boolean firstLine = true;                                                              // pc 170-171
while (in.hasNextLine()) {                                                             // pc 173 -> 413/418
    String line = in.nextLine();
    String[] fields = line.split(splitChar);
    double rhsThreshold = 0.0;
    ArrayList<Column> lhsList = new ArrayList<>();
    if (firstLine) {
        for (String string : fields) rfdFieldsName.add(string);                        // header -> instance field
        firstLine = false;
    } else {
        String rhsName = fields[0];
        int rhsIndex = 0;
        for (int i = 1; i < fields.length; i++) {
            if (rfdFieldsName.get(i).equals(fields[0])) {          // i is the RHS column position
                rhsThreshold = Double.parseDouble(fields[i]);
                rhsIndex = i - 1;                                  // 0-based column index
                /* and the LHS add is skipped: goto i++ */
            } else if (!fields[i].equals(nullChar)) {              // "?" => column NOT in the LHS
                lhsList.add(new Column(rfdFieldsName.get(i),
                                       Double.parseDouble(fields[i]),
                                       i - 1,
                                       columnTypes[i - 1]));
            }
        }
        Column rhsEl = new Column(rhsName, rhsThreshold, rhsIndex, columnTypes[rhsIndex]);
        rfdsFound.add(new RFD(lhsList, rhsEl));
    }
}
in.close(); return rfdsFound;
```

* **Header handling.** The first physical line is the header: its tokens are appended to the instance
  field `rfdFieldsName` (`ObjectArrayList<String>`, `#60`) and no RFD is produced from it.
* **CSV shape** (one line per RFD): `fields[0]` = the RHS column *name*; for `i ≥ 1`, `fields[i]` is
  either the literal `nullChar` (`"?"`, hard-coded in `Main`) meaning "this column is **not** part of
  the LHS", or a `double` threshold meaning "this column is in the LHS with that threshold".
  The column that gives the RFD its name also carries the **RHS threshold** and is never added to the
  LHS.
* `new Column(name, threshold, index, type)` — verified in `Column.<init>(String,D,I,String)`:
  `name→#18`, `threshold→#20`, `index→#22`, `type→#24`; `index` is the **0-based dataset column
  position** used everywhere as `tuple.getFields().get(column.getIndex())`.
* `Column.equals`/`hashCode` use **`name` only** (`equals` additionally does identity,
  `null` and `getClass()` checks; `hashCode` = `31 + name.hashCode()`), so threshold/index/type never
  participate in column identity.
* No validation: a missing file throws `FileNotFoundException` from `Scanner(File)` (declared by the
  constructor), a bad number throws `NumberFormatException`.

> **Correction to the brief.** The `NoKeyRFD/<rfdFileName>` path is computed and printed but **never
> used**: pc 76–118 unconditionally overwrites local 5 with the `RFD/<rfdFileName>` path before
> `new File(slot 5)` at pc 120. There is **no branch instruction anywhere in pc 0–172** (the first
> branch in the method is the `goto` at pc 173), and there is **no `File.exists()` call anywhere in
> the class**. Moreover `createNewRFDFile()` — the method that writes `NoKeyRFD/<rfdFileName>` — has
> **no call site at all** (its name occurs exactly once in the whole disassembly, in its own method
> header). Both the writer and the reader of `NoKeyRFD/` are therefore dead code in this release; the
> established fact "the program uses `NoKeyRFD/<file>` when present" does **not** hold for these
> class files.

### 2.3 `getDatasetFromFile(String csvPath, String splitChar) : ObjectArrayList<Tuple>`

Reads `user.dir/Dataset/<csvPath>`; the header line becomes `fieldsName`; each data line becomes
`tupleFields[i] = new Field(fieldsName[i], fields[i])` and then
`dataset.add(new Tuple(tupleFields, row, index))` with the arguments pushed **before** the
post-increments (`pc 198 iload row; pc 200 iinc row; pc 203 iload index; pc 205 iinc index`),
`row` starting at 1 and `index` at 0. Hence `Tuple.row` = 1-based data-row ordinal,
`Tuple.index` = 0-based position in `dataset` (for well-formed input `row == index + 1`).

There is **no** `"?"`-detection here: the missing marker is simply the literal string `"?"` stored as
the `Field.value`, and `Tuple.nullFields`/`nullFieldsCount` stay `null`/`0` until a heuristic scans
for it. The loop bound is the *row's* field count, so a row longer than the header throws
`ArrayIndexOutOfBoundsException` on `fieldsName[i]`.

### 2.4 `createMapOnRHS()`

```java
for (Tuple tuple : dataset)                                    // pc 0-20, cond pc 111
    for (Field f : tuple.getFields())                          // pc 21-43, cond pc 101
        if (f.getValue().equals("?"))                          // pc 44-54 (ifeq -> next field)
            if (!rfdForRHS.containsKey(f.getKey())) {          // pc 57-68 (ifne -> next field)
                Map rfdMap = findBestRFDs(f.getKey(), tuple);  // pc 71-80
                if (rfdMap != null) rfdForRHS.put(f.getKey(), rfdMap);   // pc 82-100
            }
```

A **lazy first-null-wins cache** keyed by column name: for every column that contains at least one
`"?"`, the RFD set is computed **once**, from the *first* tuple in dataset order that has a null in
that column, and cached for the rest of the run.

### 2.5 `findBestRFDs(String nullField, Tuple nullTuple) : Map`

```java
ArrayList<RFD> selectedRFDs = new ArrayList<>();                     // pc 0-7
for (RFD r : allRfd)                                                 // pc 8-61
    if (nullField.equals(r.getRHS().getName())) selectedRFDs.add(r); // pc 32-44
if (selectedRFDs.isEmpty()) return null;                             // pc 64-72
Object2ObjectLinkedOpenHashMap<Double, ArrayList<RFD>> rfdMap = new Object2ObjectLinkedOpenHashMap<>();
for (RFD rfd : selectedRFDs)                                         // pc 82-216
    rfdMap.computeIfAbsent-like: get-or-create ArrayList keyed by rfd.getRHS().getThreshold()
return rfdMap;                                                       // pc 219
```

**Ranking/filtering for a given null field: there is none.** All RFDs whose RHS *name* equals the
null column are kept and partitioned into **clusters keyed by their RHS threshold** (`Double`), in
order of first appearance in `allRfd`. That ordering matters downstream because `treatNullTuple`
indexes the clusters **positionally** (`new ArrayList<>(rfdForRHS.get(key).values()).get(i)`).
Since `start` removed the key RFDs from `allRfd` beforehand, key RFDs never enter `rfdForRHS` unless
`revaluateKeyRFDs` later inserts them (`§5.4`).

---

## 3. The scoring function (`calculatePattern` / `getDigits`)

### 3.1 `getDigits(double number) : int`

Source lines 1872–1882; locals `number` (1), `s` (3), `digits` (4).

```java
private int getDigits(double number) {
    String s = String.valueOf(number);                                       // pc 0-4
    int digits = 0;                                                          // pc 5-6
    if (s.contains("E"))                                                     // pc 8-15  (ldc_w #918 "E")
        digits = Integer.parseInt(s.substring(s.indexOf("-") + 1));          // pc 18-34 (ldc_w #813 "-")
    else
        digits = s.substring(s.indexOf(".")).length() - 1;                   // pc 39-55 (ldc_w #694 ".")
    return digits;                                                           // pc 57-59
}
```

* Scientific-notation branch: it searches for the **first `'-'`**, *not* for the `'E'`, and parses the
  remainder as an int. `1.0E-4 → indexOf("-")=4 → "4" → 4`. A negative number (`-1.0E-4`) gives
  `indexOf("-")=0 → "1.0E-4"` → `NumberFormatException`; a positive exponent (`1.0E10`) has no `'-'`
  (`indexOf = -1 → substring(0)`) → `NumberFormatException`.
* Plain branch: counts the characters after the decimal point, *including* the leading `.`:
  `0.05 → ".05" → 2`, `0.5 → ".5" → 1`, `0.01 → 2`, `0.30000000000000004 → 16`.
* The value means "number of digits after the decimal point" = the exponent of the value's last
  decimal place. It is called from exactly **one** place: `getCandidatesForField` pc 458, on an LHS
  `Column` threshold.
* `getCandidatesForField` has **no exception table**, so a `NumberFormatException` from
  `getDigits` propagates and aborts the run.

### 3.2 `calculatePattern(Tuple nullTuple, Tuple tuple, ArrayList tuplesRowWNegativePatternValue) : Double[]`

Parameter names from the `LocalVariableTable`: `nullTuple` (1), `tuple` (2),
`tuplesRowWNegativePatternValue` (3); locals `pattern` (4, `Double[]`), `i` (5), `tuple1Field` (6),
`tuple2Field` (7), `t1/t2` (8/9 `char`), `e` (8 `RuntimeException`), `distance` (9 `int`).
Source lines 1774–1830. Exception table: **`try [142,291) catch java/lang/RuntimeException @294`**.

```java
Double[] pattern = new Double[nullTuple.getFields().size()];        // pc 0-10   size from ARG 1
for (int i = 0; i < tuple.getFields().size(); i++) {                // pc 12-15 / 333-342  bound from ARG 2
    Field tuple1Field = nullTuple.getFields().get(i);               // pc 18-30
    Field tuple2Field = tuple.getFields().get(i);                   // pc 32-44

    if (tuple1Field.getValue().equals("?")) {                       // pc 46-57
        if (!tuple2Field.getValue().equals("?")) {                  // pc 60-71
            pattern[i] = -1.0;                                      // pc 74-84   (ldc2_w #826 = -1.0)
            tuplesRowWNegativePatternValue.add(tuple.getRow());     // pc 85-96   (Integer)
        }
        continue;                                                   // pc 97
    }
    if (tuple1Field.getValue().equals("?") || tuple2Field.getValue().equals("?")) {
        pattern[i] = -1.0;                                          // pc 128-138
        continue;                                                   // pc 139
    }
    /* both present: real distance */
    if (columnTypes[i] == "B") {                    // pc 142-152 : aaload; ldc_w #772 "B"; **if_acmpne**
        pattern[i] = tuple1Field.getValue().equals(tuple2Field.getValue())
                   ? (double) booleanEqualityThreshold              // pc 171-183
                   : (double) (booleanEqualityThreshold + 1);       // pc 187-201
    } else if (columnTypes[i].equals("C")) {        // pc 205-218 (proper String.equals)
        char t1 = tuple1Field.getValue().charAt(0);                 // pc 221-230
        char t2 = tuple2Field.getValue().charAt(0);                 // pc 232-241
        pattern[i] = (double) Math.abs(t1 - t2);                    // pc 243-259
    } else {
        try {                                                       // try [142,291)
            pattern[i] = Math.abs(Double.parseDouble(tuple1Field.getValue())
                                - Double.parseDouble(tuple2Field.getValue()));   // pc 263-290
        } catch (RuntimeException e) {
            int distance = LevensteinDistance.levenshtein3(tuple1Field.getValue(),
                                                           tuple2Field.getValue(),
                                                           2147483647.0);        // pc 296-312 (ldc2_w #824)
            if (distance >= 0) pattern[i] = (double) distance;                   // pc 314-329
        }
    }
}
return pattern;                                                              // pc 345-347
```

Decoded constants: `#826` = raw long `-4616189618054758400` = `0xBFF0000000000000` = **`-1.0`**;
`#824` = raw long `4746794007244308480` = `0x41DFFFFFFFC00000` = **`2147483647.0`** (`Integer.MAX_VALUE`
widened); `#828` (used in §3.3) = `4621819117588971520` = `0x4024000000000000` = **`10.0`**;
`#772 = "B"`, `#774 = "C"`, `#382 = "?"`.

**The two null branches are semantically identical** (`pattern[i] = -1.0`) but only the first one
records a row:

> `tuplesRowWNegativePatternValue` receives the **1-based row number of `tuple` for every column in
> which `nullTuple` is `"?"` and `tuple` has a value** — exactly the rows that could fill one of
> `nullTuple`'s holes. `-1.0` is a pure sentinel meaning "no distance computable".

**Column-type dispatch — an authoring bug.** The `"B"` test is `if_acmpne`, a **reference comparison**
of the `String` in `columnTypes[i]` against the interned literal `"B"`, whereas the sibling `"C"` test
on the very next branch uses `String.equals` (pc 215). Since `columnTypes` is `args[0].split(",")`,
its elements are freshly allocated and never identical to the literal, so **the boolean branch of
`calculatePattern` is unreachable in practice**. The type dispatch in `isKeyRfd`,
`areThereTuplesViolatingRFD`, `revaluateKeyRFDs` and the scoring loop of `getCandidatesForField` all
use proper `equals`, so only the *pattern* path degenerates (a `B` column falls into the numeric
branch, `parseDouble("M")` throws, and the Levenshtein distance of the two category labels is used).

**Units of the returned `Double[]`.** One entry per column, positionally aligned with the field lists:

| case | value | unit |
|------|-------|------|
| either side is `"?"` | `-1.0` | sentinel (no distance) |
| `'B'` (dead branch) | `booleanEqualityThreshold` if the strings are equal, else `booleanEqualityThreshold + 1` | surrogate distance |
| `'C'` | `|c1 - c2|` | difference of the Unicode code units of the **first character** |
| numeric, parseable | `|v1 - v2|` | raw absolute difference of the parsed doubles |
| numeric, unparseable | ordinary Levenshtein edit distance of the two raw strings | character edits |

So `calculatePattern` is an *un-normalised, symmetric, per-column distance vector*, **not** a score.
Normalisation happens in `getCandidatesForField`.

### 3.3 Normalisation by threshold and `Math.pow`

Inside `getCandidatesForField` the raw entry `patternValue = pattern[lhs.getIndex()].doubleValue()`
(pc 269-280) is turned into a per-RFD contribution:

```java
if (lhs.getType().equals("B")) {                                        // pc 282-293
    if (lhs.getThreshold() == (double) booleanEqualityThreshold) {       // pc 296-307
        if (patternValue == (double) booleanEqualityThreshold) {         // pc 310-318
            thresholdPassed++;  tupleSimilarityValue += 0.0;             // pc 321-330
        } else {
            tupleSimilarityValue += 2147483647.0;                        // pc 333-341 (ldc2_w #824)
        }
    }
} else if (lhs.getType().equals("C")) {                                 // pc 344-355
    if (patternValue <= lhs.getThreshold()) {                           // pc 358-366
        thresholdPassed++;
        tupleSimilarityValue += patternValue;                           // pc 372-379
    }
} else {
    if (patternValue == -1.0) break;                                    // pc 382-391 (ldc2_w #826) → pc 527
    if (patternValue <= lhs.getThreshold()) {                           // pc 394-402
        thresholdPassed++;
        if (lhs.getThreshold() == 0.0) {                                // pc 408-415
            tupleSimilarityValue += 0.0;                                // pc 418-422
        } else if (lhs.getThreshold() > 0.0 && lhs.getThreshold() < 1.0) {   // pc 433-444
            Double value = patternValue
                         * Math.pow(10.0, (double) getDigits(lhs.getThreshold()));   // pc 447-469
            tupleSimilarityValue += value.doubleValue();                // pc 471-479
        } else {
            double value = patternValue
                         / Math.pow(10.0,
                                    (double)(String.valueOf((int) lhs.getThreshold()).length() - 1));  // pc 484-508
            tupleSimilarityValue += value;                              // pc 510-515
        }
    }
}
```

Evidence: `#828 = 10.0`; both `Math.pow` call sites are
`invokestatic #834 // java/lang/Math.pow.(DD)D` at **pc 462** and **pc 504**; the sub-unit branch's
test is the pair `dcmpl(threshold, 0.0); ifle` (pc 433-434) and `dcmpg(threshold, 1.0); ifge`
(pc 443-444); the integer floor in the `>= 1` branch is `d2i` (pc 494) followed by
`String.valueOf(int).length() - 1` (pc 495-503).

After the LHS loop: `tupleSimilarityValue = tupleSimilarityValue / (double) rfd.getLHS().size()`
(pc 751-763).

**Effective formula.** For a candidate tuple `t` and an RFD `rfd`, with `d_c` the `calculatePattern`
entry of LHS column `c`:

```
sim(rfd, t) = ( 1 / |LHS(rfd)| ) * Σ_{c ∈ LHS(rfd)} w_c(d_c)

              ⎧ 0.0                                 if c is 'B' and d_c == booleanEqualityThreshold
              ⎪ 2147483647.0                        if c is 'B' and d_c != booleanEqualityThreshold
    w_c(d_c) = ⎨ d_c                                 if c is 'C'          and d_c <= thr_c
              ⎪ d_c * 10^getDigits(thr_c)           if numeric, 0 < thr_c < 1
              ⎪ d_c / 10^(len(str((int) thr_c))-1)  if numeric, thr_c >= 1
              ⎩ 0.0                                 if numeric, thr_c == 0
```

and a column counts towards `thresholdPassed` only when its condition holds; `d_c == -1.0` in the
numeric branch aborts the whole RFD (`break` out of the LHS loop, pc 391 `goto 527`), as does any
column whose distance exceeds its threshold (`ifgt -> 517`). Only if
`thresholdPassed == rfd.getLHS().size()` (pc 537) is the RFD considered at all.

**Interpretation of the normalisation.** For `thr >= 1` the difference is divided by the order of
magnitude of the threshold (`thr = 10 → /10`, `thr = 100 → /100`, `thr = 5 → /1`). For `0 < thr < 1` it
is *multiplied* by the inverse of the threshold's last decimal place (`thr = 0.05 → ×100`,
`thr = 0.5 → ×10`), i.e. the difference is expressed in units of the threshold's resolution. The two
branches are arithmetically "divide by the threshold's granularity", but the sub-unit branch makes
fine-grained columns contribute values many orders of magnitude larger than the bound they are
compared against (see §9.7).

**Units of the score.** `sim` is a **dimensionless average over LHS columns of a threshold-normalised
absolute distance**. It is *not* in `[0,1]` and is *not* a similarity: **0 is best**. It is compared
against `minTupleSimilarityValue`, which is initialised from the raw integer `booleanEqualityThreshold`
(`getCandidatesForField` pc 74-79: `getfield #51; i2d; dstore 7`). The comparison is strict:
`pc 765-770 dcmpg; ifge -> skip`, i.e. `if (tupleSimilarityValue < minTupleSimilarityValue)`.

---

## 4. Candidate search and acceptance

### 4.1 `getCandidatesForField(Tuple nullTuple, ArrayList<RFD> selectedRFDs) : ObjectArrayList<SimilarityTuple>`

Locals: `tupleWithSimilarity` (3), `tuplesRowWNegativePatternValue` (4), `x` (5), `tuple` (6),
`minTupleSimilarityValue` (7 `double`), `fieldIndex` (9), `atLeastOneFound` (10), `minrfd` (11),
`tupleRowPair` (12), `pattern` (13 `Double[]`), `tupleRowPairInv` (14), `rfd` (14),
`thresholdPassed` (16), `tupleSimilarityValue` (17), `lhs` (19), `patternValue` (21), `value` (23),
`temp` (19/5). Source lines 1130–1349. **No exception table in this method.**

```java
ObjectArrayList<SimilarityTuple> tupleWithSimilarity = new ObjectArrayList<>();      // pc 0-7
ArrayList<Integer> tuplesRowWNegativePatternValue = new ArrayList<>();               // pc 8-15
for (int x = 0; x < dataset.size(); x++) {                                          // pc 17-20 -> cond 845
    Tuple tuple = dataset.get(x);
    if (tuple.getFields().get(selectedRFDs.get(0).getRHS().getIndex())
             .getValue().equals("?")) continue;                                     // pc 37-71
    double minTupleSimilarityValue = (double) booleanEqualityThreshold;              // pc 74-79
    int fieldIndex = 0; boolean atLeastOneFound = false; RFD minrfd = null;          // pc 81-88
    String tupleRowPair = nullTuple.getRow() + "-" + tuple.getRow();                 // pc 90-121
    Double[] pattern = similarityPatterns.get(tupleRowPair);                         // pc 123-135
    if (pattern == null) {
        String tupleRowPairInv = tuple.getRow() + "-" + nullTuple.getRow();          // pc 142-173
        pattern = similarityPatterns.get(tupleRowPairInv);                           // symmetric lookup
        if (pattern == null) {
            pattern = calculatePattern(nullTuple, tuple, tuplesRowWNegativePatternValue);  // pc 194-203
            similarityPatterns.put(tupleRowPair, pattern);                           // pc 205-216
        }
    }
    for (RFD rfd : selectedRFDs) {                                                   // pc 217-223 -> cond 801
        int thresholdPassed = 0; double tupleSimilarityValue = 0.0;                   // pc 238-242
        for (Column lhs : rfd.getLHS()) { /* §3.3 */ }                                // pc 244 -> cond 524
        if (thresholdPassed != rfd.getLHS().size()) continue;                         // pc 527-537
        if (nullTuple.getNullFieldsCount() == 1 && rfd.getRHS().getThreshold() == 0.0) {   // pc 540-558
            nullTuple.getFields().set(rfd.getRHS().getIndex(),
                                      tuple.getFields().get(rfd.getRHS().getIndex()));     // pc 561-595
            results.println(nullTuple.getRow() + ";"
                            + nullTuple.getFields().get(rfd.getRHS().getIndex()) + ";"
                            + tuple + ";" + rfd + "; exact");                             // pc 596-669 (#841)
            merge tuplesRowWNegativePatternValue into tupleWithNullValue[nullTuple.getRow()];  // pc 672-740
            updatePattern(nullTuple.getRow());                                        // pc 741-746
            return null;                                                              // pc 749-750
        }
        tupleSimilarityValue = tupleSimilarityValue / (double) rfd.getLHS().size();   // pc 751-763
        if (tupleSimilarityValue < minTupleSimilarityValue) {                          // pc 765-770
            minTupleSimilarityValue = tupleSimilarityValue;
            fieldIndex = rfd.getRHS().getIndex();
            atLeastOneFound = true;
            minrfd = rfd;
        }
    }
    if (atLeastOneFound)                                                              // pc 804-806
        tupleWithSimilarity.add(new SimilarityTuple(tuple.getFields(),
                                                    minTupleSimilarityValue,
                                                    fieldIndex,
                                                    tuple.getRow(),
                                                    minrfd,
                                                    tuple.getIndex()));               // pc 809-838
}
merge tuplesRowWNegativePatternValue into tupleWithNullValue[nullTuple.getRow()];      // pc 857-925
return tupleWithSimilarity;                                                           // pc 926
```

Key facts:

* **Which tuples are candidates.** Any dataset tuple `x` whose value in the RHS column of
  `selectedRFDs.get(0)` is *not* `"?"`. `selectedRFDs.get(0)` is used only for that column index; all
  RFDs in one call come from one RHS-threshold cluster and share the same RHS column name.
* **Pattern cache.** `similarityPatterns` is keyed `"<nullTupleRow>-<tupleRow>"` with a symmetric
  fallback lookup `"<tupleRow>-<nullTupleRow>"`; the entry is stored under the *first* key only.
  `updatePattern` writes under the same convention.
* **Per-candidate best RFD, and the only filter.** For each candidate tuple the method scans **all**
  RFDs of the cluster, keeps the one with the strictly smallest mean normalised distance, and
  accepts it only if that mean is strictly below `(double) booleanEqualityThreshold` (the CLI
  `maxthr`), re-initialised for every candidate. If no RFD beats that bound, **no `SimilarityTuple`
  is produced for that candidate at all**.
* **One `SimilarityTuple` per surviving candidate row**, in dataset order (the returned list is
  *unsorted*).
* **Exact-match short circuit.** When the tuple has exactly **one** null field **and** the RFD's RHS
  threshold is **`0.0`**, the imputation is applied *inside* `getCandidatesForField`: the null tuple's
  field is overwritten with the candidate's `Field` object, a line
  `row;field;tuple;rfd; exact` goes to the `results` writer (marker `; exact`), the
  `tupleWithNullValue` bookkeeping is merged, `updatePattern` runs, and the method **returns `null`**.
  **`null` is therefore a reserved return value** meaning "already imputed exactly", never "nothing
  found". It is what makes `treatNullTuple` take its `candidates == null` branch (commit +
  `revaluateKeyRFDs` + `filled = true`).
* `tupleSimilarityValue` for a failing `'B'` column is `2147483647.0`, so such a candidate can never
  beat any sane `maxthr` — the boolean branch is a hard filter.
* Latent hazards: `pattern[lhs.getIndex()].doubleValue()` would NPE if a slot were left `null`
  (impossible with the current `levenshtein3`, see §9.11), and the array is sized from `nullTuple`
  while the loop bound comes from `tuple` (identical widths for well-formed input).

### 4.2 `populateFieldSingleAttribute(Tuple nullTuple, ObjectArrayList tupleWithSimilarity) : boolean`

Locals: `nullTuple` (1), `tupleWithSimilarity` (2), `tuple` (3, a `SimilarityTuple`),
`indexFieldToPopulate` (5). Source lines 1672–1706.

```java
for (SimilarityTuple tuple : tupleWithSimilarity) {                     // pc 0-4 -> cond 232
    if (!tuple.getCareAbout()) continue;                                // pc 20-24
    if (tuple.getFields().get(tuple.getFieldIndexSingleAttribute())
             .getValue().equals("?")) continue;                         // pc 27-50
    int indexFieldToPopulate = tuple.getFieldIndexSingleAttribute();     // pc 53-57
    nullTuple.getFields().set(indexFieldToPopulate,
                              tuple.getFields().get(indexFieldToPopulate));   // pc 59-80
    if (!isFaultless(tuple.getFields().get(indexFieldToPopulate),
                     tupleWithSimilarity, nullTuple)) {                  // pc 81-99
        nullTuple.getFields().set(indexFieldToPopulate,
            new Field(tuple.getFields().get(indexFieldToPopulate).getKey(), "?"));  // pc 190-221
        continue;
    }
    results.println(nullTuple.getRow() + ";"
                    + nullTuple.getFields().get(indexFieldToPopulate) + ";"
                    + tuple + ";" + tuple.getBased() + ";" + tuple.getSimilarityIndex());  // pc 102-177
    updatePattern(nullTuple.getRow());                                   // pc 180-182
    return true;                                                         // pc 188-189
}
return false;                                                            // pc 235-236
```

* The first `careAbout == true` candidate that (a) has a **non-`"?"` value** in the attribute to
  impute and (b) passes `isFaultless` wins. Iteration order is the list order; the multi-attribute
  path sorts that list ascending by `weightedSimilarity` first, the single-attribute path does not.
* The mutation is **by reference**: `nullTuple.getFields().set(idx, <the candidate's Field object>)`.
  Null tuple and candidate then share one `Field` instance.
* Failure restores a **fresh** `new Field(key, "?")` (not the original object) with the same key.
* Output format: `row;<Field.toString()>;<SimilarityTuple.toString()>;<RFD.toString()>;<similarityIndex>`.
  `Field.toString()` = `key + ":" + value + " "` (**trailing space**), `RFD.toString()` =
  `<LHS list rendering> + " -> " + <Column rendering>`, `Column.toString()` = `"(" + name + ")_" + threshold`,
  `SimilarityTuple.toString()` = `"SimilarityTuple [fields= " + getFields() + "weightedSimilarity=" +
  weightedSimilarity + ", fieldIndex=" + fieldIndex + "]"`.

### 4.3 `isFaultless(Field populated, ObjectArrayList tupleWithSimilarity, Tuple nullTuple) : boolean`

Locals: `populated` (1), `tupleWithSimilarity` (2), `nullTuple` (3), `rfd` (4), `lhs` (6),
`similarityTuple` (8), `indexFieldToPopulate` (10), `e` (11).
Exception table: `try [127,159) catch RuntimeException @162`. Source lines 1928–1964.

```java
for (RFD rfd : allRfd) {                                             // pc 0-22, cond 225
    for (Column lhs : rfd.getLHS()) {                                // pc 24-47, cond 215
        if (!lhs.getName().equals(populated.getKey())) continue;      // pc 49-61
        if (!areThereTuplesViolatingRFD(rfd, nullTuple)) continue;    // pc 64-71
        for (SimilarityTuple similarityTuple : tupleWithSimilarity) { // pc 74-93, cond 203
            int indexFieldToPopulate = similarityTuple.getFieldIndexSingleAttribute();  // pc 95-100
            try {                                                     // try [127,159)
                if (!similarityTuple.getFields().get(indexFieldToPopulate)
                         .getValue().equals("?")) {                    // pc 102-124
                    if (!similarityTuple.getFields().get(indexFieldToPopulate)
                             .getValue().equals(populated.getValue())) // pc 127-150
                        similarityTuple.setCareAbout(false);           // pc 153-156
                }
            } catch (RuntimeException e) {                             // pc 162
                if (!similarityTuple.getFields().get(indexFieldToPopulate)
                         .getValue().equals(populated.getValue()))
                    similarityTuple.setCareAbout(false);               // pc 190-193
            }
        }
        return false;                                                  // pc 206-207 (source line 1958)
    }
}
return true;                                                           // pc 228-229 (source line 1964)
```

Semantics: the tentative imputation is **rejected** iff there exists an RFD in `allRfd` that
(a) has the populated attribute among its LHS columns **and** (b) is currently
**violated by the dataset with respect to `nullTuple`** (`areThereTuplesViolatingRFD` returns true).
In that case, as a side effect, **every candidate whose value in the populated attribute differs from
the tentative value is permanently deactivated** (`careAbout = false`) — it is pruned for all later
candidates of the same null tuple. Otherwise the imputation is accepted.

Note that `isFaultless` is called *after* the tentative value has been written into `nullTuple`
(`populateFieldSingleAttribute` pc 59-80 precedes the call at pc 81-99), so
`areThereTuplesViolatingRFD` sees the hypothetical completed tuple.

### 4.4 `areThereTuplesViolatingRFD(RFD rfd, Tuple populatedTuple) : boolean`

Locals: `rfd` (1), `populatedTuple` (2), `x` (3), `thresholdPassed` (4), `lhs` (5), `tupleField` (7),
`populatedTupleField` (8), `t1/t2` (9/10), `e` (9), `distance` (10).
Exception tables: `try [119,261) @264`, `try [404,435) @437`. Source lines 2198–2298.

```java
for (int x = 0; x < dataset.size(); x++) {                                   // pc 0-2 -> cond 485
    if (populatedTuple.equals(dataset.get(x))) continue;                     // pc 5-17
    int thresholdPassed = 0;
    for (Column lhs : rfd.getLHS()) {                                        // pc 20-32 -> cond 313
        Field tupleField          = dataset.get(x).getFields().get(lhs.getIndex());
        Field populatedTupleField = populatedTuple.getFields().get(lhs.getIndex());
        if (!populatedTupleField.getValue().equals("?")
                && !tupleField.getValue().equals("?")) {                      // pc 91-116
            /* same B / C / numeric dispatch as isKeyRfd, thresholds from `lhs` */
            if (condition holds) thresholdPassed++;
        }
    }
    if (thresholdPassed == rfd.getLHS().size()) {                            // pc 316-325
        Field tupleField          = dataset.get(x).getFields().get(rfd.getRHS().getIndex());   // slot 5
        Field populatedTupleField = populatedTuple.getFields().get(rfd.getRHS().getIndex());   // slot 6
        if (!populatedTupleField.getValue().equals("?")
                && !tupleField.getValue().equals("?")) {
            try {
                if (Math.abs(parseDouble(tupleField) - parseDouble(populatedTupleField))
                        > rfd.getRHS().getThreshold())
                    return true;                       // pc 432 ifle -> continue ; pc 435 iconst_1/ireturn
            } catch (RuntimeException e) {
                distance = LevensteinDistance.levenshtein3(tupleField.getValue(),
                                                           populatedTupleField.getValue(),
                                                           rfd.getRHS().getThreshold());   // pc 439-459
                if (distance < 0 || (double) distance > rfd.getRHS().getThreshold())
                    return true;                       // pc 463 iflt -> 480 ; pc 477 ifle -> continue
            }
        }
    }
}
return false;                                                                    // pc 496-497
```

Differences from `isKeyRfd` worth noting:

* **Operand order is swapped**: here `dataset.get(x)` is `tupleField` and the argument
  `populatedTuple` is `populatedTupleField`, and the null test inspects `populatedTupleField` first.
* The RHS numeric test returns **`true`** when the difference **exceeds** the RHS threshold — the
  opposite sense to `isKeyRfd`'s `-1`.
* The Levenshtein variant returns `true` for `distance < 0 || distance > threshold` (pc 463
  `iflt -> 480` = the `return true` block). Since `levenshtein3` never returns a negative number the
  `distance < 0` disjunct is dead; the live test is `distance > threshold`, i.e. **an exact match
  (`distance == 0`) is correctly treated as NOT a violation** — which is the consistent behaviour, in
  contrast to `isKeyRfd`'s `ifle`.
* LHS columns that are `"?"` on either side are silently skipped, so a pair can "agree on the LHS"
  while some LHS columns were never compared.
* Self-exclusion uses `Tuple.equals` (positional value equality over `this.fields.size()` columns),
  not identity.

---

## 5. The imputation loop and mutation of state

### 5.1 `sequentialExecution()`

Locals: `tuplesWithNullValue` (1), `j` (2), `nullFields` (3), `f` (4), `nullTuple` (2 reused).
Source lines 313–346.

```java
System.out.println("Sequential heuristic selected!");              // pc 0-6 (#377)
ObjectArrayList<Tuple> tuplesWithNullValue = new ObjectArrayList<>();   // pc 9-16
startTime = System.currentTimeMillis();                            // pc 17-21
for (int j = 0; j < dataset.size(); j++) {                         // pc 24-26 -> cond 179
    ObjectArrayList<Field> nullFields = new ObjectArrayList<>();   // pc 29-36
    for (Field f : dataset.get(j).getFields()) {                   // pc 37-54 -> cond 109
        if (f.getValue().equals("?")) {                            // pc 71-82 (ifeq -> next field)
            nullCells++;                                           // pc 85-92 (field #47)
            nullFields.add(f);                                     // pc 95-100  (the SAME Field object)
        }
    }
    if (nullFields.size() > 0) {                                   // pc 112-116 (ifle -> next j)
        dataset.get(j).setNullFieldsCount(nullFields.size());      // pc 119-134
        dataset.get(j).setNullFields(nullFields);                  // pc 137-149
        tuplesWithNullValue.add(dataset.get(j));                   // pc 152-167  (the ORIGINAL object)
    }
}
for (Tuple nullTuple : tuplesWithNullValue)                        // pc 182-187 -> cond 215
    treatNullTuple(nullTuple, nullTuple.getIndex());               // pc 200-206
log.println("Total execution time " + (now - startTime) + "ms");   // pc 218-252 (#398, #315)
log.println("#Null cells: " + nullCells);                          // pc 255-279 (#400)
log.println("#Cells not filled: " + notFilledCells);               // pc 282-306 (#402)
```

* **Outer loop order = dataset order of the input CSV.** Only rows containing at least one `"?"` are
  collected, in increasing `j`; there is no sorting at all. (This is exactly what
  `nullValueBasedOrderExecution` and `timesInvolvedInLHSBasedOrderExecution` would have changed.)
* The second argument to `treatNullTuple` is `tuple.getIndex()` (0-based dataset position), **not**
  `getRow()`; `getIndex()` is the handle used for `dataset.set(index, ...)`.
* `nullCells` is a **global counter incremented once per `"?"` cell in the whole dataset**, before any
  imputation; it is printed but never decremented.
* `notFilledCells` is not touched here; it is mutated only in `treatNullTuple`.
* `Tuple.setNullFields`/`setNullFieldsCount` are called **only for rows with at least one null**; other
  rows keep `nullFields == null` and `nullFieldsCount == 0`. (This is why the dead
  `localSearchExecution`, which clones every tuple, must first call `setNullFields` on all rows: see
  `Tuple.clone()`'s NPE below.)
* `nullFields` holds the *actual* `Field` objects of the tuple's field list, so the list aliases the
  tuple state.

### 5.2 `treatNullTuple(Tuple tuple, int index)`

Locals: `tuple` (1), `index` (2), `nullFields` (3), `filled` (4), `rfds`/`maxNumberOfClusters` (5),
`field`/`i`/`x` (6), `candidates`/`candidatesMap` (7), `rfds`/`field`/`x` (8), `i`/`t1` (9),
`dependencies`/`e`/`imputed` (10), `candidates`/`y` (11), `found` (12), `t2` (13).
Exception table: `try [308,449) catch IndexOutOfBoundsException @452`. Source lines 772–976.

**Single-null-field path (`nullFields.size() == 1`, pc 8-13):**

```java
if (rfdForRHS.get(nullFields.get(0).getKey()) != null) {              // pc 16-34 (ifnull -> 170)
    for (ArrayList<SimilarityTuple> rfds :
             rfdForRHS.get(nullFields.get(0).getKey()).values()) {    // pc 37-70 -> cond 167
        System.out.print(".");                                        // pc 85-91 (#694)
        ObjectArrayList<SimilarityTuple> candidates = getCandidatesForField(tuple, rfds);  // pc 94-101
        if (candidates == null) {                                     // pc 103-105 (ifnonnull -> 129)
            dataset.set(index, tuple); revaluateKeyRFDs(tuple); filled = true; break;      // pc 108-126
        } else if (populateFieldSingleAttribute(tuple, candidates)) { // pc 129-136
            dataset.set(index, tuple); revaluateKeyRFDs(tuple); filled = true; break;      // pc 139-157
        }
    }
}
if (!filled) notFilledCells++;                                        // pc 170-172 / 175-182
return;                                                               // pc 185 -> 885
```

The cluster order is the `Map.values()` insertion order (the order in which RHS thresholds first
appear in the RFD file).

**Multi-null-field path (`nullFields.size() > 1`, pc 188-973):**

```java
int maxNumberOfClusters = 0;                                          // pc 196-197
for (Field field : nullFields) {                                      // pc 199-205 -> cond 269
    Map rfds = rfdForRHS.get(field.getKey());
    if (rfds != null && rfds.size() > maxNumberOfClusters) maxNumberOfClusters = rfds.size();
}
for (int i = 0; i < maxNumberOfClusters; i++) {                       // pc 272-275 -> cond 855
    Object2ObjectLinkedOpenHashMap candidatesMap = new Object2ObjectLinkedOpenHashMap();   // pc 278-285
    for (Field field : nullFields) {                                  // pc 287-293 -> cond 476
        try {                                                          // try [308,449)
            if (rfdForRHS.get(field.getKey()) != null) {              // pc 308-320 (ifnull -> 434)
                ArrayList<ArrayList<SimilarityTuple>> dependencies =
                    new ArrayList<>(rfdForRHS.get(field.getKey()).values());   // pc 323-358
                System.out.print(".");                                 // pc 360-366
                if (dependencies != null) {                            // pc 369-371 (ifnull -> 401)
                    ObjectArrayList<SimilarityTuple> candidates =
                        getCandidatesForField(tuple, dependencies.get(i));      // pc 374-381
                    if (candidates.size() > 0) candidatesMap.put(field, candidates);  // pc 383-400
                }
                if (dependencies == null || candidatesMap.get(field) == null)       // pc 401-413
                    candidatesMap.put(field, new ObjectArrayList<SimilarityTuple>());  // pc 416-431
            } else {
                candidatesMap.put(field, new ObjectArrayList<SimilarityTuple>());   // pc 434-448
            }
        } catch (IndexOutOfBoundsException e) {                        // i >= cluster count
            candidatesMap.put(field, new ObjectArrayList<SimilarityTuple>());       // pc 454-468
        }
    }
    if (nullFields.size() > 1) {                                       // pc 479-484 (redundant guard)
        for (int x = 0; x < nullFields.size()
                        && x < candidatesMap.get(nullFields.get(x)).size(); x++)    // pc 487-490 -> cond 727
            for (SimilarityTuple t1 : candidatesMap.get(nullFields.get(x)))         // pc 493-512 -> cond 693
                for (int y = x + 1; y < nullFields.size()
                                && y < candidatesMap.get(nullFields.get(y)).size(); y++) {  // pc 527-533 -> cond 667
                    boolean found = false;                                     // pc 536-537
                    for (SimilarityTuple t2 : candidatesMap.get(nullFields.get(y))) {  // pc 539-558 -> cond 616
                        if (t1.equals(t2)) {                                   // pc 573-580
                            t1.addNewWeight(t2.getWeightedSimilarity());        // pc 583-590
                            t2.addNewWeight(t1.getWeightedSimilarity());        // pc 593-600
                            found = true; break;                                // pc 603-606
                        }
                    }
                    if (!found)                                                // pc 619-621
                        t1.addNewWeight((double)(booleanEqualityThreshold + 1));// pc 624-633
                }
                /* after the y loop */                                          // pc 670-683
                t1.setWeightedSimilarity(t1.getWeightedSimilarity() / nullFields.size());
    }
    for (ObjectArrayList<SimilarityTuple> tupleWithSimilarity : candidatesMap.values()) {  // pc 730-742 -> cond 832
        Collections.sort(tupleWithSimilarity, new WeightedSimilarityComparator());   // pc 757-766
        if (populateFieldSingleAttribute(tuple, tupleWithSimilarity)) {              // pc 769-776
            Field imputed = tuple.getFields().get(
                tupleWithSimilarity.get(0).getFieldIndexSingleAttribute());          // pc 779-801
            dataset.set(index, tuple);                                              // pc 803-812
            revaluateKeyRFDs(tuple);                                                // pc 813-815
            nullFields.remove(imputed);                                             // pc 818-824
        }
    }
    if (nullFields.size() == 0) { filled = true; break; }                           // pc 835-845
}
if (!filled) notFilledCells += nullFields.size();                                   // pc 858-873
System.out.println("\n");                                                           // pc 876-882 (cp#685)
```

* `candidatesMap` maps each **null `Field` object** to its candidate list for cluster `i`. The
  `IndexOutOfBoundsException` catch handles fields that have fewer clusters than
  `maxNumberOfClusters`, putting an empty list.
* The `t1.equals(t2)` test is `SimilarityTuple.equals`, i.e. **positional value equality over the
  candidate tuple's whole field list** (bound = `this.getFields().size()`), meaning "the two candidate
  rows agree on every column". This is the cross-attribute consistency step: only candidate rows that
  support *all* the null attributes of the tuple are rewarded.
* The reward/penalty acts on `weightedSimilarity` (initially equal to `similarityIndex`, the mean
  normalised distance): agreeing pairs add each other's weight, a non-matching `t1` is penalised with
  `booleanEqualityThreshold + 1`, and each `t1` is finally divided by `nullFields.size()`. This is a
  *reweighting*, not a re-scoring.
* The lists are then sorted **ascending by `weightedSimilarity`** (`Collections.sort`, a stable merge
  sort), so element 0 is the best.
* After a successful imputation the field is removed from `nullFields` (`nullFields.remove(imputed)`);
  `Field.equals` compares **only the key**, so the removal succeeds even though `tuple.getFields()`
  now holds the *candidate's* `Field` object.
* The loop stops as soon as `nullFields` is empty (`filled = true; break;`).
* On failure `notFilledCells += nullFields.size()` — the *remaining* nulls, not the original count.
* The `if (nullFields.size() > 1)` guard at pc 479 is redundant (the branch is only entered when it is
  already `> 1`) — evidence of a refactor.

### 5.3 `updatePattern(int rowTuplePopulated)`

Locals: `rowTuplePopulated` (1), `tupleToPairWith` (2), `tuplesRowWNegativePatternValue` (3),
`row` (4), `indexPattern` (6), `newPattern` (7). Source lines 1838–1868.

```java
ArrayList<Integer> tupleToPairWith = tupleWithNullValue.get(rowTuplePopulated);         // pc 0-11
ArrayList<Integer> tuplesRowWNegativePatternValue = new ArrayList<>();                  // pc 12-19
if (tupleToPairWith != null) {                                                          // pc 20-21 (ifnull -> 160)
    for (Integer row : tupleToPairWith) {                                               // pc 24-30 -> cond 128
        String indexPattern = rowTuplePopulated + "-" + row;                            // pc 45-70
        Double[] newPattern = calculatePattern(dataset.get(rowTuplePopulated - 1),
                                               dataset.get(row.intValue() - 1),
                                               tuplesRowWNegativePatternValue);         // pc 72-107
        similarityPatterns.put(indexPattern, newPattern);                               // pc 109-120
    }
    if (tuplesRowWNegativePatternValue.size() > 0)                                      // pc 131-135
        tupleWithNullValue.put(rowTuplePopulated, tuplesRowWNegativePatternValue);      // pc 138-147
    else
        tupleWithNullValue.remove(rowTuplePopulated);                                   // pc 151-159
}
```

`tupleWithNullValue` is a **work queue**: `row → list of partner rows still to be paired with`.
`updatePattern` materialises the pattern arrays for that row against all its partners and then
replaces the row's entry with only those partners that actually contributed a
`tuplesRowWNegativePatternValue` entry (rows able to fill one of that row's holes); if none, the entry
is dropped. Rows are 1-based, `dataset` is 0-based, hence the `- 1` offsets.

### 5.4 `revaluateKeyRFDs(Tuple tuple)`

Locals: `tuple` (1), `iterator` (2), `rfd` (3), `verifiedTuples` (4), `i` (5), `thresholdPassed` (6),
`lhs` (7), `tuple1Field`/`tuple2Field`, `t1/t2`, `e`, `distance`, `rfdMap` (6), `rfdCollection` (7).
Exception tables: `try [146,288) @291`, `try [432,466) @469`. Source lines 980–1124.

It re-runs the `isKeyRfd` LHS test for `tuple` against **every** row `i` of the dataset (skipping
`tuple.equals(dataset.get(i))`), then, if `thresholdPassed == rfd.getLHS().size()`, the same
numeric/Levenshtein RHS tests (`pc 460 ifgt -> skip`; `pc 495 ifle -> skip`, i.e. the Levenshtein
variant again requires `0 < distance <= threshold`), accumulating `verifiedTuples`. Then, **inside**
the `i` loop:

```java
if (verifiedTuples > 0) {                                                  // pc 517 ifle -> i++
    System.out.println(rfd + " is no longer a key RFD!");                   // pc 520-543 (#795)
    allRfd.add(rfd);                                                       // pc 546-554
    if (rfdForRHS.containsKey(rfd.getRHS().getName())) {                    // pc 555-569 (ifeq -> 684)
        Map rfdMap = rfdForRHS.get(rfd.getRHS().getName());                  // pc 572-589
        ArrayList rfdCollection = (ArrayList) rfdMap.get(rfd.getRHS().getThreshold());  // pc 591-611
        if (rfdCollection != null) rfdCollection.add(rfd);                   // pc 613-624
        else { rfdCollection = new ArrayList(); rfdCollection.add(rfd);
               rfdMap.put(threshold, rfdCollection);
               rfdForRHS.put(name, rfdMap); }                                // pc 628-680
    } else {
        Map rfdMap = new Object2ObjectLinkedOpenHashMap();
        ArrayList rfdCollection = new ArrayList(); rfdCollection.add(rfd);
        rfdMap.put(rfd.getRHS().getThreshold(), rfdCollection);
        rfdForRHS.put(rfd.getRHS().getName(), rfdMap);                       // pc 684-745
    }
    break;                                                                  // pc 746 goto 764
}
/* after the i loop, reached both on normal completion and via the break */
iterator.remove();                                                          // pc 764-765 (source line 1121)
```

> **Important behavioural finding.** `iterator.remove()` sits *outside* the `for (i …)` loop (source
> line 1121, pcs 764-765, after the loop's increment/condition at pcs 749-761), so it runs for
> **every** RFD in `keyRFDs`, whether or not it "is no longer a key". The whole `keyRFDs` list is
> therefore **drained on the first call**, and later calls are no-ops. The `break` at pc 746 only
> skips the remaining `i` iterations. If the intent was "remove only the RFDs that stopped being
> keys", the `remove` would have to be inside the `if`; the bytecode does not do that (see §9.5).

The purpose of the re-check is that an imputation can turn a `"?"` LHS cell into a real value, which
can make a previously-unique LHS collide with another row and thus invalidate the key property.

### 5.5 `Tuple` / `Field` / `Column` / `SimilarityTuple` state semantics

* **`Tuple(ObjectArrayList fields, int row, int index)`** stores `fields` **by reference** and
  initialises **only** those three fields: `nullFields` stays `null`, `nullFieldsCount` and
  `involvedInLHSCount` stay `0`.
  `row` = 1-based data-row ordinal (used in all log/result output); `index` = 0-based position in
  `dataset` (used by `dataset.set(t.getIndex(), t)`).
* **`Tuple.equals`** compares the `Field.value` strings positionally with the loop bound taken from
  `this.fields.size()` (the receiver); `Field.key`, `row`, `index` and the counters are ignored, and
  the argument's size is never checked (a longer receiver throws `IndexOutOfBoundsException`).
* **`Tuple.clone()`** (source: `Tuple t = new Tuple(this.fields.clone(), this.row, this.index);
  t.setNullFields(this.nullFields.clone()); t.setNullFieldsCount(this.nullFieldsCount); return t;`):

  | structure | original vs clone |
  |---|---|
  | `fields` list object + backing array | **distinct** |
  | the `Field` objects inside `fields` | **SHARED** |
  | `nullFields` list object | **distinct** |
  | the `Field` objects inside `nullFields` | **SHARED** (and identical to the corresponding `fields` entries) |
  | `row`, `index`, `nullFieldsCount` | copied by value |
  | `involvedInLHSCount` | **NOT copied** → the clone keeps the constructor default `0` |

  `ObjectArrayList.clone()` is fastutil's `new ObjectArrayList(size)` + `System.arraycopy`, i.e. a
  fresh array of the same element references. Consequently **mutating a `Field` through the clone
  mutates the original** (`setValue`/`setTimesInvolved`), while structural edits
  (`fields.set(i, other)`, `add`, `remove`, `sort`) affect only the clone's list. `Field.clone()`
  exists (a bare `super.clone()`) but is **never called**. `Tuple.clone()` declares
  `CloneNotSupportedException` but cannot throw it; it **can** throw `NullPointerException` when
  `nullFields == null`, i.e. for a tuple that never went through a null-field scan.
* **`Field`** = `{String key; String value; int timesInvolved;}`, `timesInvolved = 0` at construction.
  `Field.equals` is `((Field) obj).getKey().equals(this.key)` — **key only**, no `instanceof`, no null
  check, asymmetric. `Field.toString()` = `key + ":" + value + " "`.
* **`Column`** = `{String name; double threshold; int index; String type;}`.
  `equals`/`hashCode` use **`name` only** (`equals` adds identity, `null` and `getClass()` checks;
  `hashCode` = `31 + name.hashCode()`). This is what makes `rfd.getLHS().contains(new Column(name,0.0,0,""))`
  in the dead `calculateGainInSwap` a name-only membership test.
* **`RFD`** = `{ArrayList<Column> LHS; Column RHS;}`, `toString()` = `LHS + " -> " + RHS`
  (literal is exactly `" -> "`).
* **`SimilarityTuple extends Tuple`**:
  `SimilarityTuple(ObjectArrayList fields, double similarityIndex, int fieldIndex, int row, RFD based,
  int rowIndex)` → `super(fields, row, rowIndex)`, `similarityIndex = arg2`,
  **`weightedSimilarity = arg2`** (same initial value), `fieldIndex = arg3`, `careAbout = true`,
  `based = arg5`. Because `super(fields, …)` stores the **candidate tuple's list object**, a
  `SimilarityTuple` *is* a view of the candidate's fields, with the candidate's `row`/`index`.
  `addNewWeight(w)` only touches `weightedSimilarity`. `equals` mirrors `Tuple.equals` but requires
  `instanceof SimilarityTuple`, so `Tuple.equals` and `SimilarityTuple.equals` are **not symmetric**.

### 5.6 `saveOutputFile()`

Reads `user.dir/TupleIniziali/<datasetFilePath>` (an input produced by the data-injection step, format
`row;attribute;expectedValue`), writes the header
`"riga;nome attributo;valore da imputare;valore imputato"` (`#331`) to the `populatedDataset` writer,
and for each input line: `row = Integer.parseInt(line.split(";")[0])`, `key = line.split(";")[1]`,
then `dataset.get(row - 1).getFields().stream().filter(e -> e.getKey().equals(key)).findAny().orElse(null)`
(`lambda$0(String,Field)` = `field.getKey().equals(name)`) and prints `line + ";" + f.getValue()`.
No `"?"` interpretation; a missing attribute name yields `null` and an NPE on `getValue()`.

---

## 6. Column types, distances and comparators

### 6.1 Type codes

`columnTypes` = `args[0].split(",")`, indexed by column position; each `Column` built by
`getRFDsFromFile` gets `columnTypes[index]`. The authors' `RENUVER/README.txt` defines the letters:

> `D = any data type: strings, numbers, decimals, etc..`
> `C = char data type, i.e., attribute values consisting of a single character`
> `B = boolean attribute values, i.e., attribute values whose value distribution consists of only two possible values (e.g., "M" and "F")`

The bytecode has **no test for `"D"` at all**: the only `String` type literals in `FillingAlgorithm`
are `cp#772 "B"`, `cp#774 "C"`, `cp#918 "E"`, `cp#813 "-"`, `cp#382 "?"`, `cp#333 ";"`. `"D"` is
therefore the `else` branch. The sample run script uses
`"D,C,D,D,D,D,D,B,B,D,D,D,D"` (so `RIVER` is `C`, `CLEAR-G`/`T-OR-D` are `B`, and textual columns such
as `MATERIAL`/`TYPE` are `D` — for which `parseDouble` fails and **Levenshtein is what actually
decides the match**).

| code | `calculatePattern` | `isKeyRfd` / `areThereTuplesViolatingRFD` / `revaluateKeyRFDs` / `getCandidatesForField` |
|------|--------------------|--------------------------------------------------------------------------------------------|
| `"B"` | **dead** (`columnTypes[i] == "B"`, `if_acmpne`) | live (`Column.getType().equals("B")`); if `threshold == booleanEqualityThreshold` → exact string equality; otherwise falls through to the numeric branch |
| `"C"` | `Math.abs(v1.charAt(0) - v2.charAt(0))` | `Math.abs(t1 - t2) <= Column.getThreshold()` |
| anything else (incl. `"D"`) | `Math.abs(parseDouble(v1) - parseDouble(v2))`, Levenshtein on failure | same |

`booleanEqualityThreshold` (CLI `args[4]`) has exactly three roles:
(i) the `'B'`-column discriminator (exact string equality instead of a distance);
(ii) the **initial upper bound** for the per-candidate best-RFD search
(`getCandidatesForField` pc 74-79) and the reweighting penalty `+1` in `treatNullTuple`
(pc 624-633);
(iii) the surrogate distance value of a `'B'` column in `calculatePattern`
(`thr` if equal, `thr + 1` if not).
It is **never** applied to `'C'` data and **never** passed into `levenshtein3`.

### 6.2 `LevensteinDistance.levenshtein3(Object, Object, double) : int`

`LevensteinDistance` has no fields and exactly two methods (`<init>` and the static `levenshtein3`);
there is no `levenshtein1`/`levenshtein2` in this build. LVT names: `firstElement`, `secondElement`,
`threshold`, `lhs`, `rhs`, `thr`.

```java
public static int levenshtein3(Object firstElement, Object secondElement, double threshold) {
    CharSequence lhs = (CharSequence) firstElement;      // pc 0-4   unconditional checkcast
    CharSequence rhs = (CharSequence) secondElement;     // pc 6-10
    int thr = (int) threshold;                           // pc 12-14 (d2i: truncation toward zero, NaN -> 0)
    if (firstElement == null || secondElement == null)   // pc 16-21 (ifnull / ifnonnull)
        return Integer.MAX_VALUE;                        // pc 24-26 (ldc #18 = 2147483647)
    if (Math.abs(lhs.length() - rhs.length()) > thr)     // pc 27-47 (if_icmple -> 66)
        return lhs.length() + rhs.length();              // pc 50-65
    return org.apache.commons.lang3.StringUtils
             .getLevenshteinDistance(lhs, rhs);          // pc 66-73
}
```

* **No type dispatch inside.** Two unconditional `checkcast java/lang/CharSequence` and no
  `instanceof`/`getClass`/branch on types; no numeric branch, no `Double.parseDouble`, no char
  handling, and no knowledge of `D`/`C`/`B`. Its constant pool has **zero `CONSTANT_String` entries**
  and exactly one numeric constant (`cp#18 Integer 2147483647`). All type dispatch lives in the
  callers, and all 7 call sites pass two `String`s from `Field.getValue()`, so the casts never fail.
* The third parameter is a **length-difference pre-filter**, not a distance bound: it is cast to `int`
  once and used only at pc 45-47. The bundled commons-lang3 **3.12.0**
  `StringUtils.getLevenshteinDistance(CharSequence, CharSequence)` is the classic unit-cost Levenshtein
  (insert/delete/substitute, no transposition, no case folding); the 3-argument overload with the `-1`
  sentinel exists in the bundled library but is **not** called here.
* **Return values:** `Integer.MAX_VALUE` if either argument is `null` (the test is on the original
  references after the casts, so a `null` argument does not throw); `len(lhs) + len(rhs)` if the
  length difference exceeds `thr` (a guaranteed upper bound, so the caller rejects it as `> thr`);
  otherwise the exact edit distance `>= 0`.
* **The return value is never negative.** Therefore every `if (distance < 0)` / `iflt` guard in
  `FillingAlgorithm` is dead, and the `ifle` guards mean `distance == 0`.
* With the `2147483647.0` threshold used by `calculatePattern`, the pre-filter never triggers and the
  result is always the exact distance.

The seven call sites (all in `FillingAlgorithm`): `revaluateKeyRFDs` pc 308 (LHS) and pc 488 (RHS);
`isKeyRfd` pc 287 (LHS) and pc 479 (RHS); `areThereTuplesViolatingRFD` pc 281 (LHS) and pc 456 (RHS);
`calculatePattern` pc 309. Their handlers catch **`java.lang.RuntimeException`** over the *whole*
type-dispatch region, not just `parseDouble`.

### 6.3 Comparators

| class | body | order | live? |
|-------|------|-------|-------|
| `SimilarityComparator.compare(a,b)` | `a.getSimilarityIndex()` vs `b.getSimilarityIndex()`: `dcmpl; ifle -> next` → `1`; `dcmpg; ifge -> next` → `-1`; else `0` | **ascending** by `similarityIndex` (NaN → 0) | **never instantiated** — dead |
| `WeightedSimilarityComparator.compare(a,b)` | identical shape on `a.getWeightedSimilarity()` | **ascending** by `weightedSimilarity` | used in `treatNullTuple` pc 766 (via `Collections.sort`) |
| `RHSThresholdComparator.compare(a,b)` | `(int)(a.getRHS().getThreshold() - b.getRHS().getThreshold())` (`dsub; d2i`) | ascending, **truncating** (thresholds less than 1.0 apart compare equal → non-transitive, contract-violating) | **never referenced** — dead |
| `FillingAlgorithm$NullValueComparator.compare(o1,o2)` | `iconst_m1; o1.getNullFieldsCount(); o2.getNullFieldsCount(); isub; imul` | **descending** by `nullFieldsCount` (most nulls first) | only in the dead `nullValueBasedOrderExecution` |
| `FillingAlgorithm$TimesInvolvedComparator.compare(o1,o2)` | `o1.getInvolvedInLHSCount() - o2.getInvolvedInLHSCount()` | **ascending** by `involvedInLHSCount` | only in the dead `timesInvolvedInLHSBasedOrderExecution` |

None defines an explicit tie-break. `ObjectArrayList` (fastutil 8) declares no `sort`, so
`list.sort(comp)` binds to the Java-8 default `List.sort` → `Arrays.sort(Object[], Comparator)`, which
is **stable** TimSort; `Collections.sort` likewise delegates to a stable merge sort. Ties therefore
preserve the pre-sort order (dataset order for the two dead heuristics, candidate insertion order for
`WeightedSimilarityComparator`).

---

## 7. Dead-code heuristics

None of the following is reachable from `Main` (`start(int)` never dispatches, and no reflection is
used). They are the clearest statement of the authors' intended optimisation directions.

### 7.1 `countTimeInvolved(Field f) : int`

`for (RFD r : allRfd) for (Column c : r.getLHS()) if (c.getName().equals(f.getKey())) n++; return n;`
(pc 0-88). An **unweighted occurrence count**: a column listed twice in one LHS counts twice; two RFDs
with the same LHS column count twice. No use of thresholds, of the RHS, or of `rfdForRHS`. Note that
`start` has already moved the key RFDs out of `allRfd`, so only non-key RFDs are counted in the
intended call order.

### 7.2 `cloneMap` / `cloneList`

* `cloneMap(m)` = `new Object2ObjectLinkedOpenHashMap(); putAll(m); return copy;` — **shallow at both
  levels**: the value objects (the `Map<Double,ArrayList<RFD>>` buckets, their `ArrayList`s and the
  `RFD`s) are shared with the original.
* `cloneList(list)` (**static**) = `new ObjectArrayList(list.size())` + `add(item.clone())` for each
  element — **deep at list + Tuple level, shallow at Field level** (see §5.5).
* Call sites: 7 × `cloneList` and 2 × `cloneMap`, **all inside `localSearchExecution`**.

### 7.3 `calculateGainInSwap(Tuple i, Tuple j) : double`

```java
double countI_J = 0.0;                                             // pc 0-1
for (Field nullFieldOfJ : j.getNullFields()) {                     // pc 2-24
    Map rfdsForJ = rfdForRHS.get(nullFieldOfJ.getKey());
    if (rfdsForJ == null) continue;                                // pc 43-45
    for (ArrayList<RFD> rfds : rfdsForJ.values())                  // pc 48-75
        for (RFD rfd : rfds)                                       // pc 77-97
            for (Field nullFieldsOfI : i.getNullFields()) {         // pc 99-121
                Column c = new Column(nullFieldsOfI.getKey(), 0.0, 0, "");   // pc 123-140
                if (rfd.getLHS().contains(c)) { countI_J += 1.0; break; }    // pc 142-159
            }
}
if (countI_J != 0.0) countI_J = countI_J / (double) j.getNullFieldsCount();   // pc 202-215
double countJ_I = 0.0;  /* mirror image with i and j swapped */               // pc 216-436
if (countJ_I != 0.0) countJ_I = countJ_I / (double) i.getNullFieldsCount();
return countI_J - countJ_I;                                                   // pc 438-442
```

With `N(a) = a.getNullFieldsCount()` and `hits(x→y)` = the number of RFDs `r` such that `r.RHS.name`
is a null column of `y` and `r.LHS` (name-only `Column.equals`, hence the throwaway
`new Column(name,0.0,0,"")`) contains at least one null column of `x` — counted once per RFD thanks to
the `break`:

```
gain(arg1 earlier, arg2 later) = hits(arg1 → arg2)/N(arg2) − hits(arg2 → arg1)/N(arg1)
```

Dimensionless, in `[-1,1]`; only `0.0`/`1.0` constants appear. `gain > 0` means the current order is
preferable; `gain < 0` means the later tuple benefits more from the partner and should be moved after
it. The division is guarded on the *numerator*, not the divisor.

### 7.4 `getNewGenerations(entry, knownOrders, tupleList) : Map`

* `entry.getKey()` is **not a column name**: it is a **comma-terminated permutation string of
  positional indices into `tupleList`**, e.g. `"0,1,2,"` (built in `localSearchExecution`);
  `getDoubleValue()` is never read here.
* `knownOrders` is an `ObjectArrayList<String>` used as both a dedup filter (`contains`, pc 282) and a
  sink (`add`, pc 296-302).
* `tupleList` is the list of `Tuple` clones, one per tuple with ≥ 1 null, in dataset order.
* It performs one linear pass `i = 0 … order.length-2`, computes
  `gain = calculateGainInSwap(tupleList.get(order[i]), tupleList.get(order[i+1]))`, accepts only
  **strictly `gain < 0`** (pc 100 `dcmpg`, pc 101 `ifge -> skip`; `NaN` is rejected too), requires
  strictly `gain < bestGain` (pc 108/109), builds the child order as the parent with positions `i`,
  `i+1` exchanged (prefix pcs 120-157, `order[i+1]` pcs 164-195, `order[i]` pcs 197-226, suffix
  pcs 228-276), and registers the child only if `!knownOrders.contains(newOrder)`.
* `bestGain` starts at `Double.MAX_VALUE` (`ldc2_w #549` = `0x7FEFFFFFFFFFFFFF`).
* Output: a `Double2ObjectLinkedOpenHashMap` mapping `Double bestGain → String childOrder`, i.e.
  **at most one entry** — there is exactly one `Map.put` site (pc 378).

> **Decisive bug: `getNewGenerations` always returns an empty map.** The accepted gains are by
> construction `< 0`, `bestGain` starts at `+MAX_VALUE` and is only ever assigned an accepted gain,
> but the single `put` is gated by `pc 316-320: dload bestGain; dconst_0; dcmpl; ifle -> 384`, i.e.
> it executes only if `bestGain > 0`. Either no swap was accepted (`bestOrder == ""`, also skipped by
> pc 331) or a swap was accepted (`bestGain < 0`, skipped by pc 320). The log line
> `"Nuovo ordine da analizzare creato: … prevede un vantaggio di …"` is therefore **unreachable**.
> Opcode bytes were re-checked against the standard table (pc 100/101 = `98 9c` = `dcmpg/ifge`;
> pc 319/320 = `97 9e` = `dcmpl/ifle`). Two repairs are conceivable — invert the accept test to
> `gain > 0` (which would flip the heuristic's meaning), or invert the final gate to `bestGain < 0`
> (the minimal-edit, semantically coherent repair given §7.3). The bytecode cannot prove which line
> was mistyped; it does prove that no child is ever produced.

### 7.5 `localSearchExecution() : ObjectArrayList`

Banner `"Local search heuristic selected!"` (`#413`).

* **Phase 1 (pc 9-231)**: pre-processing identical in layout to `sequentialExecution`
  (`nullCells++`, `setNullFieldsCount`, `setNullFields`) plus an explicit order encoding
  `slot2 = "0,1,…,k-1,"` where position `j` is the `j`-th null-containing tuple in dataset order, and
  a list of `dataset.get(i).clone()` in the same order. Unlike `sequentialExecution`,
  `setNullFieldsCount`/`setNullFields` are called for **every** tuple (also with count 0), which is
  what makes the later dataset-wide cloning safe (see the `nullFields == null` NPE in §5.5).
* **Phase 2 (pc 234-366)**: `cloneList(dataset)`, `cloneList(nullTupleList)`, `cloneMap(rfdForRHS)`,
  `scores = new Object2DoubleLinkedOpenHashMap()`, `knownOrders` seeded with the identity order, then
  the baseline run `for (Tuple t : slot1) treatNullTuple(t, t.getIndex())`; the resulting dataset
  snapshot goes into the return slot, after which `dataset`, the list and `rfdForRHS` are **restored**
  from the backups. `slot10 = notFilledCells`; `scores.put(order, (double) slot10)`;
  if `slot10 <= 0` the search is skipped entirely; otherwise `notFilledCells = 0`.
* **Phase 3 (pc 395-736)**: iterate the `scores` worklist with a fastutil linked-map entry iterator
  (`object2DoubleEntrySet().iterator()`, which is **not fail-fast** — `modCount` is never referenced —
  and walks the insertion-ordered link chain, so an appended entry would be seen later);
  print `"Parto dalla generazione " + key + " che ha ottenuto score " + value`; call
  `getNewGenerations`; print `"Sono state generate " + n + " nuovi figli"`; for each child, parse the
  permutation, `for (int p …) treatNullTuple(slot1.get(perm[p]), slot1.get(perm[p]).getIndex())`,
  overwrite `bestScore`/`bestOrder`/`bestDataset` (**there is no comparison anywhere in this method —
  no `dcmp*` at all**), restore the state, print `".\n"`, `scores.put(child, score)` and snapshot.
* Then, **unconditionally**, print
  `"Nessuna nuova generazione creata da analizzare\nElenco delle generazioni trattate"` (`#503`, one
  constant), one `"<order>con score: <value>"` line per entry, the three standard log lines (with
  `#402` fed the *local* baseline counter `slot10`, not the field), and return the snapshot.

Divergences from `sequentialExecution`: returns `ObjectArrayList` instead of `void`; **rolls the
`dataset` field back** so the return value is the only carrier of the imputed rows; keeps the
`rfdForRHS` restore shallow (so `revaluateKeyRFDs`'s mutations of shared `RFD`/`ArrayList` objects are
not undone); emits extra `System.out` tracing. Given §7.4, its **effective behaviour is the baseline
identity-order run only** (the `"."` prints and the child loop never execute).

### 7.6 `nullValueBasedOrderExecution()`

Banner `"Null value heuristic selected!"` (`#600`). The pre-processing loop is the **same instruction
layout at the same offsets** as `sequentialExecution`'s; the only added step is
`pc 182-190: slot1.sort(new FillingAlgorithm$NullValueComparator())`, followed by
`for (Tuple t : slot1) treatNullTuple(t, t.getIndex())` (pc 193-226) and the three standard log lines.
The sort key is the cached `nullFieldsCount` (which *is* set in this path), so tuples with the most
missing values are imputed first; ties keep dataset order (stable sort). Rows without nulls never enter
the order list.

### 7.7 `timesInvolvedInLHSBasedOrderExecution()`

Banner `"LHS involving counter heuristic selected!"` (`#613`). The pre-processing loop is fused with
the LHS bookkeeping:

```java
for each row i, for each Field f with value "?":           // pc 80-101
    nullCells++;                                            // pc 94-101
    int c = memo.containsKey(f.getKey()) ? memo.getInt(f.getKey())   // Object2IntLinkedOpenHashMap
                                         : countTimeInvolved(f);     // pc 107-152
    f.setTimesInvolved(c);                                  // pc 153-157
    nulls.add(f);                                           // pc 160-164
if (nulls.size() > 0) {                                     // pc 178-183
    int max = -1;                                           // pc 186-187
    for (Field f : nulls) if (f.getTimesInvolved() > max) max = f.getTimesInvolved();  // pc 189-235
    dataset.get(i).setInvolvedInLHSCount(max);              // pc 238-251  (only writer in the JAR)
    dataset.get(i).setNullFields(nulls);                    // pc 254-267
    System.out.println("The tuple at row " + tuple.getRow() + " has " + nulls.size()
        + " null value/s.\nIts field appear " + max + " times in LHSs of RFDs.");      // #639/#644/#646/#648
    slot1.add(dataset.get(i));                              // pc 337-349
}
slot1.sort(new FillingAlgorithm$TimesInvolvedComparator()); // pc 367-375
System.out.println("The order is the sequent:");            // pc 378-384 (#653)
for (Tuple t : slot1) System.out.println(t + " - null value appears "
        + t.getInvolvedInLHSCount() + " times");            // #659/#664
for (Tuple t : slot1) treatNullTuple(t, t.getIndex());      // pc 465-482
/* + the three standard log lines */
```

* The ordering key is the **maximum** (not the sum, not a single field) over the tuple's null fields of
  the number of LHS occurrences of that column; the ascending comparator puts tuples whose missing
  columns are least involved in rule LHSs first.
* **Divergence:** this path never calls `Tuple.setNullFieldsCount`, so `getNullFieldsCount()` stays `0`
  for every tuple. Harmless in isolation (the field is not read here), but it makes this ordering
  incompatible with the `NullValueComparator` and with `calculateGainInSwap`'s denominators — note the
  division guard tests the numerator, so a stale `0` divisor would give `±Infinity`.
* The memo is keyed by **column name** while `setTimesInvolved(c)` writes onto the *current tuple's*
  `Field` object, so for a column that is null in several rows the same value is stamped on each.

---

## 8. Concrete pruning hook points

Every place an external semantic-pruning step could intervene, what it receives, and exactly what it
must produce. "Required output" means the invariants the surrounding bookkeeping depends on.

**(a) Dataset loading — `getDatasetFromFile(String csvPath, String splitChar)`.**
Receives the raw CSV. Must produce `ObjectArrayList<Tuple>` with `Tuple.fields[i].key` = the header
name of column `i`, `row` = 1-based data-row ordinal, `index` = 0-based position in the returned list
(`treatNullTuple` writes back with `dataset.set(index, tuple)`). A pruner may rewrite cell values here
(unit normalisation, canonicalisation) *before* the `"?"` convention applies; it must not reorder
columns, because `columnTypes` is positional.

**(b) RFD loading — `getRFDsFromFile(String splitChar, String nullChar, String[] columnTypes)`.**
Receives the RFD CSV. Must produce `ArrayList<RFD>` whose every `Column` carries the **0-based dataset
index** of its attribute, a threshold and a type string. This is the cheapest semantic-pruning seam:
dropping a `(RFD line)` removes it from `allRfd` and therefore from `createMapOnRHS`,
`findBestRFDs`, `rfdForRHS`, `isFaultless` and the dead heuristics. `rfdFieldsName` must still be filled
from the header (only the dead `createNewRFDFile` reads it, so this is currently inconsequential).

**(c) Key-RFD split — `start(int)` pc 14-86.** Produces the partition
`allRfd` (everything usable as a rule) vs `keyRFDs` (LHS behaves like a key, RHS threshold exactly 0.0).
Vetoing/forcing `isKeyRfd` changes which RFDs are usable: moving an RFD into `keyRFDs` removes it from
every rule lookup until `revaluateKeyRFDs` re-admits it.

**(d) RFD cache — `createMapOnRHS()` and `findBestRFDs(String nullField, Tuple nullTuple)`.**
Produces `rfdForRHS : columnName → Map<Double rhsThreshold, ArrayList<RFD>>`, computed **once per
column name** from the first tuple that has a null in that column. `findBestRFDs` is the per-column
entry point; returning **`null` means "this column can never be imputed"** (it stays `"?"` and
inflates `notFilledCells`). Required invariants: the map's values must be `ArrayList<RFD>`, and **the
positional order of `values()` defines the "cluster index" `i`** used by `treatNullTuple`'s
multi-attribute loop — reordering or dropping clusters changes the semantics of every multi-null
tuple. `rfdForRHS` is also read by the dead `calculateGainInSwap` and by `revaluateKeyRFDs`, so this is
the highest-leverage hook.

**(e) Candidate generation — `getCandidatesForField(Tuple nullTuple, ArrayList<RFD> selectedRFDs)`.**
Receives one RHS-threshold cluster. Must return an `ObjectArrayList<SimilarityTuple>` **or `null`** —
and **`null` is reserved**: it means "an exact single-attribute match was found and already committed",
and the caller responds by committing the tuple, calling `revaluateKeyRFDs` and marking it filled. A
pruner meaning "no candidates" must return an **empty list**.
Each returned `SimilarityTuple` must have: `fields` = the candidate dataset tuple's **actual**
`ObjectArrayList<Field>` (shared, not copied); `fieldIndex` = the column to impute;
`weightedSimilarity` initialised to the score (it is the sort key); `careAbout = true`;
`based` = the supporting RFD; `row`/`index` = the candidate's. Side effects to reproduce or
deliberately skip: writes into `similarityPatterns` (`"<nullRow>-<candRow>"`), maintenance of
`tupleWithNullValue[nullRow]` (the work queue consumed by `updatePattern`), and the
`results.println(...)` audit line.

**(f) Acceptance test — `isFaultless(Field populated, ArrayList tupleWithSimilarity, Tuple nullTuple)`.**
Called **after** the tentative value has been written into `nullTuple`, so a semantic checker sees the
hypothetical completed tuple. Must return `boolean`; `true` = keep, `false` = roll back (the caller
restores a `new Field(key, "?")`). A pruner can AND its own predicate here. Beware the existing side
effect: it sets `careAbout = false` on every candidate disagreeing with the tentative value, which
permanently removes those candidates for this null tuple.

**(g) Value selection / commit — `populateFieldSingleAttribute(Tuple nullTuple, ArrayList tupleWithSimilarity)`.**
Iterates the candidate list and mutates `nullTuple.getFields().set(idx, candidateField)`. Options:
(i) pre-sort/pre-filter the list before the call — ordering is already load-bearing (the
multi-attribute path sorts ascending by `weightedSimilarity`, the single-attribute path does not);
(ii) set `careAbout = false` to veto candidates; (iii) wrap the method to add a semantic constraint
before delegating. Required outputs: `boolean`, plus the `results.println` and
`updatePattern(nullTuple.getRow())` side effects.

**(h) Multi-attribute consistency — `treatNullTuple(Tuple, int)` pc 479-845.**
`candidatesMap : Field → ObjectArrayList<SimilarityTuple>` is the cross-attribute structure, and the
`t1.equals(t2)` whole-row value-equality test is the existing "the same source row supports both
attributes" rule — the natural place to substitute a *semantic* join (e.g. "same entity" rather than
"identical values"). Any replacement must keep `weightedSimilarity` monotonically comparable (the later
`Collections.sort(..., WeightedSimilarityComparator)` and `tupleWithSimilarity.get(0)` depend on it) and
must mutate `nullFields` (via `remove(imputed)`) plus `filled` so the `nullFields.size() == 0` /
`notFilledCells += size()` accounting stays correct. Note `nullFields.remove` relies on `Field.equals`
being **key-only**: replacing the tuple's `Field` objects with different keys silently breaks the loop.

**(i) Pattern cache — `updatePattern(int)`.** `tupleWithNullValue : row → ArrayList<Integer> partnerRows`
must be re-materialised into `similarityPatterns` whenever the tentative imputation changes which
partners are still usable. Any hook that mutates `tupleWithNullValue` must call `updatePattern(row)`,
or `getCandidatesForField` will reuse stale `Double[]` patterns (cache key `"<nullRow>-<candRow>"`, with
a symmetric fallback lookup).

**(j) Key re-evaluation — `revaluateKeyRFDs(Tuple)`.** Called after every successful imputation; decides
whether a former key RFD must be moved into `allRfd` and `rfdForRHS`. This is where a pruner can
re-admit or permanently retire an RFD. **Caveat: as compiled, the method drains `keyRFDs`
unconditionally** (§5.4), so after the first successful imputation this hook has no input left.

**(k) Final audit / output — `saveOutputFile()`.** Reads `TupleIniziali/<datasetFilePath>`
(`row;attributeName` per line, plus an expected value that is echoed), writes
`Populated/output_….csv` with the header
`"riga;nome attributo;valore da imputare;valore imputato"`, one line per requested cell:
`line + ";" + dataset.get(row-1) field with key == attributeName .getValue()`. This is the
**verification hook**: an external semantic checker can compare the requested cells against the
`Results` writer (which carries `row;field;candidate;rfd;score`, plus the `; exact` variant) and the
`Logs` writer (`#Null cells:`, `#Cells not filled:`, timings). A missing attribute name yields `null`
and an NPE, and there is no `"?"` post-check on the output.

**(l) Fixed knobs usable without touching the control flow:** `columnTypes[]` (stored by reference in
the constructor; note the `calculatePattern` `B` branch is only reachable for an *interned* `"B"`),
`booleanEqualityThreshold` (score bound + boolean distance + reweight penalty), and the null marker
(`"?"`, a hard-coded literal compared by `String.equals` in every heuristic).

**(m) Dead-code hooks.** `getNewGenerations(entry, knownOrders, tupleList)` +
`calculateGainInSwap(i, j)` are exactly the seam where an external scorer over *processing orders*
would be plugged in, and `localSearchExecution` is the driver that would consume it (after fixing the
§7.4 sign bug). `nullValueBasedOrderExecution` and `timesInvolvedInLHSBasedOrderExecution` are the two
alternative orderings, each a one-line change away from `sequentialExecution`.

---

## 9. Open ambiguities

1. **`getDigits` is unsafe and its domain is undocumented.** The scientific-notation branch searches
   for the first `'-'` rather than the `'E'`, so it throws `NumberFormatException` for negative values
   and for positive exponents; `getCandidatesForField` has no exception table, so such a threshold
   aborts the run. It is only ever called on LHS thresholds in `(0,1)` for well-formed input.
   *Competing readings*: the author may have assumed the sub-unit domain; the bytecode cannot decide.
2. **`columnTypes[i] == "B"` is a reference comparison** (`if_acmpne`, `calculatePattern` pc 152),
   while the adjacent `"C"` test uses `String.equals` (pc 215). Since `columnTypes` comes from
   `String.split`, the boolean branch of `calculatePattern` is unreachable in practice.
   *Competing readings*: (a) a genuine `==` bug making boolean support in the pattern path dead;
   (b) an identity test that would work only for interned literals — but `Main` passes
   `args[0].split(",")`, so (a) is far more likely. Every other type dispatch uses `equals`, so only
   the scoring path degenerates.
3. **`iflt` vs `ifle` on the Levenshtein RHS test.** `isKeyRfd` uses `ifle` (pc 486, `distance <= 0 →
   return -1`), `areThereTuplesViolatingRFD` uses `iflt` (pc 463, `distance < 0 → return true`), and
   the LHS handlers use `iflt` (pc 294 in `isKeyRfd`, "skip"). Because `levenshtein3` never returns a
   negative value, the `iflt` tests are dead and `isKeyRfd`'s RHS Levenshtein path returns `-1` for
   every reachable input. *Competing readings*: (a) a typo for `iflt`; (b) a deliberate rule. Given
   that the numeric sibling accepts equality, (a) is much more likely. No practical consequence here,
   because `start` only tests `isKeyRfd(...) != 0`.
4. **The RHS half of `isKeyRfd` is unobservable.** `start` distinguishes only `0` from non-zero, so
   `-1` and `n > 0` are equivalent to the caller. The `int` return type (rather than `boolean`)
   suggests an earlier design where the verifying-pair count mattered; that design is not visible.
5. **`revaluateKeyRFDs` drains `keyRFDs`.** `iterator.remove()` is compiled after the `for (i …)` loop
   (pc 764, source line 1121) and is reached both on normal completion and via the `break` at pc 746,
   so every key RFD is removed on the first call. *Competing readings*: (a) an authoring bug (the
   `remove` was meant to sit inside `if (verifiedTuples > 0)`); (b) an intentional one-shot
   re-evaluation. The method name and the `" is no longer a key RFD!"` message point to (a), but the
   bytecode is unambiguous about what runs.
6. **The `NoKeyRFD/` mechanism is entirely dead.** `getRFDsFromFile` computes and prints the
   `NoKeyRFD/<file>` path and then unconditionally overwrites it with `RFD/<file>` (pc 76-118, no
   branch in between); there is no `File.exists()` anywhere; and `createNewRFDFile()` — the only writer
   of that directory — has no call site. This contradicts the brief's "already-established fact" that a
   pre-existing `NoKeyRFD/<rfdFileName>` is preferred.
7. **Sub-unit threshold normalisation is an amplification.** For `0 < thr < 1` the contribution is
   `d * 10^getDigits(thr)`, for `thr >= 1` it is `d / 10^(len(str((int) thr))-1)`. Both express "divide
   by the threshold's granularity", but the sub-unit case produces values many orders of magnitude
   larger than the `booleanEqualityThreshold` bound they are compared against, so fine-grained columns
   dominate the average. Whether this is intended scaling or a `*`/`/` slip cannot be decided from the
   bytecode: the source expression is literally
   `patternValue * Math.pow(10.0, (double) getDigits(lhs.getThreshold()))`.
8. **`Tuple.clone()` shares `Field` objects and drops `involvedInLHSCount`.** `fields.clone()` /
   `nullFields.clone()` are shallow (fastutil `new ObjectArrayList` + `System.arraycopy`), so the
   clone's `Field` instances are the originals; and the clone's `involvedInLHSCount` is `0`. For the
   live path this is harmless (no clone is taken), but it changes the meaning of the dead
   `localSearchExecution` / `TimesInvolvedComparator` combination. Also, `Tuple.clone()` NPEs when
   `nullFields == null`, i.e. for tuples that never went through a null scan — which is why the dead
   `localSearchExecution` must call `setNullFields` on *every* row before cloning.
9. **`if (dependencies == null …)` in `treatNullTuple` (pc 401) is statically non-null** — it sits
   inside `if (dependencies != null)`. The compiled source is most plausibly the *separate* statement
   `if (dependencies == null || candidatesMap.get(field) == null) candidatesMap.put(field, new
   ObjectArrayList<>());`, which reduces at runtime to `if (candidatesMap.get(field) == null) put(empty)`
   unless the exception handler jumped there. Either way the effect is the same, but the guard is
   redundant.
10. **The `x`/`y` guards on the cross-attribute loops** in `treatNullTuple` (pc 708-727 and pc 648-667)
    are explicit extra conditions in the `for` statements (`x < nullFields.size() && x <
    candidatesMap.get(nullFields.get(x)).size()`), not artefacts. Their intent (skip attribute pairs
    whose candidate lists are shorter than the index) is clear; whether `<` or `<=` was meant is not
    decidable.
11. **`calculatePattern` sizes its result by argument 1 but loops over argument 2**
    (`new Double[nullTuple.getFields().size()]`, bound `tuple.getFields().size()`); for ragged input
    this is an `ArrayIndexOutOfBoundsException`. Likewise `pattern[lhs.getIndex()].doubleValue()` would
    NPE if a slot were left `null`, which the current `levenshtein3` can never do (`if (distance >= 0)`
    at pc 316 is always true).
12. **`RHSThresholdComparator` truncates** `(a.threshold - b.threshold)` to `int`, so `0.0` and `0.5`
    compare equal and the comparator is non-transitive (contract-violating). It has no live call site,
    so this only affects the dead heuristics — as does `SimilarityComparator`, which is never even
    instantiated.
13. **`Tuple.equals` / `SimilarityTuple.equals` bound the loop by `this.fields.size()`** and never
    compare the other operand's size (and `SimilarityTuple.equals` additionally requires
    `instanceof SimilarityTuple`, making the two implementations asymmetric). Two tuples of different
    width can therefore be "equal", which matters in `treatNullTuple`'s `t1.equals(t2)` cross-attribute
    test only for ragged datasets.
14. **`getNewGenerations` can never produce a child** (see §7.4). Which of the two inverted tests is the
    defect cannot be proven from the bytecode; what is proven is that the entire local-search
    generation loop, its tracing output and the `#503` "no new generation" banner path are
    unreachable in effect. A secondary consequence — the missing *best-candidate comparison* in
    `localSearchExecution` (no `dcmp*` anywhere in its body; candidates merely overwrite the incumbent)
    — would only become observable after that bug is fixed.
