#!/usr/bin/env python3
"""Make xnu/patches/0132-star2lte-sctlr-span.patch from the real tree.
usage: python3 make-0132.py XNU_TREE PATCH_DIR
Edits osfmk/arm64/proc_reg.h (whitespace-insensitive anchors), writes the diff with
git, restores the tree, then git-apply --checks the result."""
import subprocess, sys, os
tree, outdir = sys.argv[1], sys.argv[2]
rel = "osfmk/arm64/proc_reg.h"
p = os.path.join(tree, rel)
lines = open(p).read().split("\n")
if any("SCTLR_S9_SPAN" in l for l in lines):
    sys.exit("already patched: " + p)
d = [i for i, l in enumerate(lines) if l.split()[:2] == ["#define", "SCTLR_EL1_DEFAULT"]]
if len(d) != 1:
    sys.exit("anchor 1 (#define SCTLR_EL1_DEFAULT) found %d times" % len(d))
d = d[0]
e = [i for i in range(d + 1, min(len(lines), d + 12)) if lines[i].split() == ["SCTLR_ROP_KEYS_DEFAULT", "|", "SCTLR_JOP_KEYS_DEFAULT)"]]
if len(e) != 1:
    sys.exit("anchor 2 (last macro line) not found within 12 lines")
e = e[0]
lines[e] = lines[e] + "\n#define SCTLR_EL1_DEFAULT (SCTLR_EL1_DEFAULT_PRE_S9 | SCTLR_S9_SPAN)"
lines[d] = ("/*\n * S9: set SCTLR_EL1.SPAN (bit 23) so PSTATE.PAN is NOT forced to 1 on exception entry.\n"
            " * This build does not define __ARM_PAN_AVAILABLE__, so the copyio code never clears PAN and\n"
            " * every copyin/copyout of a user page takes a permission fault forever. SPAN is RES1 on\n"
            " * cores without PAN (Exynos M3), so this is safe on both clusters.\n */\n"
            "#define SCTLR_S9_SPAN 0x00800000\n#define SCTLR_EL1_DEFAULT_PRE_S9 \\")
open(p, "w").write("\n".join(lines))
diff = subprocess.run(["git", "-C", tree, "diff", "-U3", "--", rel], capture_output=True, text=True, check=True).stdout
subprocess.run(["git", "-C", tree, "checkout", "--", rel], check=True)
if not diff:
    sys.exit("empty diff")
out = os.path.join(outdir, "0132-star2lte-sctlr-span.patch")
open(out, "w").write(diff)
r = subprocess.run(["git", "-C", tree, "apply", "--check", os.path.abspath(out)], capture_output=True, text=True)
print("wrote", out, "| apply --check:", "OK" if r.returncode == 0 else "FAILED " + r.stderr)
