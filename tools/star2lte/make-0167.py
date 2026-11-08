#!/usr/bin/env python3
# make-0167.py TREE OUT.patch
# Nofault MMIO probe for the S9+ survey. 0164 panicked on a synchronous external
# abort (esr 0x96000010) reading 0x104xxxxx. In handle_kernel_abort (sleh.c) such an
# abort is not a VM fault / alignment / parity fault, so it never reaches the copyio
# recovery table (reading of the code, not tested). This patch:
#  1. sleh.c: if fault_code == FSC_SYNC_EXT_ABORT and a recovery entry exists, recover.
#  2. machine_routines_asm.s: s9_probe_read32(addr, *out), a one-load helper with a
#     COPYIO_RECOVER_RANGE (returns 0, or EFAULT on abort), modelled on _bcopyin.
#  3. a5xelte_touch.c: s9survey=4 probes candidate pages through it and logs ok/FAULT.
#     Level 3 now means exactly 3 (it reads USI directly and would still panic).
# Needs a clean tree (git -C TREE commit -am 0166 first). Leaves the edit uncommitted.
# UNTESTED: not built, not run. If the abort does not take the recovery path the
# phone panics exactly like 0164.
import subprocess, sys, pathlib

tree = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()

if subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                  capture_output=True, text=True, check=True).stdout.strip():
    sys.exit("tree not clean: git -C %s commit -am '<previous number>'" % tree)


def edit(path, pairs):
    f = tree / path
    s = f.read_text()
    for old, new in pairs:
        if s.count(old) != 1:
            sys.exit("%s: expected exactly one match, found %d for:\n%s" % (path, s.count(old), old[:90]))
        s = s.replace(old, new)
    f.write_text(s)


if "s9_probe_read32" in (tree / "osfmk/arm64/machine_routines_asm.s").read_text():
    sys.exit("0167 already applied")

# 1. sleh.c
edit("osfmk/arm64/sleh.c", [(
    '\t\tpanic_with_thread_kernel_state("Unexpected abort while on interrupt stack.", state);\n\t}\n',
    '\t\tpanic_with_thread_kernel_state("Unexpected abort while on interrupt stack.", state);\n\t}\n'
    '\n'
    '\t/* S9 (0167): sync external abort inside a recovery range (s9_probe_read32). */\n'
    '\tif (fault_code == FSC_SYNC_EXT_ABORT && recover) {\n'
    '\t\thandle_kernel_abort_recover(state, esr, fault_addr, thread);\n'
    '\t\treturn;\n'
    '\t}\n')])

# 2. asm helper
asm_old = ("#if CONFIG_DTRACE\n/*\n * int dtrace_nofault_copy8(const char *src, uint32_t *dst)\n")
asm_new = (
    "/*\n * int s9_probe_read32(vm_offset_t addr, uint32_t *out)   (patch 0167)\n"
    " * Returns 0, or EFAULT if the load takes an abort.\n */\n"
    "\t.text\n\t.align 2\n\t.globl EXT(s9_probe_read32)\nLEXT(s9_probe_read32)\n"
    "\tARM64_STACK_PROLOG\n\tPUSH_FRAME\n\tCOPYIO_RECOVER_RANGE 1f\n"
    "\tldr\t\tw2, [x0]\n\tstr\t\tw2, [x1]\n1:\n\tmov\t\tx0, #0\n\tPOP_FRAME\n\tARM64_STACK_EPILOG\n\n"
    + asm_old)
edit("osfmk/arm64/machine_routines_asm.s", [(asm_old, asm_new)])

# 3. survey level 4
probe = '''\tif (level == 4) {
\t\tstatic const struct { uint32_t pa; const char *name; } cand[] = {
\t\t\t{ 0x104b0000u, "hsi2c10 (dts)" },
\t\t\t{ 0x10411000u, "usi? (0164 guess)" },
\t\t\t{ 0x10430000u, "pin? (0164 guess)" },
\t\t\t{ 0x15a80000u, "clock-controller (dts)" },
\t\t\t{ 0x10400000u, "peric0 cmu? (guess)" },
\t\t\t{ 0x10800000u, "peric1 cmu? (guess)" },
\t\t};
\t\tstatic const unsigned offs[] = { 0x00, 0x04, 0x08, 0x0c, 0x20, 0x24, 0x40 };
\t\tfor (unsigned c = 0; c < sizeof(cand) / sizeof(cand[0]); c++) {
\t\t\tvm_offset_t m = ml_io_map(cand[c].pa, 0x1000);
\t\t\tprintf("S9SURVEY PROBE %08x %s\\n", cand[c].pa, cand[c].name);
\t\t\tif (!m) {
\t\t\t\tprintf("S9SURVEY PROBE map failed\\n");
\t\t\t\tcontinue;
\t\t\t}
\t\t\tfor (unsigned i = 0; i < sizeof(offs) / sizeof(offs[0]); i++) {
\t\t\t\tuint32_t v = 0;
\t\t\t\tint rc = s9_probe_read32(m + offs[i], &v);
\t\t\t\tprintf("S9SURVEY PROBE %08x+%02x %s %08x\\n", cand[c].pa, offs[i],
\t\t\t\t    rc ? "FAULT" : "ok", rc ? 0u : v);
\t\t\t\tif (rc) {
\t\t\t\t\tbreak;
\t\t\t\t}
\t\t\t}
\t\t}
\t\tprintf("S9SURVEY PROBE done\\n");
\t}

'''
edit("bsd/dev/a5xelte_touch.c", [
    ("#define S9_TS_ADDR      0x48u\n",
     "#define S9_TS_ADDR      0x48u\nextern int s9_probe_read32(vm_offset_t addr, uint32_t *out);\n"),
    ("\tif (level >= 3) {   /* S9SURVEY: level >= 3 reads",
     "\tif (level == 3) {   /* S9SURVEY: level 3 reads"),
    ("\tif (level >= 3) {\n\t\tvm_offset_t i2c = ml_io_map(S9_I2C_PA, 0x1000);",
     probe + "\tif (level == 3) {\n\t\tvm_offset_t i2c = ml_io_map(S9_I2C_PA, 0x1000);"),
])

diff = subprocess.run(["git", "-C", str(tree), "diff"], capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff")
out.write_text(diff)
print("wrote", out)
