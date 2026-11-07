#!/usr/bin/env python3
"""make-0159: clamp the ID registers read by the commpage code to an ARMv8.0 baseline.

0157 boot (8 cpus): xpcproxy dies with SIGILL (sig 4) at the same pc 0x1d473b588 in 3-4 processes,
then launchd exits and the kernel panics ("initproc exited, namespace 2 subcode 0x4").
Hypothesis (NOT yet measured on the M3): osfmk/arm/commpage/commpage.c builds the user-visible
feature bits (LSE atomics, DotProd, FHM, SHA3, RDM, FP16, JSCVT, FCMA, LRCPC, ...) from the BOOT
core's (A55) ID registers; the Exynos M3 is ARMv8.0 (+ AES/PMULL/SHA1/SHA2/CRC32, same as Linux's
/proc/cpuinfo shows for both). iOS code that uses an advertised feature faults on an M3.

Clamp (only turns features OFF):
  ISAR0 &= 0x11120   (AES=2, SHA1=1, SHA2=1, CRC32=1; atomics/RDM/SHA3/DP/FHM/TS cleared)
  ISAR1  = 0         (DPB/JSCVT/FCMA/LRCPC/SPECRES/... cleared)
  PFR0  &= ~(FP[19:16], AdvSIMD[23:20], RAS[31:28], DIT[51:48])
  PFR1   = 0,  MMFR2 = 0
MMFR0 is left alone.

Needs 0158 committed in TREE_DIR:  git -C WORK3/xnu commit -am "0158"
usage: python3 tools/star2lte/make-0159.py TREE_DIR OUT_PATCH
UNTESTED (not compiled). Applied unconditionally (this tree only builds the S9+ board).
"""
import subprocess, sys, os

tree, out = sys.argv[1], sys.argv[2]
rel = "osfmk/arm/commpage/commpage.c"
path = os.path.join(tree, rel)
src = open(path).read()
if "S9CLAMP" in src:
    sys.exit("already applied (S9CLAMP)")

dirty = subprocess.run(["git", "-C", tree, "status", "--porcelain", "--untracked-files=no"],
                       capture_output=True, text=True, check=True).stdout.strip()
if dirty:
    sys.exit("tree has uncommitted changes, commit them first:\n" + dirty)

edits = [
    ('uint64_t isar0 = __builtin_arm_rsr64("ID_AA64ISAR0_EL1");',
     'uint64_t isar0 = __builtin_arm_rsr64("ID_AA64ISAR0_EL1") & 0x11120ULL; /* S9CLAMP: ARMv8.0 + crypto + crc32 */'),
    ('uint64_t isar1 = __builtin_arm_rsr64("ID_AA64ISAR1_EL1");',
     'uint64_t isar1 = __builtin_arm_rsr64("ID_AA64ISAR1_EL1") & 0ULL; /* S9CLAMP */'),
    ('uint64_t pfr0 = __builtin_arm_rsr64("ID_AA64PFR0_EL1");',
     'uint64_t pfr0 = __builtin_arm_rsr64("ID_AA64PFR0_EL1") &\n\t    ~((0xffULL << 16) | (0xfULL << 28) | (0xfULL << 48)); /* S9CLAMP: no FP16/RAS/DIT */'),
    ('uint64_t pfr1 = __builtin_arm_rsr64("ID_AA64PFR1_EL1");',
     'uint64_t pfr1 = __builtin_arm_rsr64("ID_AA64PFR1_EL1") & 0ULL; /* S9CLAMP */'),
    ('uint64_t mmfr2 = __builtin_arm_rsr64("ID_AA64MMFR2_EL1");',
     'uint64_t mmfr2 = __builtin_arm_rsr64("ID_AA64MMFR2_EL1") & 0ULL; /* S9CLAMP */'),
]
for old, new in edits:
    if src.count(old) != 1:
        sys.exit("anchor not found exactly once (%d): %s" % (src.count(old), old))
    src = src.replace(old, new)
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
