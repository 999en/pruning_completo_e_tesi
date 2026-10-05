# RENUVER (EDBT prototype) — data model & column/string distance: bytecode reconstruction

**Artifact analysed.** Classes in `analisi/classi/` (rigenerabili con `python3 analisi/estrai_classi.py`)
are byte-identical (MD5) to the members of `RENUVER/RENUVER_EDBT.jar`: `Tuple.class cee066c1a449…`, `Column.class c736f09d198a…`,
`LevensteinDistance.class cc3aa7aa2de6…`, `FillingAlgorithm.class 4ccf1b7e50c7…`. Class file major version 52 (Java 8),
`SourceFile` attributes present, `LocalVariableTable` retained (used below as evidence for parameter names).
All offsets below are **bytecode offsets (pc)**; branch targets are given as absolute pcs.
Bundled library: `org/apache/commons/lang3` **3.12.0** (`META-INF/maven/org.apache.commons/commons-lang3/pom.properties`),
`it.unimi.dsi.fastutil` (8.x API).

---

## A. `Column`

Class header: `this Column super java/lang/Object interfaces []`; fields (all `private`):
`name Ljava/lang/String;`, `type Ljava/lang/String;`, `index I`, `threshold D`.

### Constructor `Column(String, double, int, String)`

`LocalVariableTable` of `<init>(Ljava/lang/String;DILjava/lang/String;)V` is decisive on argument order:

```
slot 1  name       Ljava/lang/String;     slot 4  index  I
slot 2  threshold  D                      slot 5  type   Ljava/lang/String;
```

Body (offsets 5, 10, 15, 21):

```
    5: aload_1   putfield #18 // Column.name      Ljava/lang/String;
   10: dload_2   putfield #20 // Column.threshold D
   15: iload 4   putfield #22 // Column.index     I
   21: aload 5   putfield #24 // Column.type      Ljava/lang/String;
```

So the signature is `Column(String name, double threshold, int index, String type)` →
`name=arg1`, `threshold=arg2`, `index=arg3`, `type=arg4`.

Call-site corroboration (`FillingAlgorithm.getRFDsFromFile`, offsets 323–359, locals `rhsName`,`rhsIndex`,`i`):

```
341: rfdFieldsName.get(i)          // String  -> name
346: Double.parseDouble(fields[i]) // double  -> threshold
349: iload 16 ; 351: iconst_1 ; isub   // i-1  -> index (0-based attribute position)
353: aload_3 ; 354: iload 16 ; 358: aaload  // columnTypes[i-1] -> type
359: invokespecial Column.<init>
```

i.e. `name` = attribute name, `index` = 0-based column position in a dataset row, `threshold` = the per-RFD
similarity threshold read from the RFD file, `type` = the user-supplied type letter.

### Accessors
`getType()/setType(String)`, `getName()/setName(String)`, `getThreshold()/setThreshold(double)`, `getIndex()`.
**There is no `setIndex`** (method list has exactly 11 members: `<init>`, getType, setType, getName, setName,
getThreshold, setThreshold, getIndex, toString, hashCode, equals). `index` and `type` are `private`, not `final`.

### `toString()` (offsets 0–31)
```
new StringBuilder("(") ; append(this.name) ; append(")_") ; append(this.threshold) ; toString()
```
Constant pool: `cp#45 String '('`, `cp#53 String ')_'` → `"(" + name + ")_" + threshold`
(e.g. `(REL-L)_2.0`, matching `testrun/Results/output_bridges_14_1.csv_3H4.txt`).

### `hashCode()` (offsets 0–31)
```
    0: bipush 31 ; istore_1        // int prime = 31;  <-- stored and never used again (dead local "prime")
    3: iconst_1 ; istore_2         // int result = 1;  (LVT: slot 2 = "result")
    5: bipush 31 ; iload_2 ; imul  // 31 * result
    9: getfield Column.name ; ifnonnull -> 20 ; iconst_0 ; goto 27
   20: getfield Column.name ; invokevirtual String.hashCode()I
   27: iadd ; istore_2 ; iload_2 ; ireturn
```
⇒ `result = 31 * 1 + (name == null ? 0 : name.hashCode())` = `31 + name.hashCode()`.
Only `name` participates; `threshold`, `index`, `type` are ignored.

### `equals(Object)` (offsets 0–64), local `other` (`checkcast Column` at 27)
```
 0/2: if_acmpne -> 7      // this == obj  -> (fallthrough at 5) iconst_1; ireturn
 7/8: ifnonnull -> 13     // obj == null  -> iconst_0; ireturn
13–21: getClass() != obj.getClass() -> iconst_0; ireturn   (getClass comparison ⇒ subclasses never equal)
26–30: other = (Column) obj
31–55: this.name == null ? (other.name != null -> false) : this.name.equals(other.name)
63:   iconst_1
```
⇒ **`equals` compares `name` only** (null-safe on the receiver's side), plus identity/`getClass`/`checkcast`.
`threshold`, `index`, `type` are *not* compared ⇒ two Columns for the same attribute but with different
thresholds or even different type letters are `equals`-equal (and share a hashCode).

---

## B. `RFD`

`this RFD super java/lang/Object interfaces []`. Fields: `LHS Ljava/util/ArrayList;` (Signature attribute present,
i.e. generic `ArrayList<Column>`), `RHS LColumn;`.

### Constructor `RFD(java.util.ArrayList, Column)`
LVT parameter names: slot 1 `lHS Ljava/util/ArrayList;`, slot 2 `rHS LColumn;`.
```
    5: aload_1 putfield #18 // RFD.LHS : ArrayList
   10: aload_2 putfield #20 // RFD.RHS : Column
```
Accessors: `getLHS()/setLHS(ArrayList)`, `getRHS()/setRHS(Column)`. No `equals`, no `hashCode` (identity hash).

### `toString()` (offsets 0–29)
```
new StringBuilder() ; append(this.LHS) /* StringBuilder.append(Object) -> ArrayList.toString() */
                     ; ldc #48 ' -> ' ; append(this.RHS) /* -> Column.toString() */ ; toString()
```
Constant pool entry is exactly three characters: `cp#48 String ' -> '` (space, hyphen, greater-than, space).
⇒ `"[<col>, <col>, …] -> (<name>)_<threshold>"` (identical to the `;RFD;` column of the Results file).

Construction site (`getRFDsFromFile` 396–409): `new RFD(lhsList, rhsEl)` where `lhsList` is the `ArrayList<Column>`
of the LHS attributes and `rhsEl` is the RHS `Column`; the RHS entry is the one whose *name* matches `fields[0]`.

---

## C. `Field`

`this Field super java/lang/Object interfaces [java/lang/Cloneable]`. Fields (private):
`timesInvolved I`, `key Ljava/lang/String;`, `value Ljava/lang/String;`.

### Constructor `Field(String, String)`
LVT: slot 1 `key`, slot 2 `value`.
```
    5: aload_1 putfield #18 // Field.key
   10: aload_2 putfield #20 // Field.value
   15: iconst_0 putfield #22 // Field.timesInvolved = 0
```
⇒ `Field(String key, String value)`, `timesInvolved` initialised to **0**.

### Accessors
`getKey()`, `getValue()`, `setValue(String)`, `getTimesInvolved()`, `setTimesInvolved(int)`.
**No `setKey`.** `value` is always a `String` — the data model never stores a numeric/Boolean cell value or a Java
`null` value (see Context §H).

### `toString()` (offsets 0–34)
```
new StringBuilder(String.valueOf(this.key)) ; append(":") ; append(this.value) ; append(" ") ; toString()
```
⇒ `key + ":" + value + " "` — **note the trailing space** (`cp#49 String ' '`); corroborated by
`Results/output_…txt` lines such as `22;REL-L:S ;` and by `Populated/…csv` (`26;LANES;2;?`).

### `timesInvolved`
Written only by `FillingAlgorithm.timesInvolvedInLHSBasedOrderExecution` (offset 157:
`Field.setTimesInvolved(I)`), with `countTimeInvolved(field)` = number of `RFD`s in `allRfd` whose LHS contains a
`Column` with the same `name` as `field.getKey()` (`countTimeInvolved`, offsets 37–88). It is a cache of
"how many RFDs use this attribute in the LHS"; it is a property of the *Field object*, not of the tuple.

### `equals(Object)` (whole method, 17 bytes; local `r`)
```
    0: aload_1 ; checkcast Field ; astore_2
    5: aload_2 ; invokevirtual Field.getKey() ; aload_0 ; getfield Field.key ; String.equals ; ireturn
```
⇒ `((Field) obj).getKey().equals(this.key)` — **only `key` is compared** (receiver/argument order reversed:
the *other* field's key is the receiver). `value` and `timesInvolved` are ignored. No `==` shortcut, no null check:
passing `null` or a non-`Field` throws (`NullPointerException` / `ClassCastException`); a `Field` whose `key` is
`null` also throws. No `hashCode` override (identity hash).

### `clone()` — shallow, and never used
```
=== METHOD clone()Ljava/lang/Object; (access 0x1, throws java/lang/CloneNotSupportedException)
    0: aload_0
    1: invokespecial #72 // java/lang/Object.clone.()Ljava/lang/Object;
    4: areturn
```
`Object.clone()` on a `Cloneable` class ⇒ a **new `Field` object** with `key` and `value` **copied by reference**
(`String`s are immutable, so this is indistinguishable from a value copy) and the same `timesInvolved`.
`key`/`value`/`timesInvolved` are then fully independent between original and clone — mutating the clone with
`setValue`/`setTimesInvolved` does **not** affect the original.
No `athrow` is present, so the declared `CloneNotSupportedException` is never thrown in practice.
**`Field.clone()` has no callers anywhere in the JAR** (no constant-pool reference to `Field.clone` in any
non-library class) — it is dead code.

---

## D. `Tuple`

`this Tuple super java/lang/Object interfaces [java/lang/Cloneable]`. Field order in the class file:
`row I`, `index I`, `nullFieldsCount I`, `involvedInLHSCount I`,
`nullFields Lit/unimi/dsi/fastutil/objects/ObjectArrayList;` (Signature), `fields …ObjectArrayList;` (Signature).

### Constructor `Tuple(ObjectArrayList, int, int)`
LVT is decisive: slot 1 `fields Lit/unimi/dsi/fastutil/objects/ObjectArrayList;`, slot 2 `row I`, slot 3 `index I`.
```
    5: aload_1 putfield #24 // Tuple.fields : ObjectArrayList
   10: iload_2 putfield #26 // Tuple.row    : I
   15: iload_3 putfield #28 // Tuple.index  : I
   19: return
```
⇒ `Tuple(ObjectArrayList fields, int row, int index)`. The constructor initialises **only** those three fields:
`nullFields` stays `null`, `nullFieldsCount` and `involvedInLHSCount` stay `0`.

Meaning of `row` / `index` (`getDatasetFromFile`, offsets 190–211, LVT locals `row I`, `index I`):
the reader skips the header line and, for every data line, executes
`dataset.add(new Tuple(tupleFields, row, index))` with post-increments, `row` starting at 1 and `index` at 0.
⇒ `row` = 1-based data-row number (used in all log/result output, `Tuple.getRow()`),
`index` = 0-based position of the tuple in `FillingAlgorithm.dataset`, and it is used as such:
`dataset.set(t.getIndex(), t)` in `treatNullTuple` and `treatNullTuple(t, t.getIndex())` in the heuristics.
For a well-formed file `row == index + 1` always.

Accessors: `getIndex()`, `getRow()`, `getFields()/setFields(ObjectArrayList)`,
`getNullFieldsCount()/setNullFieldsCount(int)`, `getNullFields()/setNullFields(ObjectArrayList)`,
`getInvolvedInLHSCount()/setInvolvedInLHSCount(int)`. No `setRow`, no `setIndex`, no `hashCode`.

### `toString()`
```
    0: getfield Tuple.fields ; invokevirtual ObjectArrayList.toString() ; areturn
```
⇒ the bare `fields` list rendering, e.g. `[ID:E27 , RIVER:A , … , TYPE:SIMPLE-T ]`
(note the `Field.toString()` trailing space before each comma). Seen verbatim in the Results file for the
"exact" fill branch.

### `equals(Object)` (offsets 0–70; locals `t` = `(Tuple) obj`, `i`)
```
 0/4: instanceof Tuple ; ifne -> 9 ; else iconst_0/ireturn
 9–13: t = (Tuple) obj
14–16: i = 0 ; goto 58
19–50: this.fields.get(i).getValue().equals( t.getFields().get(i).getValue() ) ; ifeq -> iconst_0/ireturn
55:    iinc i,1
58–66: i < this.fields.size() ; if_icmplt -> 19
69:    iconst_1
```
⇒ compares **only the `Field.value` strings, position by position**, with the loop bound taken from
`this.fields.size()` (the *receiver*), and `t.getFields().get(i)` indexed with the same `i`.
Not compared: `Field.key`, `row`, `index`, `nullFields`, `nullFieldsCount`, `involvedInLHSCount`, and the two
lists' sizes (a longer receiver throws `IndexOutOfBoundsException` unless the argument is at least as long).
`getValue()` returning `null` throws NPE. Because the test is `instanceof Tuple`, a `SimilarityTuple`
(as subclass) can be `equals`-equal to a plain `Tuple` — see §E for the resulting asymmetry.

### `clone()` — **exactly what is copied and what is shared**
Real method (the `clone()Ljava/lang/Object;` at index 14 is only the synthetic bridge `aload_0; invokevirtual Tuple.clone()LTuple; areturn`, access `0x1041`):

```
=== METHOD clone()LTuple; (access 0x1, throws java/lang/CloneNotSupportedException)
    0: new              #1  // Tuple
    3: dup
    4: aload_0
    5: getfield         #24 // Tuple.fields : ObjectArrayList
    8: invokevirtual    #93 // ObjectArrayList.clone()Lit/unimi/dsi/fastutil/objects/ObjectArrayList;
   11: aload_0
   12: getfield         #26 // Tuple.row : I
   15: aload_0
   16: getfield         #28 // Tuple.index : I
   19: invokespecial    #95 // Tuple.<init>(ObjectArrayList;II)V
   22: astore_1                       // Tuple t   (LVT: slot 1 = "t", start=23)
   23: aload_1
   24: aload_0
   25: getfield         #81 // Tuple.nullFields : ObjectArrayList
   28: invokevirtual    #93 // ObjectArrayList.clone()Lit/unimi/dsi/fastutil/objects/ObjectArrayList;
   31: invokevirtual    #97 // Tuple.setNullFields(ObjectArrayList)V
   34: aload_1
   35: aload_0
   36: getfield         #76 // Tuple.nullFieldsCount : I
   39: invokevirtual    #99 // Tuple.setNullFieldsCount(I)V
   42: aload_1
   43: areturn
```

Source-equivalent:

```java
public Tuple clone() throws CloneNotSupportedException {
    Tuple t = new Tuple(this.fields.clone(), this.row, this.index);
    t.setNullFields(this.nullFields.clone());
    t.setNullFieldsCount(this.nullFieldsCount);
    return t;                      // involvedInLHSCount is NOT copied -> 0 in the clone
}
```

What `ObjectArrayList.clone()` does (fastutil, same JAR) — decisive for the sharing question:

```
=== it/unimi/dsi/fastutil/objects/ObjectArrayList.clone()Lit/unimi/dsi/fastutil/objects/ObjectArrayList;
    0: new ObjectArrayList(this.size) ; astore_1
   12: getfield a [Ljava/lang/Object; ; 16: iconst_0 ; 18: c.a ; 21: iconst_0 ; 22: this.size
   26: invokestatic java/lang/System.arraycopy
   29–34: c.size = this.size ; areturn
```
⇒ **new `ObjectArrayList` with a fresh backing array; element references are copied, not the elements.**

Therefore, for `Tuple o` and `Tuple c = o.clone()`:

| structure | original vs clone |
|---|---|
| `fields` list object | **distinct** (`c.fields != o.fields`, distinct backing arrays) |
| the `Field` objects inside `fields` | **SHARED** (`c.fields.get(i) == o.fields.get(i)`) |
| `nullFields` list object | **distinct** (fresh `ObjectArrayList`, fresh backing array) |
| the `Field` objects inside `nullFields` | **SHARED** — and in practice they are exactly the same objects as the corresponding entries of `fields` (see §H: `nullFields.add(f)` adds references) |
| `row`, `index` | copied by value |
| `nullFieldsCount` | copied by value |
| `involvedInLHSCount` | **NOT copied** — the clone's field keeps the constructor default `0` |

Consequences (this is the point flagged in the task):
* **Mutating a `Field` through the clone mutates the original.** `c.getFields().get(i).setValue("X")` or
  `setTimesInvolved(n)` is visible in `o`, because it is the very same object. The same holds for
  `c.getNullFields().get(j)`.
* **Structural edits do not propagate.** `c.getFields().set(i, otherField)` (which is exactly what the filling code
  does — `FillingAlgorithm.populateFieldSingleAttribute` offsets 59–78 performs
  `t.getFields().set(fieldIndex, candidate.getFields().get(fieldIndex))`) replaces the slot only in the clone's
  list; `o` keeps the original reference. Same for `add`/`remove`/`sort` on the lists.
* `Tuple.clone()` declares `CloneNotSupportedException` but cannot throw it (`ObjectArrayList.clone()` has no
  `throws` and no `athrow`), so the checked exception is spurious. It *can* throw `NullPointerException` when
  `this.nullFields == null`, i.e. for a Tuple that never went through the null-field scan, because the
  constructor leaves `nullFields` at `null` while `clone()` calls `nullFields.clone()` unconditionally.
* Call sites: `FillingAlgorithm.localSearchExecution` (offset 207, dataset-wide cloning) and
  `FillingAlgorithm.cloneList` (offset 32) — both inside methods that are **never invoked** (see Context §H).

---

## E. `SimilarityTuple` (`extends Tuple`)

Fields (declaration order): `weightedSimilarity D`, `based LRFD;`, `careAbout Z`, `similarityIndex D`,
`fieldIndex I`. It adds no `hashCode`.

### Constructor `SimilarityTuple(ObjectArrayList, double, int, int, RFD, int)`

LVT is decisive:

```
slot 1  fields           Lit/unimi/dsi/fastutil/objects/ObjectArrayList;
slot 2  similarityIndex  D
slot 4  fieldIndex       I
slot 5  row              I
slot 6  based            LRFD;
slot 7  rowIndex         I
```

Body:
```
    0–6:  aload_1 ; iload 5 ; iload 7 ; invokespecial Tuple.<init>(ObjectArrayList;II)V
          //  super(fields, row, rowIndex)  ->  Tuple.fields=arg1, Tuple.row=arg4, Tuple.index=arg6
   10–11: dload_2 ; putfield #22 // SimilarityTuple.similarityIndex   = arg2
   15–16: dload_2 ; putfield #24 // SimilarityTuple.weightedSimilarity = arg2   (same value initially)
   20–22: iload 4 ; putfield #26 // SimilarityTuple.fieldIndex        = arg3
   26–27: iconst_1 ; putfield #28 // SimilarityTuple.careAbout        = true
   31–33: aload 6 ; putfield #30 // SimilarityTuple.based             = arg5
```
⇒ `SimilarityTuple(ObjectArrayList fields, double similarityIndex, int fieldIndex, int row, RFD based, int rowIndex)`
with `arg6 (rowIndex)` stored into the inherited `Tuple.index`.
Construction site `FillingAlgorithm.getCandidatesForField` offsets 809–835:

```
new SimilarityTuple( tuple.getFields(),          // arg1 – the source tuple's list, NOT cloned
                     bestScore,                  // arg2 – accumulated weight / rfd.getLHS().size()
                     rfd.getRHS().getIndex(),    // arg3
                     tuple.getRow(),             // arg4
                     bestRFD,                    // arg5
                     tuple.getIndex())           // arg6
```
Note: the candidate **shares the whole `fields` list object** of the database tuple.

### Methods
* `getWeightedSimilarity()D`, `setWeightedSimilarity(D)V`.
* `addNewWeight(double w)`: `this.weightedSimilarity += w` (offsets 0–10: `aload_0; dup; getfield; dload_1; dadd; putfield`). It touches `weightedSimilarity` only — never `similarityIndex`.
* `setCareAbout(Z)V`, `getCareAbout()Z`.
* `getSimilarityIndex()D` (no setter).
* `getFieldIndexSingleAttribute()I` (getter for `fieldIndex`) and `setFieldIndex(I)V`.
* `getBased()RFD` (no setter).

### `toString()` (offsets 0–48), literals `cp#56 'SimilarityTuple [fields= '`, `cp#69 'weightedSimilarity='`,
`cp#77 ', fieldIndex='`, `cp#82 ']'`
⇒ `"SimilarityTuple [fields= " + getFields() + "weightedSimilarity=" + weightedSimilarity + ", fieldIndex=" + fieldIndex + "]"`
(note: one space after `fields=`, **no** space after `weightedSimilarity=` or before `]`).
Matches the Results file verbatim, e.g.
`SimilarityTuple [fields= [ID:E14 , RIVER:M , … ]weightedSimilarity=0.0, fieldIndex=11]`.

### `equals(Object)` (offsets 0–70)
Byte-for-byte the same shape as `Tuple.equals`, except the first test is
`instanceof SimilarityTuple` (offset 1, `checkcast SimilarityTuple` at 10), and the comparison is again only
`this.getFields().get(i).getValue().equals(t.getFields().get(i).getValue())` for
`i < this.getFields().size()`. `weightedSimilarity`, `similarityIndex`, `fieldIndex`, `careAbout`, `based`,
`row`, `index` are **not** compared. Since `Tuple.equals` accepts any `Tuple` while `SimilarityTuple.equals`
requires a `SimilarityTuple`, the two implementations are **not symmetric** (`tuple.equals(simTuple)` may be
`true` while `simTuple.equals(tuple)` is `false`).

---

## F. Comparators

All five classes implement `java/util/Comparator`; each also carries the synthetic bridge
`compare(Ljava/lang/Object;Ljava/lang/Object;)I` (access `0x1041`) that simply `checkcast`s and forwards, so only
the typed method matters. None of them define an explicit tie-breaker: ties return `0`.

### F.1 `SimilarityComparator.compare(SimilarityTuple, SimilarityTuple)` — ASCENDING on `similarityIndex`
```
    0–8:  a.getSimilarityIndex() ; b.getSimilarityIndex() ; dcmpl ; ifle -> 14
   12–13: iconst_1 ; ireturn                       // a > b  ->  1
   14–22: a.getSimilarityIndex() ; b.getSimilarityIndex() ; dcmpg ; ifge -> 28
   26–27: iconst_m1 ; ireturn                      // a < b  -> -1
   28–29: iconst_0 ; ireturn                       // equal (or NaN) -> 0
```
⇒ `a.getSimilarityIndex() < b.getSimilarityIndex() ? -1 : (a > b ? 1 : 0)`; **ascending** (smaller index sorts
first). `dcmpl`/`dcmpg` pair makes a NaN comparison return `0`. No tie-break.
**Never instantiated anywhere in the JAR** (no `new SimilarityComparator` in any class; `FillingAlgorithm`'s
constant pool contains only `WeightedSimilarityComparator`, `NullValueComparator`, `TimesInvolvedComparator`) — dead code.

### F.2 `WeightedSimilarityComparator.compare(SimilarityTuple, SimilarityTuple)` — ASCENDING on `weightedSimilarity`
Identical instruction sequence (offsets 0–29) with `getWeightedSimilarity()` instead of `getSimilarityIndex()`.
**Ascending**, ties (and NaN) → `0`.
Used once, `FillingAlgorithm.localSearchExecution` offset 759: `Collections.sort(list, new WeightedSimilarityComparator())`
(`java/util/Collections.sort` — stable), after each element was rescaled by
`st.setWeightedSimilarity(st.getWeightedSimilarity() / (double) list.size())` (offsets 670–683). The consuming code
then takes element `0` (`list.get(0).getFieldIndexSingleAttribute()`, offset 785) ⇒ the **smallest** weighted
similarity wins (the Results file header note in `README.txt`: "the distance score (lower is better)").

### F.3 `RHSThresholdComparator.compare(RFD, RFD)` — ASCENDING on `RHS.getThreshold()`, truncated to `int`
```
    0–14: a.getRHS().getColumn…getThreshold() ; b.getRHS().getThreshold() ; dsub ; d2i ; ireturn
```
The whole method is `(int)(a.getRHS().getThreshold() - b.getRHS().getThreshold())` — **`d2i` truncates toward
zero**, so any pair of thresholds less than 1.0 apart compares as `0` (e.g. `0.9` vs `0.1` → `0`), NaN → `0`, and
out-of-range differences saturate at `±Integer.MAX_VALUE`. This also makes the comparator **non-transitive**
(`a=1.9,b=1.0,c=0.1`: `compare(a,b)=0`, `compare(b,c)=0`, but `compare(a,c)=1`), which violates the
`Comparator` contract. Ascending order, ties → `0`.
**Never referenced by any class** (no constant-pool reference outside its own class file) — dead code.

### F.4 `FillingAlgorithm$NullValueComparator.compare(Tuple, Tuple)` — DESCENDING on `nullFieldsCount`
```
    0: iconst_m1
    1–9: a.getNullFieldsCount() ; b.getNullFieldsCount() ; isub ; imul ; ireturn
```
i.e. `-1 * (a.nullFieldsCount - b.nullFieldsCount) == b.nullFieldsCount - a.nullFieldsCount` ⇒ a tuple with a
**larger** `nullFieldsCount` sorts **earlier** (negative result). The `-1 *` makes this the opposite of the
"obvious" reading; the bytecode is unambiguous (`iconst_m1` precedes the subtraction, `imul` after it), so the
order really is descending: more missing cells first. Overflow is impossible for realistic counts. Ties → `0`.
Used once, `nullValueBasedOrderExecution` offset 183: `tuplesToFill.sort(new NullValueComparator())`
(`ObjectArrayList` declares no `sort`; the call resolves to the `java.util.List.sort(Comparator)` default method,
which is `toArray` + `Arrays.sort(Object[])` = stable TimSort) ⇒ ties keep dataset order. That method is never
invoked (see Context §H).

### F.5 `FillingAlgorithm$TimesInvolvedComparator.compare(Tuple, Tuple)` — ASCENDING on `involvedInLHSCount`
```
    0–8: a.getInvolvedInLHSCount() ; b.getInvolvedInLHSCount() ; isub ; ireturn
```
⇒ ascending: the tuple whose null fields appear in the fewest LHSs first. Ties → `0` (stable sort keeps the
dataset order). Used once, `timesInvolvedInLHSBasedOrderExecution` offset 368:
`tuplesToFill.sort(new TimesInvolvedComparator())` (same `List.sort` default ⇒ stable). Method never invoked.
Note this comparator reads `Tuple.involvedInLHSCount`, **not** `Field.timesInvolved`; the per-field
`getTimesInvolved()` values are only used to compute the tuple-level maximum in that same method (offsets 186–251:
`max = max over nullFields of f.getTimesInvolved()`, initialised to `-1`, then `Tuple.setInvolvedInLHSCount(max)`).

**Sorting/stability summary.** `ObjectArrayList` (fastutil 8) declares no `sort`, and neither do
`AbstractObjectList`/`ObjectList`; therefore `list.sort(comp)` is `java.util.List.sort`, and
`Collections.sort` delegates to it as well ⇒ all three real usages are **stable** sorts, so comparator ties are
broken by the pre-sort order (dataset order for F.4/F.5, insertion order of candidate tuples for F.2).

---

## G. `LevensteinDistance.levenshtein3(Object, Object, double) : int`

Class `LevensteinDistance` has **no fields** and exactly two methods: `<init>()V` and the static `levenshtein3`
(access `0x0009`). There is no `levenshtein1`/`levenshtein2` in the bytecode — only the name of this third
variant survives (an unused `private` sibling would still have been compiled into the class file, so versions 1
and 2 simply do not exist in this build).

### Complete method body (74 bytes) and its local variable table

LVT: `slot 0 firstElement Ljava/lang/Object;`, `slot 1 secondElement Ljava/lang/Object;`,
`slot 2 threshold D`, `slot 4 lhs Ljava/lang/CharSequence;` (start=6), `slot 5 rhs Ljava/lang/CharSequence;`
(start=12), `slot 6 thr I` (start=16). ⇒ parameter names `firstElement`, `secondElement`, `threshold`.

```
    0: aload_0
    1: checkcast        #16 // java/lang/CharSequence
    4: astore           4              // lhs = (CharSequence) firstElement
    6: aload_1
    7: checkcast        #16 // java/lang/CharSequence
   10: astore           5              // rhs = (CharSequence) secondElement
   12: dload_2
   13: d2i
   14: istore           6              // thr = (int) threshold
   16: aload_0
   17: ifnull           -> 24          // firstElement == null
   20: aload_1
   21: ifnonnull        -> 27
   24: ldc              #18 // int 2147483647
   26: ireturn                          // return Integer.MAX_VALUE
   27: aload           4
   29: invokeinterface  #19 // java/lang/CharSequence.length.()I
   34: aload           5
   36: invokeinterface  #19 // java/lang/CharSequence.length.()I
   41: isub                               // len(lhs) - len(rhs)
   42: invokestatic     #23 // java/lang/Math.abs.(I)I
   45: iload           6                  // thr
   47: if_icmple        -> 66             // if |Δlen| <= thr  -> compute real distance
   50: aload           4
   52: invokeinterface  #19 // length
   57: aload           5
   59: invokeinterface  #19 // length
   64: iadd
   65: ireturn                            // return len(lhs) + len(rhs)
   66: aload           4
   68: aload           5
   70: invokestatic     #29 // org/apache/commons/lang3/StringUtils.getLevenshteinDistance.(Ljava/lang/CharSequence;Ljava/lang/CharSequence;)I
   73: ireturn
```
Constant pool: `cp#18 Integer 2147483647` (the class contains exactly one numeric constant, this int; there is no
double constant in `LevensteinDistance`). The only other CP references are `java/lang/CharSequence.length()I`,
`java/lang/Math.abs(I)I` and `StringUtils.getLevenshteinDistance(CharSequence,CharSequence)I`.

Reconstruction:

```java
public static int levenshtein3(Object firstElement, Object secondElement, double threshold) {
    CharSequence lhs = (CharSequence) firstElement;   // unconditional casts, performed before the null test
    CharSequence rhs = (CharSequence) secondElement;
    int thr = (int) threshold;                        // d2i: truncation toward zero; NaN -> 0
    if (firstElement == null || secondElement == null) return Integer.MAX_VALUE;
    if (Math.abs(lhs.length() - rhs.length()) > thr) return lhs.length() + rhs.length();
    return StringUtils.getLevenshteinDistance(lhs, rhs);
}
```

### Algorithm
For the non-degenerate path the method delegates to commons-lang3 3.12.0
`StringUtils.getLevenshteinDistance(CharSequence, CharSequence)` — the classic unit-cost Levenshtein
(insert/delete/substitute, **no** transposition, **no** case folding, `char`-by-`char` comparison), i.e.

```java
if (s == null || t == null) throw new IllegalArgumentException("Strings must not be null");
int n = s.length(), m = t.length();
if (n == 0) return m; else if (m == 0) return n;
if (n > m) { swap(s,t); n = m; m = t.length(); }        // 0x2c–0x74 of that method
int[] p = new int[n+1];  for (i=0..n) p[i] = i;         // 0x42–0x5f
for (int j = 1; j <= m; j++) {                          // 0x60–0xd6
    char t_j = t.charAt(j-1); int p_j = p[0]; p[0] = j;
    for (int i = 1; i <= n; i++) {
        int p_i = p[i];
        int cost = (s.charAt(i-1) == t_j) ? 0 : 1;
        p[i] = Math.min(Math.min(p[i-1]+1, p[i]+1), p_j + cost);
        p_j = p_i;
    }
}
return p[n];
```
(This is the 2-argument overload; the 3-argument `getLevenshteinDistance(CharSequence,CharSequence,int)` with the
`-1` sentinel also exists in the bundled jar but is **not** called by `levenshtein3`.)

### Role of the third `double` parameter — a *length-difference* bound, not a distance bound
* It is cast to `int` **once, before any check** (`d2i`, offsets 12–14): fractional thresholds are truncated
  (`0.9 → 0`), `NaN → 0`, and values outside `int` range saturate.
* It is used **only** at offsets 45–47: `if (Math.abs(lhs.length() - rhs.length()) > thr) return lhs.length() + lhs.length()`.
  It never prunes on the computed edit distance (the commons-lang3 2-arg routine is unthresholded and always
  computes the full DP table).
* **Return values / sentinels**
  1. `Integer.MAX_VALUE` (`2147483647`) if `firstElement == null || secondElement == null` (offsets 16–26). Note
     the null test is performed on the *original* references (`aload_0`/`aload_1`), after the casts, so a null
     argument does not throw: `checkcast` accepts `null`.
  2. `lhs.length() + rhs.length()` if the length difference exceeds `thr` (offsets 50–65). This is the
     "delete everything, insert everything" upper bound on the true edit distance, i.e. "definitely farther than
     the threshold" — the caller rejects it because it is `> thr`.
  3. Otherwise the exact Levenshtein distance (`>= 0`).
  There is **no negative sentinel** in this build.
* Degenerate cases: `(int)` of a negative threshold makes the test `|Δlen| > thr` true for every pair, so the
  method returns `len1+len2` without computing the distance; a huge threshold (`>= 2^31-1`, e.g. the literal used
  in `calculatePattern`) disables the prune entirely.

### Exact meaning of the returned `int`
The minimum number of single-character insertions, deletions or substitutions needed to turn the first string into
the second (standard Levenshtein edit distance over UTF-16 code units, `charAt`, case-sensitive), or one of the two
sentinels above. It is an integer count, and callers compare it directly against `Column.getThreshold()` (a
`double`) after an `i2d` widening. It is symmetric in its two string arguments.

### Dispatch on runtime type / column type — **there is none inside `levenshtein3`**
`levenshtein3` begins with two *unconditional* `checkcast java/lang/CharSequence` (offsets 1 and 7) and no
`instanceof`/`getClass`/branch on types. There is no numeric branch, no `Double.parseDouble`, no char handling and
no knowledge of `'D'`/`'C'`/`'B'` inside the method. Its constant pool (48 slots) contains **zero `CONSTANT_String`
entries** and exactly **one numeric constant** (`cp#18 Integer 2147483647`); the only `Utf8` entries of length ≤ 3
are `'()V'`, `'()I'`, `'abs'`, `'D'`, `'I'` (descriptor/method-name letters) and the LVT names `'lhs'`, `'rhs'`,
`'thr'`. All type dispatch lives in the callers
(`FillingAlgorithm`), and **every one of the 7 call sites passes two `String`s** obtained from
`Field.getValue()` (`Ljava/lang/String;` implements `CharSequence`), so the casts never fail in this program.
Passing a non-`CharSequence` object (e.g. a boxed number) would throw `ClassCastException`.

### The 7 call sites (all in `FillingAlgorithm`; `levenshtein3` is called nowhere else)

| # | method / pc | operands | post-processing of the result | protected range → handler |
|---|---|---|---|---|
| 1 | `revaluateKeyRFDs` 308 (LHS column loop) | `f1.getValue(), f2.getValue(), Column.getThreshold()` | `int d; if (d < 0) skip; if ((double)d > thr) skip; else matched++` (`iflt` 315, `dcmpg`/`ifgt` 327) | `[146,288) → 291` |
| 2 | `revaluateKeyRFDs` 488 (RHS) | `f1.getValue(), f2.getValue(), RFD.getRHS().getThreshold()` | `if (d <= 0) skip; if (d > thr) skip; else count++` (`ifle` 495) | `[432,466) → 469` |
| 3 | `isKeyRfd` 287 (LHS) | `f1.getValue(), f2.getValue(), Column.getThreshold()` | `if (d < 0) skip; if (d > thr) skip; else count++` | `[125,267) → 270` |
| 4 | `isKeyRfd` 479 (RHS) | RHS values + `RFD.getRHS().getThreshold()` | `if (d <= 0) return -1; if (d > thr) return -1; else count++` (`ifle` 486) | `[421,458) → 460` |
| 5 | `areThereTuplesViolatingRFD` 281 (LHS) | `f1.getValue(), f2.getValue(), Column.getThreshold()` | `if (d < 0) skip; if (d > thr) skip; else matched++` | `[119,261) → 264` |
| 6 | `areThereTuplesViolatingRFD` 456 (RHS) | RHS values + `RFD.getRHS().getThreshold()` | `if (d < 0) return true; if (d > thr) return true; else continue` (`iflt` 463) | `[404,435) → 437` |
| 7 | `calculatePattern` 309 (per-attribute pattern) | `f1.getValue(), f2.getValue(), 2147483647.0` (`ldc2_w #824`, `cp#824 Double 2147483647.0`) | `if (d < 0) leave pattern[i] null; else pattern[i] = (double) d` | `[142,291) → 294` |

Notes on these sites:
* The exception handlers catch **`java.lang.RuntimeException`** (exception-table entries, not
  `NumberFormatException` specifically) and the protected ranges cover the whole type-dispatch block, not just
  `Double.parseDouble`. So a `StringIndexOutOfBoundsException` from `charAt(0)` on an empty value, or an NPE from a
  `null` value, also lands in the Levenshtein fallback.
* The `d < 0` tests are **dead code** in this build, since `levenshtein3` never returns a negative value
  (consistent with an older variant that returned `-1`).
* The `d <= 0` tests (sites 2 and 4, RHS) are *live* and mean that two **identical** non-numeric RHS values
  (distance 0, reached only after `parseDouble` failed) are **not** counted as agreeing.

### Column-type dispatch (caller side) and the type-code letters
`FillingAlgorithm` compares a type letter in exactly two places, both by `String.equals` with the literals
`cp#772 'B'` and `cp#774 'C'`:
```
(c.getType().equals("B"))  -> isKeyRfd 125–136, revaluateKeyRFDs 146–157, areThereTuplesViolatingRFD 119–130,
                              getCandidatesForField 282–293
(c.getType().equals("C"))  -> isKeyRfd 175–186, revaluateKeyRFDs 196–207, areThereTuplesViolatingRFD 169–180,
                              getCandidatesForField 344–355
```
The binding for a `'B'` column additionally requires `c.getThreshold() == (double) booleanEqualityThreshold`
(`dcmpl`/`ifne` at 139–150 / 160–171 / 133–144 / 296–307; field `FillingAlgorithm.booleanEqualityThreshold`, an
`int`, set in the constructor from slot 7). The dispatch inside those blocks is:

| type | test | distance used |
|---|---|---|
| `'B'` **and** `threshold == booleanEqualityThreshold` | `f1.getValue().equals(f2.getValue())` | boolean: distance is 0 (match) or "not equal" (no count); no Levenshtein |
| `'B'` but `threshold != booleanEqualityThreshold` | falls through to the numeric block | `Double.parseDouble` of `"true"`/`"false"`/`"M"`/`"F"` throws ⇒ **Levenshtein** with `thr = Column.getThreshold()` |
| `'C'` | `Math.abs(v1.charAt(0) - v2.charAt(0)) <= threshold` (raw UTF-16 code-unit difference of the **first char only**) | char-code distance; Levenshtein is reached only if `charAt(0)` throws (empty string) |
| anything else — **including `'D'`** (no `"D"` test exists) | `Math.abs(Double.parseDouble(v1) - Double.parseDouble(v2)) <= threshold` | numeric; on `RuntimeException` ⇒ **Levenshtein** |

Decisive evidence that `'D'` is *not* tested: the constant pool of `FillingAlgorithm` has `cp#772 String 'B'`,
`cp#774 String 'C'`, `cp#918 String 'E'` (used by `getDigits`), `cp#813 String '-'`, `cp#382 String '?'`, but the
only `Utf8 'D'` (`cp#256`) is a field descriptor letter — there is **no `String 'D'` constant** and no
`ldc`/comparison against `"D"`. The numeric path is therefore the `else` branch. The authors' own
`RENUVER/README.txt` fixes the intended meaning of the letters:

> `- D = any data type: strings, numbers, decimals, etc..`
> `- C = char data type, i.e., attribute values consisting of a single character`
> `- B = boolean attribute values, i.e., attribute values whose value distribution consists of only two possible values (e.g., "M" and "F")`

with the Bridges type list `"D,C,D,D,D,D,D,B,B,D,D,D,D"` (so `RIVER`='C', `CLEAR-G`/`T-OR-D`='B', everything else
'D', including textual `MATERIAL`/`TYPE` columns). This is exactly consistent with the bytecode: for ordinary
string attributes typed `'D'`, `parseDouble` fails and the **Levenshtein** distance is what actually decides the
match.

**`booleanEqualityThreshold` and char data.** It is never applied to `'C'` data and is never passed into
`levenshtein3`. Its only uses are: (i) as the `'B'`-column discriminator above (exact string equality instead of a
distance); (ii) in `calculatePattern` (offsets 171–201) the pattern value for a `'B'` column is
`(double) booleanEqualityThreshold` when the two values are equal, else `(double)(booleanEqualityThreshold + 1)`;
(iii) in `getCandidatesForField` (offsets 296–341) a `'B'` column with `threshold == booleanEqualityThreshold`
contributes `weight += 0.0` and counts as matched when the pattern equals `booleanEqualityThreshold`, otherwise
`weight += 2147483647.0` (a huge penalty) and the match counter is *not* incremented. There is a latent bug in
(ii): the guard is a **reference** comparison —
```
  142: getfield columnTypes ; 146: iload 5 ; 148: aaload ; 149: ldc_w #772 // B
  152: if_acmpne -> 205
```
i.e. `columnTypes[i] != "B"` (`if_acmpne`), not `.equals`. `columnTypes` comes from `args[0].split(",")`
(`Main` 267–275), whose elements are freshly created `String`s and are not interned, so this `'B'` branch is
reachable only if the type string happens to be the interned literal (in practice dead: `'B'` columns then fall
through to the numeric/Levenshtein path in `calculatePattern`). The sibling tests in `getCandidatesForField` and in
the three RFD-checking methods use `.equals("B")` and are unaffected.

### How the threshold/type feed the weighted candidate score (context for G)
`calculatePattern` produces `Double[] pattern` (one entry per attribute position, `-1.0` = "one of the two cells is
missing/non-comparable", `cp#826 Double -1.0`). `getCandidatesForField` (offsets 269–515) then accumulates, per
LHS column `c` with pattern value `p`:
`'B'&threshold==boolEq` → `p==boolEq ? (matched++, +0.0) : (+2147483647.0)`;
`'C'` → `p <= threshold ? (matched++, weight += p) : skip`;
else → `p == -1.0 ? abort : (p <= threshold ? (matched++, weight += scale(p,threshold)) : skip)` with
`scale = p*10^getDigits(threshold)` for `0 < threshold < 1`, `p / 10^(len(String.valueOf((int)threshold))-1)` for
`threshold >= 1`, and `+0.0` for `threshold == 0`. A candidate is kept only when `matched == rfd.getLHS().size()`,
and its score is `weight / rfd.getLHS().size()` (offsets 751–763), keeping the **minimum** over all RFDs
(offsets 765–792). `getDigits(double)` (offsets 0–59) is
`String.valueOf(d).contains("E") ? Integer.parseInt(s.substring(s.indexOf("-")+1)) : s.substring(s.indexOf(".")).length()-1`
(`cp#918 'E'`); for a threshold whose `String.valueOf` contains `E` but no `-` (e.g. `1.0E10`) this throws
`NumberFormatException` that is **not** caught, since `getCandidatesForField` has no exception table.

---

## H. Context — missing-value representation, null counting, and dead code

### `FillingAlgorithm.getDatasetFromFile(String csvPath, String splitChar)`
(throws `FileNotFoundException`; LVT locals `firstLine`, `fieldsName`, `row`, `index`, `line`, `fields`,
`tupleFields`, `i`.) It reads `System.getProperty("user.dir") + File.separator + "Dataset" + File.separator + csvPath`
with a `Scanner`; the first line `line.split(splitChar)` gives `fieldsName` (header); for every later line
`fields = line.split(splitChar)` and
`tupleFields.add(new Field(fieldsName[i], fields[i]))` for `i` in `0 .. fields.length-1`, then
`dataset.add(new Tuple(tupleFields, row, index))` with `row`/`index` post-incremented from 1/0.

Crucially: **there is no conversion of `"?"` (or of any cell) into a null `Field`/null value here.** The literal
string `"?"` is stored as the `Field.value`, and the loop bound is the *row's* field count, not the header's
(a data row longer than the header would throw `ArrayIndexOutOfBoundsException` on `fieldsName[i]`).
`Tuple.nullFields`/`nullFieldsCount` are left untouched (`null`/`0`) by the constructor.

### Where a `"?"` cell becomes a "null field" and how it is counted
Every heuristic performs its own scan with the same shape, e.g. `sequentialExecution` offsets 29–167:

```java
ObjectArrayList nullFields = new ObjectArrayList();
for (Field f : dataset.get(i).getFields()) {
    if (f.getValue().equals("?")) {          // 71–82: getValue().equals("?") ; ifeq -> next
        nullCells++;                         // this.nullCells++  (field #47)
        nullFields.add(f);                   // SAME Field object as in tuple.fields (no copy)
    }
}
if (nullFields.size() > 0) {                 // 112–116
    dataset.get(i).setNullFieldsCount(nullFields.size());   // 130–134
    dataset.get(i).setNullFields(nullFields);               // 148–149
    tuplesToFill.add(dataset.get(i));
}
```
* A "null cell" is exactly a `Field` whose `value` **`String.equals("?")`** (the marker `cp#382 '?'`, the same
  literal that `Main` passes as `rfdNullChar`). A Java `null` value would NPE at `getValue().equals(...)`;
  it never occurs because `Field.value` is always a split token.
* `Tuple.nullFieldsCount` = number of `"?"` cells in the row; `FillingAlgorithm.nullCells` (an `int` field) =
  total number of `"?"` cells seen, accumulated independently in each heuristic and printed at the end as
  `"#Null cells: "`.
* `Tuple.nullFields` holds **references to the very same `Field` objects** that live in `tuple.fields`, so
  `setValue`/`setTimesInvolved` on a null-field element is visible through `tuple.getFields()` and vice versa.
  This is the second reason the shallow `Tuple.clone()` sharing matters (§D).
* `timesInvolvedInLHSBasedOrderExecution` (offsets 80–270) also sets, per `"?"` field,
  `f.setTimesInvolved(countTimeInvolved(f))` (cached per attribute name in an `Object2IntLinkedOpenHashMap`) and
  then `tuple.setInvolvedInLHSCount(max over nullFields)`; `nullFieldsCount` is **not** set by that heuristic.
* `localSearchExecution` (offsets 36–161) performs the same scan and always calls `setNullFieldsCount` /
  `setNullFields` for every tuple (also when the count is 0), which is what makes the later dataset-wide
  `Tuple.clone()` (offset 207) safe w.r.t. the `nullFields == null` NPE noted in §D.
* Filling itself replaces the slot (`populateFieldSingleAttribute` 59–78:
  `t.getFields().set(fieldIndex, candidate.getFields().get(fieldIndex))`); on failure it writes a fresh
  `new Field(key, "?")` back into the slot (offsets 190–221). So filled cells stop being `"?"`, and
  `FillingAlgorithm.notFilledCells` counts tuples/cells left unfilled (`sequentialExecution` 200–206 loops the
  tuples that had nulls and `treatNullTuple` increments `notFilledCells` when no candidate succeeded:
  `treatNullTuple` offsets 175–182; `localSearchExecution` adds the residual count at 863–873).

### `FillingAlgorithm.saveOutputFile()` (no parameters; reads, writes `populatedDataset`)
```
 62–69: populatedDataset.println("riga;nome attributo;valore da imputare;valore imputato")   // cp#331
 72–190: for each line of  user.dir/TupleIniziali/<datasetFilePath>   (cp#329 'TupleIniziali', cp#333 ';')
         row   = Integer.parseInt(line.split(";")[0]);          // 81–94
         key   = line.split(";")[1];                            // 96–106
         Field f = dataset.get(row - 1).getFields().stream()
                        .filter(x -> x.getKey().equals(key))     // invokedynamic lambda$0
                        .findAny().orElse(null);                 // 108–152
         populatedDataset.println(line + ";" + f.getValue());    // 154–187
```
* The `TupleIniziali/<dataset>` file is an **input** (the README: "the tuples whose missing values have been
  randomly injected"; format `row;attribute;expectedValue`), read line by line; only its first two fields are
  used, and the whole original line is echoed, so the output has the 4 columns of the header.
* No `"?"`/null interpretation happens here either — it simply prints `Field.getValue()` of the (possibly
  filled) cell; if no `Field` matches the attribute name, `f` is `null` and `f.getValue()` throws NPE
  (the stream `filter` is `lambda$0(String, Field)` = `field.getKey().equals(name)`).
* `Tuple.getRow()` is 1-based, hence `dataset.get(row - 1)`.

### Dead code relevant to interpretation (verified by constant-pool reference search over all non-library classes)
* `SimilarityComparator` and `RHSThresholdComparator`: **no class references them** (no `Class` constant of theirs
  outside their own class file).
* `Field.clone()`: no caller.
* `FillingAlgorithm.start(int)` **ignores its `int` argument** — between offsets 0 and 163 it never executes a
  load of slot 1 (no `iload_1`, no `iload slot 1`) — and unconditionally performs: remove key RFDs
  (`isKeyRfd`), `createMapOnRHS()`, `sequentialExecution()`, `saveOutputFile()`. The three other heuristics
  (`localSearchExecution`, `nullValueBasedOrderExecution`, `timesInvolvedInLHSBasedOrderExecution`) and therefore
  all three live comparator uses are **never invoked** from anywhere in the JAR, matching the README note
  "In this release, only the sequential heuristic 0 is supported" (the shipped `testrun` output file name
  `…_3H4.txt` even shows a heuristic argument of 4 being ignored).
* No reflection is used anywhere (`Class.forName`/`getMethod`/`invoke` never appear), so these dead methods cannot
  be reached dynamically.

### `Main` (argument plumbing, for reference)
`main(String[])` requires exactly 6 args (`args.length != 6` → print `USAGE` and `System.exit(0)`), builds the three
`PrintWriter`s (`Results/output_<args1>_<args4>H<args5>.txt`, `Logs/log_….txt`,
`Populated/output_….csv`), then
`new FillingAlgorithm(args[1], args[2], args[3], ";", "?", args[0].split(","), Integer.parseInt(args[4]), results, log, populatedDataset)`
and `fa.start(Integer.parseInt(args[5]))`. Constructor LVT names:
`datasetPath, splitChar, rfdPath, rfdSplitChar, rfdNullChar, columnTypes, booleanEqualityThreshold, results, log, populatedDataset`.
