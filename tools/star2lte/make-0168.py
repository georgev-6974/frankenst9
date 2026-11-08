#!/usr/bin/env python3
# make-0168.py TREE OUT.patch
# s9survey=5: READ-ONLY nofault dumps (via s9_probe_read32 from 0167) of
#   hsi2c@104B0000 (0x00-0xff), USI page 0x10411000 (0x00-0x3f), pin block 0x10430000 (0x00-0x1ff).
# A word that aborts prints as "--------". No writes of any kind.
# Looking for: a pin CON word 00220000 (gpp1-4/5 at function 2 = I2C muxed by S-Boot),
# and any non-zero hsi2c10 register.
# Needs a clean tree (git -C TREE commit -am 0167 first). Leaves the edit uncommitted.
# UNTESTED: not built, not run.
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
if "s9survey_pdump" in s:
    sys.exit("0168 already applied")

helper = '''static void
s9survey_pdump(const char *tag, vm_offset_t base, unsigned len)
{
\tfor (unsigned o = 0; o < len; o += 16) {
\t\tchar b[4][12];
\t\tfor (unsigned i = 0; i < 4; i++) {
\t\t\tuint32_t x = 0;
\t\t\tif (s9_probe_read32(base + o + 4 * i, &x)) {
\t\t\t\tsnprintf(b[i], sizeof(b[i]), "--------");
\t\t\t} else {
\t\t\t\tsnprintf(b[i], sizeof(b[i]), "%08x", x);
\t\t\t}
\t\t}
\t\tprintf("S9SURVEY %s +%03x: %s %s %s %s\\n", tag, o, b[0], b[1], b[2], b[3]);
\t}
}

'''
a1 = "static void\ns9i2c_reset(vm_offset_t bus)\n"
if s.count(a1) != 1:
    sys.exit("anchor s9i2c_reset: found %d" % s.count(a1))
s = s.replace(a1, helper + a1)

a2 = '\t\tprintf("S9SURVEY PROBE done\\n");\n\t}\n'
if s.count(a2) != 1:
    sys.exit("anchor PROBE done: found %d" % s.count(a2))
block = '''\tif (level == 5) {
\t\tvm_offset_t i2c5 = ml_io_map(S9_I2C_PA, 0x1000);
\t\tprintf("S9SURVEY P5: read-only dumps, -------- = abort\\n");
\t\tif (i2c5) {
\t\t\ts9survey_pdump("I2C10", i2c5, 0x100);
\t\t}
\t\ts9survey_pdump("USI", usi, 0x40);
\t\ts9survey_pdump("PIN", pin, 0x200);
\t\tprintf("S9SURVEY P5: done\\n");
\t}
'''
s = s.replace(a2, a2 + block)
f.write_text(s)

diff = subprocess.run(["git", "-C", str(tree), "diff"], capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff")
out.write_text(diff)
print("wrote", out)
