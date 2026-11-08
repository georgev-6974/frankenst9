#!/usr/bin/env python3
# make-0171.py TREE OUT.patch
# s9survey=8: set USI10 (0x1041102C, guess: serves hsi2c@104B0000) to 4 (I2C),
# test write-readback on hsi2c timing regs, then the pin-mux + ACK probe, then restore.
# Needs a clean tree (git -C TREE commit -am 0170 first). UNTESTED, not built.
import subprocess, sys, pathlib

tree = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()

if subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                  capture_output=True, text=True, check=True).stdout.strip():
    sys.exit("tree not clean: git -C %s commit -am '0170'" % tree)

f = tree / "bsd/dev/a5xelte_touch.c"
s = f.read_text()
if "level == 7" not in s:
    sys.exit("0170 not in this tree")
if "level == 8" in s:
    sys.exit("0171 already applied")

anchor = "\tfor (unsigned i = 0; i < 64; i++) {\n\t\tprev[i] = a5touch_read(aon, i * 4);\n\t}\n"
if s.count(anchor) != 1:
    sys.exit("watch-loop anchor: found %d" % s.count(anchor))

block = '''\tif (level == 8) {
\t\tvm_offset_t i2c = ml_io_map(S9_I2C_PA, 0x1000);
\t\tvm_offset_t usi = ml_io_map(0x10411000, 0x1000);
\t\tuint8_t b[3] = { 0, 0, 0 };
\t\tuint32_t u0 = 0xdead;
\t\tif (!i2c || !usi) {
\t\t\tprintf("S9SURVEY P8: mapping failed\\n");
\t\t} else if (s9_probe_read32(usi + 0x2c, &u0)) {
\t\t\tprintf("S9SURVEY P8: usi10 read faulted\\n");
\t\t} else {
\t\t\tuint32_t u1 = 0, rb = 0;
\t\t\tuint32_t con = a5touch_read(pin, 0x20);
\t\t\tuint32_t pud = a5touch_read(pin, 0x28);
\t\t\tprintf("S9SURVEY P8 usi10 before: %08x\\n", u0);
\t\t\ta5touch_write(usi, 0x2c, 4);
\t\t\tif (s9_probe_read32(usi + 0x2c, &u1)) {
\t\t\t\tu1 = 0xbad;
\t\t\t}
\t\t\tprintf("S9SURVEY P8 usi10 after write 4: %08x\\n", u1);
\t\t\ta5touch_write(i2c, 0x60, 0x01020304u);
\t\t\trb = a5touch_read(i2c, 0x60);
\t\t\tprintf("S9SURVEY P8 hsi2c +60 wrote 01020304 read %08x\\n", rb);
\t\t\ta5touch_write(i2c, 0x60, 0);
\t\t\ta5touch_write(pin, 0x20, (con & ~0x00ff0000u) | 0x00220000u);
\t\t\ta5touch_write(pin, 0x28, pud & ~0x00ff0000u);
\t\t\ts9i2c_reset(i2c);
\t\t\ts9survey_pdump("P8 i2c", i2c, 0x80);
\t\t\tif (s9i2c_cmd_read(i2c, 0x55, b, 1)) {
\t\t\t\tprintf("S9SURVEY P8: chip ACKed at 0x48, cmd 0x55 -> %02x\\n", b[0]);
\t\t\t} else {
\t\t\t\tprintf("S9SURVEY P8: no ACK from 0x48\\n");
\t\t\t}
\t\t\tprintf("S9SURVEY P8 gpp1 DAT %08x\\n", a5touch_read(pin, 0x24));
\t\t\ta5touch_write(pin, 0x20, con);
\t\t\ta5touch_write(pin, 0x28, pud);
\t\t\ta5touch_write(usi, 0x2c, u0);
\t\t\tprintf("S9SURVEY P8: restored usi10 and pins\\n");
\t\t}
\t}

'''
f.write_text(s.replace(anchor, block + anchor))

diff = subprocess.run(["git", "-C", str(tree), "diff"], capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff")
out.write_text(diff)
print("wrote", out)
