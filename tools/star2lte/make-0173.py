#!/usr/bin/env python3
# make-0173.py TREE OUT.patch
# s9survey=10: read-only dense dump of CMU_PERIC0 (0x10400000) windows with real offsets:
# 0x1000-0x1200, 0x1800-0x1a00, 0x2000-0x2400, 0x3000-0x3800. Nofault reads.
# Needs a clean tree (git -C TREE commit -am 0172 first). UNTESTED, not built.
import subprocess, sys, pathlib

tree = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()

if subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                  capture_output=True, text=True, check=True).stdout.strip():
    sys.exit("tree not clean: git -C %s commit -am '0172'" % tree)

f = tree / "bsd/dev/a5xelte_touch.c"
s = f.read_text()
if "level == 9" not in s:
    sys.exit("0172 not in this tree")
if "level == 10" in s:
    sys.exit("0173 already applied")

anchor = "\tfor (unsigned i = 0; i < 64; i++) {\n\t\tprev[i] = a5touch_read(aon, i * 4);\n\t}\n"
if s.count(anchor) != 1:
    sys.exit("watch-loop anchor: found %d" % s.count(anchor))

block = '''\tif (level == 10) {
\t\tstatic const unsigned win[4][2] = { {0x1000, 0x200}, {0x1800, 0x200}, {0x2000, 0x400}, {0x3000, 0x800} };
\t\tvm_offset_t m = ml_io_map(0x10400000, 0x8000);
\t\tif (!m) {
\t\t\tprintf("S9SURVEY P10: map failed\\n");
\t\t} else {
\t\t\tfor (unsigned k = 0; k < 4; k++) {
\t\t\t\tchar tag[24];
\t\t\t\tsnprintf(tag, sizeof(tag), "P10 w%04x", win[k][0]);
\t\t\t\ts9survey_pdump(tag, m + win[k][0], win[k][1]);
\t\t\t}
\t\t}
\t\tprintf("S9SURVEY P10: done\\n");
\t}

'''
f.write_text(s.replace(anchor, block + anchor))

diff = subprocess.run(["git", "-C", str(tree), "diff"], capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff")
out.write_text(diff)
print("wrote", out)
