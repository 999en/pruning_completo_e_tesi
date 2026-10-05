#!/usr/bin/env python3
"""Wrapper: run jvmdis_ex.py and resolve relative branch offsets to absolute targets."""
import re, subprocess, sys
args = sys.argv[1:]
out = subprocess.run(["python3", "jvmdis_ex.py"] + args, capture_output=True, text=True)
if out.returncode != 0:
    sys.stderr.write(out.stderr); sys.exit(out.returncode)
lines = out.stdout.split("\n")
cur_pc = 0
for ln in lines:
    m = re.match(r"^\s*(\d+): (\S+)\s*(.*)$", ln)
    if m:
        cur_pc = int(m.group(1))
        mn, arg = m.group(2), m.group(3)
        arg = re.sub(r"-> (-?\d+)(?! \(abs)", lambda mm: "-> %d (abs %d)" % (int(mm.group(1)), cur_pc + int(mm.group(1))), arg)
        arg = re.sub(r"(\{?|, )(-?\d+)->(-?\d+)", lambda mm: "%s%s->%d(abs)" % (mm.group(1), mm.group(2), cur_pc + int(mm.group(3))), arg)
        arg = re.sub(r"default->(-?\d+)", lambda mm: "default->%d(abs)" % (cur_pc + int(mm.group(1))), arg)
        print("%5d: %-16s %s" % (cur_pc, mn, arg))
    else:
        print(ln)
