#!/usr/bin/env python3
# make-0175.py TREE OUT.patch
# s9survey=13: USI word 0x1041101C = 4 (found by the 0174 sweep), pin-mux gpp1-4/5 to I2C,
# s9i2c_reset, ACK probe of 0x48 (cmd 0x55, 0x52), dump hsi2c regs, restore pins + USI.
# Needs a clean tree (git -C TREE commit -am 0174 first). UNTESTED, not built.
import subprocess, sys, pathlib

tree = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()

if subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                  capture_output=True, text=True, check=True).stdout.strip():
    sys.exit("tree not clean: git -C %s commit -am '0174'" % tree)

f = tree / "bsd/dev/a5xelte_touch.c"
s = f.read_text()
if "level == 11" not in s:
    sys.exit("0174 not in this tree")
if "level == 13" in s:
    sys.exit("0175 already applied")

anchor = "\tfor (unsigned i = 0; i < 64; i++) {\n\t\tprev[i] = a5touch_read(aon, i * 4);\n\t}\n"
if s.count(anchor) != 1:
    sys.exit("watch-loop anchor: found %d" % s.count(anchor))

block = '''\tif (level == 13) {
\t\tvm_offset_t i2c = ml_io_map(S9_I2C_PA, 0x1000);
\t\tvm_offset_t usi = ml_io_map(0x10411000, 0x1000);
\t\tuint8_t b[3] = { 0, 0, 0 };
\t\tuint32_t u0 = 0xdead;
\t\tif (!i2c || !usi) {
\t\t\tprintf("S9SURVEY P13: mapping failed\\n");
\t\t} else if (s9_probe_read32(usi + 0x1c, &u0)) {
\t\t\tprintf("S9SURVEY P13: usi +1c read faulted\\n");
\t\t} else {
\t\t\tuint32_t con = a5touch_read(pin, 0x20);
\t\t\tuint32_t pud = a5touch_read(pin, 0x28);
\t\t\ta5touch_write(usi, 0x1c, 4);
\t\t\ta5touch_write(pin, 0x20, (con & ~0x00ff0000u) | 0x00220000u);
\t\t\ta5touch_write(pin, 0x28, pud & ~0x00ff0000u);
\t\t\tprintf("S9SURVEY P13 usi+1c %08x -> %08x, gpp1 DAT %08x\\n", u0,
\t\t\t    a5touch_read(usi, 0x1c), a5touch_read(pin, 0x24));
\t\t\ts9i2c_reset(i2c);
\t\t\ts9survey_pdump("P13 i2c", i2c, 0x80);
\t\t\tif (s9i2c_cmd_read(i2c, 0x55, b, 1)) {
\t\t\t\tprintf("S9SURVEY P13: chip ACKed at 0x48, cmd 0x55 -> %02x\\n", b[0]);
\t\t\t\tif (s9i2c_cmd_read(i2c, 0x52, b, 3)) {
\t\t\t\t\tprintf("S9SURVEY P13: cmd 0x52 -> %02x %02x %02x\\n", b[0], b[1], b[2]);
\t\t\t\t}
\t\t\t} else {
\t\t\t\tprintf("S9SURVEY P13: no ACK from 0x48\\n");
\t\t\t}
\t\t\ts9survey_pdump("P13 i2c after", i2c, 0x80);
\t\t\tprintf("S9SURVEY P13 gpp1 DAT %08x\\n", a5touch_read(pin, 0x24));
\t\t\ta5touch_write(pin, 0x20, con);
\t\t\ta5touch_write(pin, 0x28, pud);
\t\t\ta5touch_write(usi, 0x1c, u0);
\t\t\tprintf("S9SURVEY P13: restored\\n");
\t\t}
\t}

'''
f.write_text(s.replace(anchor, block + anchor))

diff = subprocess.run(["git", "-C", str(tree), "diff"], capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff")
out.write_text(diff)
print("wrote", out)
