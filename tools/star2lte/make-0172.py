#!/usr/bin/env python3
# make-0172.py TREE OUT.patch
# s9survey=9: read-only scan with nofault reads: one 16-byte line every 0x200 bytes over
# 0x10400000, 0x10800000, 0x15a80000 (0x8000 each) to find which CMU pages answer.
# Needs a clean tree (git -C TREE commit -am 0171 first). UNTESTED, not built.
import subprocess, sys, pathlib

tree = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()

if subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                  capture_output=True, text=True, check=True).stdout.strip():
    sys.exit("tree not clean: git -C %s commit -am '0171'" % tree)

f = tree / "bsd/dev/a5xelte_touch.c"
s = f.read_text()
if "level == 8" not in s:
    sys.exit("0171 not in this tree")
if "level == 9" in s:
    sys.exit("0172 already applied")

anchor = "\tfor (unsigned i = 0; i < 64; i++) {\n\t\tprev[i] = a5touch_read(aon, i * 4);\n\t}\n"
if s.count(anchor) != 1:
    sys.exit("watch-loop anchor: found %d" % s.count(anchor))

block = '''\tif (level == 9) {
\t\tstatic const uint64_t bases[3] = { 0x10400000, 0x10800000, 0x15a80000 };
\t\tfor (unsigned k = 0; k < 3; k++) {
\t\t\tvm_offset_t m = ml_io_map(bases[k], 0x8000);
\t\t\tchar tag[16];
\t\t\tif (!m) {
\t\t\t\tprintf("S9SURVEY P9 %llx: map failed\\n", bases[k]);
\t\t\t\tcontinue;
\t\t\t}
\t\t\tfor (unsigned o = 0; o < 0x8000; o += 0x200) {
\t\t\t\tsnprintf(tag, sizeof(tag), "P9 %llx", bases[k]);
\t\t\t\ts9survey_pdump(tag, m + o, 0x10);
\t\t\t}
\t\t}
\t\tprintf("S9SURVEY P9: done\\n");
\t}

'''
f.write_text(s.replace(anchor, block + anchor))

diff = subprocess.run(["git", "-C", str(tree), "diff"], capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff")
out.write_text(diff)
print("wrote", out)
