#!/usr/bin/env python3
"""make-0154: 0152 read the whole first 16 KiB of the PMU and took a synchronous external abort
(panic: data abort, esr 0x96000010 = DFSC 0x10, far 0xfffffff000abd030, most likely PMU+0x1030).
This limits the snapshot/diff to registers that Samsung's kernel and danstronics' m3 driver read:
  0x414 0x41C 0x500 0x1088 0x2000-0x203C 0x2040 0x2044 0x204C 0x2114 0x2180 0x21EC 0x2258 0x2380 0x2384
(0x2000-0x203C = CLUSTER1 and CLUSTER0 per-core CONFIGURATION/STATUS, per their notes: a CLAIM
for the A55 half.) Everything else is skipped.

Needs 0153 committed in TREE_DIR:  git -C WORK3/xnu commit -am "0153"
usage: python3 tools/star2lte/make-0154.py TREE_DIR OUT_PATCH
UNTESTED (not run on the real tree).
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
if "s9pmu_ok" in src:
    sys.exit("already applied (s9pmu_ok)")
if "S9M3" not in src:
    sys.exit("0153 (S9M3) not in tree: apply/commit 0153 first")

dirty = subprocess.run(["git", "-C", tree, "status", "--porcelain", "--untracked-files=no"],
                       capture_output=True, text=True, check=True).stdout.strip()
if dirty:
    sys.exit("tree has uncommitted changes, commit them first:\n" + dirty)

a_snap = "static uint32_t s9pmu_snap[4096];\n"
a_loop1 = "\t\tfor (int w = 0; w < 4096; w++) {\n\t\t\ts9pmu_snap[w] = s9pmu[w];\n\t\t}\n"
a_loop2 = "\t\t\tuint32_t v = s9pmu[w];\n"
a_done = "done, %d changed (max 40 shown)"
for name, a in (("snap", a_snap), ("loop1", a_loop1), ("loop2", a_loop2), ("done", a_done)):
    if src.count(a) != 1:
        sys.exit("anchor %s not found exactly once (%d)" % (name, src.count(a)))

helper = '''
/* s9pmu_ok: PMU byte offsets known to be readable (0152 aborted reading the whole block) */
static bool
s9pmu_ok(uint32_t o)
{
\treturn o == 0x414 || o == 0x41C || o == 0x500 || o == 0x1088 ||
\t       (o >= 0x2000 && o <= 0x203C) || o == 0x2040 || o == 0x2044 || o == 0x204C ||
\t       o == 0x2114 || o == 0x2180 || o == 0x21EC || o == 0x2258 ||
\t       o == 0x2380 || o == 0x2384;
}
'''
new_loop1 = ("\t\tfor (int w = 0; w < 4096; w++) {\n"
             "\t\t\tif (s9pmu_ok((uint32_t)w * 4)) {\n"
             "\t\t\t\ts9pmu_snap[w] = s9pmu[w];\n"
             "\t\t\t}\n"
             "\t\t}\n")
new_loop2 = ("\t\t\tif (!s9pmu_ok((uint32_t)w * 4)) {\n"
             "\t\t\t\tcontinue;\n"
             "\t\t\t}\n"
             "\t\t\tuint32_t v = s9pmu[w];\n")
src = (src.replace(a_snap, a_snap + helper).replace(a_loop1, new_loop1)
       .replace(a_loop2, new_loop2).replace(a_done, "done, %d changed (max 40, safe-list)"))
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
