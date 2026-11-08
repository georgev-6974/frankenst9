#!/usr/bin/env python3
# make-0169.py TREE OUT.patch
# s9survey=6: first WRITING survey level. Is the touch chip reachable on I2C 0x48?
#  - sets gpp1-4/5 (pin block 0x10430000 +0x20 CON, +0x28 PUD; bank order from the dts,
#    0x20 stride ASSUMED) to function 2 / no pull, as the dts hsi2c10_bus node says,
#  - s9i2c_reset + the existing cmd reads (0x55 then 0x52) on hsi2c@104B0000,
#  - prints pin words and hsi2c regs before/after, then restores the original pin words.
# No rail, clock or USI writes. Level 3 (USI/PIN reads) is NOT run.
# Needs a clean tree (git -C TREE commit -am 0168 first). Leaves the edit uncommitted.
# UNTESTED: not built, not run. A write into a gated block could raise an async error
# that the 0167 recovery does not catch (panic).
import subprocess, sys, pathlib

tree = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()

if subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                  capture_output=True, text=True, check=True).stdout.strip():
    sys.exit("tree not clean: git -C %s commit -am '<previous number>'" % tree)

f = tree / "bsd/dev/a5xelte_touch.c"
s = f.read_text()
if "s9_probe_read32" not in s:
    sys.exit("0167 not in this tree")
if "level == 6" in s:
    sys.exit("0169 already applied")

anchor = "\tfor (unsigned i = 0; i < 64; i++) {\n\t\tprev[i] = a5touch_read(aon, i * 4);\n\t}\n"
if s.count(anchor) != 1:
    sys.exit("watch-loop anchor: found %d" % s.count(anchor))

block = '''\tif (level == 6) {
\t\tvm_offset_t i2c = ml_io_map(S9_I2C_PA, 0x1000);
\t\tuint8_t b[3] = { 0, 0, 0 };
\t\tif (!i2c) {
\t\t\tprintf("S9SURVEY P6: I2C mapping failed\\n");
\t\t} else {
\t\t\tuint32_t con = a5touch_read(pin, 0x20);
\t\t\tuint32_t pud = a5touch_read(pin, 0x28);
\t\t\tprintf("S9SURVEY P6 gpp1 before: CON %08x DAT %08x PUD %08x\\n",
\t\t\t    con, a5touch_read(pin, 0x24), pud);
\t\t\ta5touch_write(pin, 0x20, (con & ~0x00ff0000u) | 0x00220000u);
\t\t\ta5touch_write(pin, 0x28, pud & ~0x00ff0000u);
\t\t\tprintf("S9SURVEY P6 gpp1 muxed: CON %08x DAT %08x PUD %08x\\n",
\t\t\t    a5touch_read(pin, 0x20), a5touch_read(pin, 0x24), a5touch_read(pin, 0x28));
\t\t\ts9survey_dump("I2C6a", i2c, 0x80);
\t\t\ts9i2c_reset(i2c);
\t\t\tif (s9i2c_cmd_read(i2c, 0x55, b, 1)) {
\t\t\t\tprintf("S9SURVEY P6: chip ACKed at 0x48, cmd 0x55 -> %02x\\n", b[0]);
\t\t\t\tif (s9i2c_cmd_read(i2c, 0x52, b, 3)) {
\t\t\t\t\tprintf("S9SURVEY P6: cmd 0x52 -> %02x %02x %02x\\n", b[0], b[1], b[2]);
\t\t\t\t}
\t\t\t} else {
\t\t\t\tprintf("S9SURVEY P6: no ACK from 0x48 (rails off, USI mode, clock or timing)\\n");
\t\t\t}
\t\t\tprintf("S9SURVEY P6 gpp1 after: DAT %08x\\n", a5touch_read(pin, 0x24));
\t\t\ts9survey_dump("I2C6b", i2c, 0x80);
\t\t\ta5touch_write(pin, 0x20, con);
\t\t\ta5touch_write(pin, 0x28, pud);
\t\t\tprintf("S9SURVEY P6 gpp1 restored: CON %08x PUD %08x\\n",
\t\t\t    a5touch_read(pin, 0x20), a5touch_read(pin, 0x28));
\t\t}
\t}

'''
f.write_text(s.replace(anchor, block + anchor))

diff = subprocess.run(["git", "-C", str(tree), "diff"], capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff")
out.write_text(diff)
print("wrote", out)
