#!/usr/bin/env python3
"""make-0155: reset_vector: map an Exynos M3's real MPIDR to the ADT phys id.

Measured (0154 boot): M3 core 0 woke with MPIDR_EL1 0x80000100 (MT clear, Aff1 = cluster).
A55 core 1 has 0x81000100 -> same low 16 bits (0x0100), so reset_vector's `MPIDR & 0xFFFF`
matches the wrong cpu-data entry for cpu 4. The ADT gives M3 core n the id 0x400 + (n << 8).
CLAIMS (from danstronics' notes, not measured here): M3 MPIDRs are 0x100..0x103 (core in Aff0),
M3 MIDR implementer is 0x53 (MIDR 0x531f0020); A55 is 0x41.

Edit: osfmk/arm64/start.s, right after the SWEET `and x0, x15, #0xFFFF` line.

Needs 0154 committed in TREE_DIR:  git -C WORK3/xnu commit -am "0154"
usage: python3 tools/star2lte/make-0155.py TREE_DIR OUT_PATCH
UNTESTED (not assembled).
"""
import re, subprocess, sys, os

tree, out = sys.argv[1], sys.argv[2]
rel = "osfmk/arm64/start.s"
path = os.path.join(tree, rel)
src = open(path).read()
if "S9M3MPIDR" in src:
    sys.exit("already applied (S9M3MPIDR)")

dirty = subprocess.run(["git", "-C", tree, "status", "--porcelain", "--untracked-files=no"],
                       capture_output=True, text=True, check=True).stdout.strip()
if dirty:
    sys.exit("tree has uncommitted changes, commit them first:\n" + dirty)

pat = re.compile(r"[ \t]*and[ \t]+x0, x15, #0xFFFF[ \t]*// Full Aff1:Aff0 \(SWEET: core in Aff1\)\n")
if len(pat.findall(src)) != 1:
    sys.exit("anchor not found exactly once (%d)" % len(pat.findall(src)))
m = pat.search(src)

ins = ("\t/* S9M3MPIDR: Exynos M3 (MIDR implementer 0x53) has MPIDR 0x100+core (Aff1 = cluster);\n"
       "\t * the ADT phys id is 0x400 + (core << 8). Without this cpu 4 (0x100) matches A55 core 1. */\n"
       "\tmrs\t\tx2, MIDR_EL1\n"
       "\tlsr\t\tx2, x2, #24\n"
       "\tcmp\t\tx2, #0x53\n"
       "\tb.ne\t\tLs9_not_m3\n"
       "\tand\t\tx0, x15, #0xFF\n"
       "\tlsl\t\tx0, x0, #8\n"
       "\tadd\t\tx0, x0, #0x400\n"
       "Ls9_not_m3:\n")
src = src[:m.end()] + ins + src[m.end():]
open(path, "w").write(src)

diff = subprocess.run(["git", "-C", tree, "diff", "--", rel], capture_output=True,
                      text=True, check=True).stdout
if not diff:
    sys.exit("empty diff?")
open(out, "w").write(diff)
chk = subprocess.run(["git", "-C", tree, "apply", "-R", "--check", os.path.abspath(out)],
                     capture_output=True, text=True)
print("hunks:", diff.count("\n@@"), "| reverse-apply check:", "OK" if chk.returncode == 0 else chk.stderr)
print("wrote", out)
