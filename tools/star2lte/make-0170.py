#!/usr/bin/env python3
# make-0170.py TREE OUT.patch
# s9survey=7: do writes to hsi2c@104B0000 stick? Writes only timing regs +60..+6c
# (block disabled), reads back, restores. Dumps +c4..+dc before/after with nofault reads.
# Needs a clean tree (git -C TREE commit -am 0169 first). UNTESTED, not built.
import subprocess, sys, pathlib

tree = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()

if subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                  capture_output=True, text=True, check=True).stdout.strip():
    sys.exit("tree not clean: git -C %s commit -am '0169'" % tree)

f = tree / "bsd/dev/a5xelte_touch.c"
s = f.read_text()
if "level == 6" not in s:
    sys.exit("0169 not in this tree")
if "level == 7" in s:
    sys.exit("0170 already applied")

anchor = "\tfor (unsigned i = 0; i < 64; i++) {\n\t\tprev[i] = a5touch_read(aon, i * 4);\n\t}\n"
if s.count(anchor) != 1:
    sys.exit("watch-loop anchor: found %d" % s.count(anchor))

block = '''\tif (level == 7) {
\t\tvm_offset_t i2c = ml_io_map(S9_I2C_PA, 0x1000);
\t\tif (!i2c) {
\t\t\tprintf("S9SURVEY P7: I2C mapping failed\\n");
\t\t} else {
\t\t\tstatic const unsigned offs[4] = { 0x60, 0x64, 0x68, 0x6c };
\t\t\tuint32_t orig[4], rb[4];
\t\t\ts9survey_pdump("P7 before", i2c + 0xc0, 0x20);
\t\t\tfor (unsigned i = 0; i < 4; i++) {
\t\t\t\torig[i] = a5touch_read(i2c, offs[i]);
\t\t\t\ta5touch_write(i2c, offs[i], 0x01020304u + i);
\t\t\t\trb[i] = a5touch_read(i2c, offs[i]);
\t\t\t\tprintf("S9SURVEY P7 +%02x: orig %08x wrote %08x read %08x\\n",
\t\t\t\t    offs[i], orig[i], 0x01020304u + i, rb[i]);
\t\t\t}
\t\t\tfor (unsigned i = 0; i < 4; i++) {
\t\t\t\ta5touch_write(i2c, offs[i], orig[i]);
\t\t\t}
\t\t\ts9survey_pdump("P7 after", i2c + 0xc0, 0x20);
\t\t\tprintf("S9SURVEY P7: restored\\n");
\t\t}
\t}

'''
f.write_text(s.replace(anchor, block + anchor))

diff = subprocess.run(["git", "-C", str(tree), "diff"], capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff")
out.write_text(diff)
print("wrote", out)
