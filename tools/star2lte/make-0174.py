#!/usr/bin/env python3
# make-0174.py TREE OUT.patch
# s9survey=11: for each USI word 0x10411008..0x10411038 (skips +04, it aborts): write 4,
#   test whether hsi2c@104B0000 takes a write (+0x60), restore. On a hit also run the ACK probe.
# s9survey=12: for each of 26 QCH words at CMU_PERIC0 0x10403000.. toggle bit0, test, restore.
# Needs a clean tree (git -C TREE commit -am 0173 first). UNTESTED, not built.
import subprocess, sys, pathlib

tree = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()

if subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                  capture_output=True, text=True, check=True).stdout.strip():
    sys.exit("tree not clean: git -C %s commit -am '0173'" % tree)

f = tree / "bsd/dev/a5xelte_touch.c"
s = f.read_text()
if "level == 10" not in s:
    sys.exit("0173 not in this tree")
if "level == 11" in s:
    sys.exit("0174 already applied")

fn_anchor = "static void\ns9survey_thread(void *arg, wait_result_t result)\n"
if s.count(fn_anchor) != 1:
    sys.exit("fn anchor: found %d" % s.count(fn_anchor))
helper = '''/* Does hsi2c timing reg +0x60 take a write? (block alive) */
static bool
s9i2c_takes_writes(vm_offset_t i2c)
{
\ta5touch_write(i2c, 0x60, 0x01020304u);
\tuint32_t rb = a5touch_read(i2c, 0x60);
\ta5touch_write(i2c, 0x60, 0);
\treturn rb != 0;
}

'''
s = s.replace(fn_anchor, helper + fn_anchor)

anchor = "\tfor (unsigned i = 0; i < 64; i++) {\n\t\tprev[i] = a5touch_read(aon, i * 4);\n\t}\n"
if s.count(anchor) != 1:
    sys.exit("watch-loop anchor: found %d" % s.count(anchor))

block = '''\tif (level == 11) {
\t\tvm_offset_t i2c = ml_io_map(S9_I2C_PA, 0x1000);
\t\tvm_offset_t usi = ml_io_map(0x10411000, 0x1000);
\t\tif (!i2c || !usi) {
\t\t\tprintf("S9SURVEY P11: mapping failed\\n");
\t\t} else {
\t\t\tfor (unsigned o = 0x08; o <= 0x38; o += 4) {
\t\t\t\tuint32_t orig = 0;
\t\t\t\tif (s9_probe_read32(usi + o, &orig)) {
\t\t\t\t\tprintf("S9SURVEY P11 usi +%02x: read faulted\\n", o);
\t\t\t\t\tcontinue;
\t\t\t\t}
\t\t\t\ta5touch_write(usi, o, 4);
\t\t\t\tbool hit = s9i2c_takes_writes(i2c);
\t\t\t\tprintf("S9SURVEY P11 usi +%02x orig %08x -> 4: hsi2c10 %s\\n", o, orig, hit ? "ALIVE" : "dead");
\t\t\t\ta5touch_write(usi, o, orig);
\t\t\t}
\t\t}
\t\tprintf("S9SURVEY P11: done\\n");
\t}
\tif (level == 12) {
\t\tvm_offset_t i2c = ml_io_map(S9_I2C_PA, 0x1000);
\t\tvm_offset_t cmu = ml_io_map(0x10400000, 0x8000);
\t\tif (!i2c || !cmu) {
\t\t\tprintf("S9SURVEY P12: mapping failed\\n");
\t\t} else {
\t\t\tfor (unsigned k = 0; k < 26; k++) {
\t\t\t\tunsigned o = 0x3000 + 4 * k;
\t\t\t\tuint32_t orig = a5touch_read(cmu, o);
\t\t\t\ta5touch_write(cmu, o, orig ^ 1u);
\t\t\t\tbool hit = s9i2c_takes_writes(i2c);
\t\t\t\ta5touch_write(cmu, o, orig);
\t\t\t\tprintf("S9SURVEY P12 qch +%04x (%08x ^1): hsi2c10 %s\\n", o, orig, hit ? "ALIVE" : "dead");
\t\t\t}
\t\t}
\t\tprintf("S9SURVEY P12: done\\n");
\t}

'''
f.write_text(s.replace(anchor, block + anchor))

diff = subprocess.run(["git", "-C", str(tree), "diff"], capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff")
out.write_text(diff)
print("wrote", out)
