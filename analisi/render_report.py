#!/usr/bin/env python3
"""Render the pruning experiment results into the markdown report."""
import os
import json, os, sys, collections

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/results/analisi"
REPORT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/results/analisi/nota_di_render.md"

recs = []
for f in ("experiment.json", "experiment2.json"):
    p = os.path.join(OUT, f)
    if os.path.exists(p):
        try: recs += json.load(open(p))
        except Exception as e: print(f"[warn] {f}: {e}", file=sys.stderr)

groups = collections.OrderedDict()
for r in recs:
    if "family" not in r or "config" not in r:
        continue
    groups.setdefault(r["config"], []).append(r)

def fmt_ms(v):
    if v is None: return "—"
    return f"{v:,}".replace(",", " ") + " ms"

lines = []
for cfg, rs in groups.items():
    rs = [r for r in rs if r.get("rc") == 0]
    if not rs: continue
    base = next((r for r in rs if r["variant"] == "orig"), None)
    fam, ds, rfdf, thr = rs[0]["family"], rs[0]["dsfile"], rs[0]["n_rfd_all"], rs[0]["thr"]
    lines.append(f"\n### {ds} · soglia {thr} · {rfdf} RFD")
    lines.append("")
    lines.append("| variante | RFD | preprocessing | esecuzione | non riempite | corrette | errate | Δ corrette |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in rs:
        d = ""
        if base and r is not base:
            delta = r["n_correct"] - base["n_correct"]
            d = f"{delta:+d}" if delta else "0"
        red = ""
        if base and r is not base:
            red = f" (−{100*(base['n_rfd']-r['n_rfd'])/max(1,base['n_rfd']):.0f}%)"
        lines.append(f"| {r['variant']} | {r['n_rfd']:,}".replace(",", " ") +
                     f"{red} | {fmt_ms(r.get('pre_ms'))} | {fmt_ms(r.get('exec_ms'))} | "
                     f"{r.get('notfilled','—')} | **{r['n_correct']}** | {r['n_wrong']} | {d} |")

block = "\n".join(lines) if lines else "\n*(nessun risultato disponibile)*\n"

# Il blocco generato va inserito al posto del marcatore in un file di nota. Quel file e' un
# artefatto facoltativo: se non c'e' (o non contiene il marcatore) il blocco viene stampato a
# video invece di essere scritto, cosi' lo script non dipende da un file che non esiste.
marker = "<!-- EXPERIMENT2 -->"
if os.path.exists(REPORT) and marker in open(REPORT, encoding="utf-8").read():
    txt = open(REPORT, encoding="utf-8").read().replace(marker, block)
    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write(txt)
    print(f"nota aggiornata ({os.path.basename(REPORT)}) con {len(groups)} configurazioni")
else:
    print(f"[nota] {os.path.relpath(REPORT, os.path.dirname(os.path.dirname(OUT)))} assente o senza marcatore: "
          f"blocco stampato a video ({len(groups)} configurazioni)")
    print(block)
