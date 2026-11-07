#!/usr/bin/env python3
"""make-0156: make a5xelte_send_ipi() non-fatal and log GIC target masks (diagnostic).

Why: 0155 boot: cpu 4 reached initCPU, then "Nested panic detected" x3 with panic_caller
a5xelte_send_ipi (pexpert/arm/pe_fiq.c): `panic("a5xelte: GICv2 target CPU%u unavailable")` fires
when a5_gic_cpu_masks[logical] == 0. That panic is NESTED, so the first panic text is hidden.
Now: send_ipi logs "S9IPI: ... dropped" and returns instead of panicking, and pe_init_fiq logs
"S9IPI: CPU<n> mask=<hex>" when a core stores its mask. Expect cpu 4 mask=0x10 if its GIC
CPU-interface id is 4 (the SGI source id seen on screen was 4).

Needs 0155 committed in TREE_DIR:  git -C WORK3/xnu commit -am "0155"
usage: python3 tools/star2lte/make-0156.py TREE_DIR OUT_PATCH
UNTESTED (not compiled).
"""
import subprocess, sys, os

tree, out = sys.argv[1], sys.argv[2]
rel = "pexpert/arm/pe_fiq.c"
path = os.path.join(tree, rel)
src = open(path).read()
if "S9IPI" in src:
    sys.exit("already applied (S9IPI)")

dirty = subprocess.run(["git", "-C", tree, "status", "--porcelain", "--untracked-files=no"],
                       capture_output=True, text=True, check=True).stdout.strip()
if dirty:
    sys.exit("tree has uncommitted changes, commit them first:\n" + dirty)

a1 = '\t\tpanic("a5xelte: GICv2 target CPU%u unavailable", logical);\n'
a2 = "\ta5_gic_cpu_masks[logical] = mask;\n"
for name, a in (("panic", a1), ("mask", a2)):
    if src.count(a) != 1:
        sys.exit("anchor %s not found exactly once (%d)" % (name, src.count(a)))

n1 = ('\t\tkprintf("S9IPI: GICv2 target CPU%u unavailable (mask %x), IPI dropped\\n", logical,\n'
      '\t\t   logical < SWEET_SMP_MAX_CPUS ? (unsigned)a5_gic_cpu_masks[logical] : 0U);\n'
      '\t\treturn;\n')
n2 = a2 + '\tkprintf("S9IPI: CPU%u mask=%x\\n", logical, (unsigned)mask);\n'
src = src.replace(a1, n1).replace(a2, n2)
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
