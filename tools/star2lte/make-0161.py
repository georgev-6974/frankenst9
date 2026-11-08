#!/usr/bin/env python3
# make-0161.py TREE OUT.patch
# SWEET FBDIAG logged on every swap (~1000/min); log only the first 20 and then every 1000th.
# Needs a clean tree (commit the previous edit first). Leaves the edit uncommitted.
import re, subprocess, sys, pathlib

tree = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()

if subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                  capture_output=True, text=True, check=True).stdout.strip():
    sys.exit("tree not clean: git -C %s commit -am '<previous number>'" % tree)

f = tree / "iokit/Kernel/arm/SweetFramebuffer.cpp"
s = f.read_text()

pat = re.compile(r"(sweet_dbg_n\+\+;\n\s*)if \(1\) \{")
if len(pat.findall(s)) != 1:
    sys.exit("expected exactly one 'sweet_dbg_n++; if (1) {' in %s, found %d" % (f, len(pat.findall(s))))
s = pat.sub(r"\1if (sweet_dbg_n <= 20 || (sweet_dbg_n % 1000) == 0) {", s)
f.write_text(s)

diff = subprocess.run(["git", "-C", str(tree), "diff"], capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff")
out.write_text(diff)
print("wrote", out)
