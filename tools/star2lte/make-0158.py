#!/usr/bin/env python3
"""make-0158: log the AArch64 ID registers of every core (diagnostic).

0157 boot (8 cpus): all cores alive, then launchd (pid 1) exits with namespace 2 subcode 0x4
(SIGILL, my reading). Suspect: user space is told the A55's ARMv8.2+ features, the Exynos M3 lacks
some. Linux /proc/cpuinfo hides it (identical Features lines). This prints, per core after the
SCTLR line in initCPU:
  S9ID cpu=N ISAR0=.. ISAR1=.. PFR0=.. MMFR1=.. MMFR2=..
Bits that differ between cpu 0-3 (A55) and cpu 4-7 (M3) must be masked from the commpage.
Registers are read by encoding (S3_0_C0_Cm_o) to avoid name-support problems:
  ISAR0 S3_0_C0_C6_0, ISAR1 S3_0_C0_C6_1, PFR0 S3_0_C0_C4_0, MMFR1 S3_0_C0_C7_1, MMFR2 S3_0_C0_C7_2

Needs 0157 committed in TREE_DIR:  git -C WORK3/xnu commit -am "0157"
usage: python3 tools/star2lte/make-0158.py TREE_DIR OUT_PATCH
UNTESTED (not compiled).
"""
import subprocess, sys, os

tree, out = sys.argv[1], sys.argv[2]
rel = None
for d, _, fs in os.walk(tree):
    if "SweetCPU.cpp" in fs:
        rel = os.path.relpath(os.path.join(d, "SweetCPU.cpp"), tree)
        break
if not rel:
    sys.exit("SweetCPU.cpp not found")
path = os.path.join(tree, rel)
src = open(path).read()
if "S9ID" in src:
    sys.exit("already applied (S9ID)")

dirty = subprocess.run(["git", "-C", tree, "status", "--porcelain", "--untracked-files=no"],
                       capture_output=True, text=True, check=True).stdout.strip()
if dirty:
    sys.exit("tree has uncommitted changes, commit them first:\n" + dirty)

import re
pat = re.compile(r'[ \t]*\(unsigned long long\)__builtin_arm_rsr64\("ACTLR_EL1"\)\);\n')
if len(pat.findall(src)) != 1:
    sys.exit("anchor not found exactly once (%d)" % len(pat.findall(src)))

add = '''\tkprintf(CPU_PORT_NAME " S9ID cpu=%u ISAR0=%llx ISAR1=%llx PFR0=%llx MMFR1=%llx MMFR2=%llx\\n",
\t  getCPUNumber(), (unsigned long long)__builtin_arm_rsr64("S3_0_C0_C6_0"),
\t  (unsigned long long)__builtin_arm_rsr64("S3_0_C0_C6_1"),
\t  (unsigned long long)__builtin_arm_rsr64("S3_0_C0_C4_0"),
\t  (unsigned long long)__builtin_arm_rsr64("S3_0_C0_C7_1"),
\t  (unsigned long long)__builtin_arm_rsr64("S3_0_C0_C7_2"));
'''
m = pat.search(src)
src = src[:m.end()] + add + src[m.end():]
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
