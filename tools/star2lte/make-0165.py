#!/usr/bin/env python3
# make-0165.py TREE OUT.patch
# Fix for 0164: its first reads (USI page 0x10411000) caused a synchronous external
# abort (esr 0x96000010) on the S9+, i.e. the 0x104xxxxx peripheral block is not
# accessible after S-Boot. Now s9survey=1 and =2 read ONLY the always-on block
# 0x14050000 (keys, touch IRQ pin); USI / pin block / I2C reads need s9survey=3
# and are expected to abort until the block is powered and clocked.
# Needs a clean tree (git -C TREE commit -am 0164 first). Leaves the edit uncommitted.
# UNTESTED: not built by CI, not run on the phone.
import re, subprocess, sys, pathlib

tree = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()

if subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                  capture_output=True, text=True, check=True).stdout.strip():
    sys.exit("tree not clean: git -C %s commit -am '<previous number>'" % tree)

f = tree / "bsd/dev/a5xelte_touch.c"
s = f.read_text()
if "s9survey" not in s:
    sys.exit("0164 (s9survey) not in this tree")
if "S9SURVEY: level >= 3" in s:
    sys.exit("0165 already applied")

# 1. wrap USI + PIN reads in level >= 3
pat1 = re.compile(r'(\tprintf\("S9SURVEY USI modes:.*?\ts9survey_dump\("PIN", pin, 0x100\);\n)', re.S)
m = pat1.findall(s)
if len(m) != 1:
    sys.exit("expected one USI/PIN block, found %d" % len(m))


def wrap(mm):
    body = "".join("\t" + ln if ln.strip() else ln for ln in mm.group(1).splitlines(True))
    return ("\tif (level >= 3) {   /* S9SURVEY: level >= 3 reads the 0x104xxxxx block (aborts if off) */\n"
            + body + "\t}\n")


s = pat1.sub(wrap, s)

# 2. I2C block: level 3 instead of 2
old = "\tif (level >= 2) {\n\t\tvm_offset_t i2c = ml_io_map(S9_I2C_PA, 0x1000);"
if s.count(old) != 1:
    sys.exit("expected one I2C level gate, found %d" % s.count(old))
s = s.replace(old, old.replace("level >= 2", "level >= 3"))

# 3. AON dump stays at level 1/2 (it is above the wrapped block already? make sure order is fine)
f.write_text(s)

diff = subprocess.run(["git", "-C", str(tree), "diff"], capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff")
out.write_text(diff)
print("wrote", out)
