#!/usr/bin/env python3
# make-0176.py TREE OUT.patch
# s9survey=14: GPIO pull test on gpp1-4/5 (off/down/up), then I2C probe 0x48 with pull-up ON.
import subprocess, sys, pathlib

tree = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()

if subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                  capture_output=True, text=True, check=True).stdout.strip():
    sys.exit("tree not clean: git -C %s commit -am '0175'" % tree)

f = tree / "bsd/dev/a5xelte_touch.c"
s = f.read_text()
if "level == 13" not in s:
    sys.exit("0175 not in this tree")
if "level == 14" in s:
    sys.exit("0176 already applied")

anchor = "\tfor (unsigned i = 0; i < 64; i++) {\n\t\tprev[i] = a5touch_read(aon, i * 4);\n\t}\n"
if s.count(anchor) != 1:
    sys.exit("watch-loop anchor: found %d" % s.count(anchor))

block = '''\tif (level == 14) {
\t\tvm_offset_t i2c = ml_io_map(S9_I2C_PA, 0x1000);
\t\tvm_offset_t usi = ml_io_map(0x10411000, 0x1000);
\t\tuint8_t b[3] = { 0, 0, 0 };
\t\tuint32_t u0 = 0xdead;
\t\tif (!i2c || !usi) {
\t\t\tprintf("S9SURVEY P14: mapping failed\\n");
\t\t} else if (s9_probe_read32(usi + 0x1c, &u0)) {
\t\t\tprintf("S9SURVEY P14: usi +1c read faulted\\n");
\t\t} else {
\t\t\tuint32_t con = a5touch_read(pin, 0x20);
\t\t\tuint32_t pud = a5touch_read(pin, 0x28);
\t\t\tstatic const uint32_t pulls[3] = { 0, 1, 3 };
\t\t\ta5touch_write(usi, 0x1c, 4);
\t\t\ta5touch_write(pin, 0x20, con & ~0x00ff0000u);
\t\t\tfor (int k = 0; k < 3; k++) {
\t\t\t\ta5touch_write(pin, 0x28, (pud & ~0x00000f00u) | ((pulls[k] * 5u) << 8));
\t\t\t\tfor (volatile int d = 0; d < 2000000; d++) { }
\t\t\t\tprintf("S9SURVEY P14 input pull=%u DAT %08x\\n", pulls[k], a5touch_read(pin, 0x24));
\t\t\t}
\t\t\ta5touch_write(pin, 0x20, (con & ~0x00ff0000u) | 0x00220000u);
\t\t\ta5touch_write(pin, 0x28, (pud & ~0x00000f00u) | 0x00000f00u);
\t\t\tfor (volatile int d = 0; d < 2000000; d++) { }
\t\t\tprintf("S9SURVEY P14 i2c mux, pull-up: DAT %08x\\n", a5touch_read(pin, 0x24));
\t\t\ts9i2c_reset(i2c);
\t\t\tif (s9i2c_cmd_read(i2c, 0x55, b, 1)) {
\t\t\t\tprintf("S9SURVEY P14: chip ACKed at 0x48, cmd 0x55 -> %02x\\n", b[0]);
\t\t\t} else {
\t\t\t\tprintf("S9SURVEY P14: no ACK from 0x48\\n");
\t\t\t}
\t\t\tprintf("S9SURVEY P14 INT_STATUS %08x FIFO_STAT %08x DAT %08x\\n",
\t\t\t    a5touch_read(i2c, 0x24), a5touch_read(i2c, 0x30), a5touch_read(pin, 0x24));
\t\t\ta5touch_write(pin, 0x20, con);
\t\t\ta5touch_write(pin, 0x28, pud);
\t\t\ta5touch_write(usi, 0x1c, u0);
\t\t\tprintf("S9SURVEY P14: restored\\n");
\t\t}
\t}

'''
f.write_text(s.replace(anchor, block + anchor))

diff = subprocess.run(["git", "-C", str(tree), "diff"], capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff")
out.write_text(diff)
print("wrote", out)