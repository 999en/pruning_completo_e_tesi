#!/usr/bin/env python3
"""
NOTA SULLA CONSEGNA — questo script e' la documentazione della tecnica di strumentazione usata per
la misura del costo (capitolo 2 della tesi). Lavora su due alberi di sorgenti decompilati
(`src_fix` e `src_instr`) che NON sono inclusi nella cartella: si rigenerano decomprimendo
`RENUVER/RENUVER_EDBT.jar` con un decompilatore (e' stato usato `cfr`). Il risultato della sua
esecuzione sono i due JAR presenti qui accanto: `RENUVER_clean.jar` (ricostruzione equivalente
all'originale) e `RENUVER_instr.jar` (la stessa build con i wrapper di cronometraggio).
Per la misura gia' pronta da rieseguire vedi `esegui_strumentato.sh`; per la prova di equivalenza
vedi `prova_equivalenza.sh`.
"""
from __future__ import annotations

import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src_fix")
DST = os.path.join(HERE, "src_instr")

METHODS = [
    # (nome, tipo di ritorno, argomenti, contatore, campo tempo)
    ("isFaultless", "boolean",
     "Field populated, ObjectArrayList<SimilarityTuple> tupleWithSimilarity, Tuple nullTuple",
     "N_ISFAULTLESS", "T_ISFAULTLESS"),
    ("areThereTuplesViolatingRFD", "boolean",
     "RFD rfd, Tuple populatedTuple",
     "N_ARETHERE", "T_ARETHERE"),
    ("getCandidatesForField", "ObjectArrayList<SimilarityTuple>",
     "Tuple nullTuple, ArrayList<RFD> selectedRFDs",
     "N_CANDIDATES", "T_CANDIDATES"),
]

FIELDS = """
    // ---- strumentazione patch E (solo conteggi e tempi; nessun effetto sulla semantica) ----
    public static long T_ISFAULTLESS = 0L, T_ARETHERE = 0L, T_CANDIDATES = 0L;
    public static long N_ISFAULTLESS = 0L, N_ARETHERE = 0L, N_CANDIDATES = 0L,
                       N_POPULATE = 0L, N_POPULATE_OK = 0L, N_TREATNULL = 0L, N_SCANNED_RFD = 0L;
"""

REPORT = '''
        this.log.println("===== STRUMENTAZIONE (patch E) =====");
        this.log.println("treatNullTuple chiamate: " + N_TREATNULL);
        this.log.println("getCandidatesForField : n=" + N_CANDIDATES
                + "  tempo=" + (T_CANDIDATES / 1000000L) + "ms"
                + "  (" + pct(T_CANDIDATES) + "% del totale strumentato)");
        this.log.println("isFaultless           : n=" + N_ISFAULTLESS
                + "  tempo=" + (T_ISFAULTLESS / 1000000L) + "ms"
                + "  (" + pct(T_ISFAULTLESS) + "% del totale strumentato)");
        this.log.println("  di cui areThereTuplesViolatingRFD: n=" + N_ARETHERE
                + "  tempo=" + (T_ARETHERE / 1000000L) + "ms"
                + "  (" + pct(T_ARETHERE) + "% del totale strumentato)");
        this.log.println("    di cui il controllo del NOME della colonna: "
                + ((T_ISFAULTLESS - T_ARETHERE) / 1000000L) + "ms");
        this.log.println("populateFieldSingleAttribute: n=" + N_POPULATE
                + "  riusciti=" + N_POPULATE_OK);
        this.log.println("totale strumentato: " + ((T_CANDIDATES + T_ISFAULTLESS) / 1000000L) + "ms");
'''

PCT = '''
    private static String pct(long part) {
        long tot = T_CANDIDATES + T_ISFAULTLESS;
        if (tot <= 0L) return "0,0";
        return String.format("%.1f", 100.0 * part / tot);
    }
'''


def main():
    if os.path.isdir(DST):
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)
    path = os.path.join(DST, "FillingAlgorithm.java")
    s = open(path, encoding="utf-8").read()

    # 1) campi statici: inseriti subito dopo la dichiarazione della classe
    m = re.search(r"public class FillingAlgorithm[^{]*\{", s)
    if not m:
        sys.exit("[errore] dichiarazione di classe non trovata")
    s = s[:m.end()] + FIELDS + s[m.end():]

    # 2) wrapper per ciascun metodo
    for name, ret, args, cnt, tfield in METHODS:
        pat = re.compile(
            r"(private\s+)" + re.escape(ret) + r"(\s+)" + re.escape(name) +
            r"(\s*\(" + re.escape(args) + r"\)\s*\{)")
        hits = pat.findall(s)
        if len(hits) != 1:
            sys.exit(f"[errore] {name}: trovate {len(hits)} definizioni, attese 1")
        s = pat.sub(lambda mm: (mm.group(1) + ret + mm.group(2) + name + "_impl" + mm.group(3)), s, count=1)
        wrapper = f'''
    private {ret} {name}({args}) {{
        long __t0 = System.nanoTime();
        try {{
            return {name}_impl({", ".join(a.strip().split()[-1] for a in args.split(","))});
        }} finally {{
            {tfield} += System.nanoTime() - __t0;
            {cnt}++;
        }}
    }}
'''
        s = s[:m.end() + len(FIELDS)] + wrapper + s[m.end() + len(FIELDS):]

    # 3) contatori dei percorsi
    s = s.replace("private void treatNullTuple(Tuple tuple, int index) {",
                  "private void treatNullTuple(Tuple tuple, int index) {\n        N_TREATNULL++;", 1)
    s = s.replace("private boolean populateFieldSingleAttribute(",
                  "private boolean populateFieldSingleAttribute(", 1)
    s = s.replace("        for (RFD rfd : this.allRfd) {",
                  "        for (RFD rfd : this.allRfd) {\n            N_SCANNED_RFD++;", 1)
    # successo di populateFieldSingleAttribute: il corpo ritorna true in un solo punto
    s = s.replace("            this.updatePattern(nullTuple.getRow());\n            return true;",
                  "            this.updatePattern(nullTuple.getRow());\n            N_POPULATE_OK++;\n            return true;", 1)

    # 4) helper pct + report in fondo a sequentialExecution()
    s = s.replace("    private ObjectArrayList<Tuple> localSearchExecution()",
                  PCT + "\n    private ObjectArrayList<Tuple> localSearchExecution()", 1)
    anchor = '        this.log.println("#Cells not filled: " + this.notFilledCells);'
    if anchor not in s:
        sys.exit("[errore] ancora del report non trovata")
    s = s.replace(anchor, anchor + REPORT, 1)

    open(path, "w", encoding="utf-8").write(s)
    print("strumentazione applicata a src_instr/FillingAlgorithm.java")
    print(f"  campi aggiunti: {FIELDS.count('=') } contatori/tempi")
    print(f"  wrapper: {[m[0] for m in METHODS]}")


if __name__ == "__main__":
    main()
