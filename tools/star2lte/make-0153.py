#!/usr/bin/env python3
"""make-0153: write the six CLUSTER1 PMU fields before PSCI CPU_ON of the first M3 (cpu 4).

Facts (CLAIMS from danstronics/ios-s9plus-exynos core/drivers/core/hakios.exynos_m3.c, who cite
Samsung's exynos9810 kernel, flexpmu_cal_system_exynos9810.h pmucal_lpm_init, and the mainline
S9+ port; NOT yet measured here). PMU = 0x14060000. Only the masked bits are changed:
  +0x1088 [31:24]=0x8D   +0x2114 [1:0]=2   +0x2180 [1:0]=2
  +0x21EC [1:0]=2        +0x2258 [1:0]=2   +0x2384 [1:0]=2
Each field is read, written, read back and logged:
  S9M3 off=0xOFF OLD->NOW (want NOW)
Their S-Boot readings to compare with: +0x1088 = 0xC7150000, the five OPTION fields = 1.
Then a few state registers are logged: S9M3 st 2000=.. 2004=.. 2040=.. 2044=.. 2380=..
Runs only for cpu 4. Goes before the 0152 PMU snapshot so the S9PMU diff shows what firmware
changes, not our writes.

Needs 0152 committed in TREE_DIR:  git -C WORK3/xnu commit -am "0152"
usage: python3 tools/star2lte/make-0153.py TREE_DIR OUT_PATCH
UNTESTED (not run on the real tree).
"""
import subprocess, sys, os

tree, out = sys.argv[1], sys.argv[2]
rel = None
for d, _, fs in os.walk(tree):
    if "SweetCPU.cpp" in fs:
        rel = os.path.relpath(os.path.join(d, "SweetCPU.cpp"), tree)
        break
if not rel:
    sys.exit("SweetCPU.cpp not found")
path = os.path.join(tree, rel)
src = open(path).read()
if "S9M3" in src:
    sys.exit("already applied (S9M3)")
if "S9PMU" not in src:
    sys.exit("0152 (S9PMU) not in tree: apply/commit 0152 first")

dirty = subprocess.run(["git", "-C", tree, "status", "--porcelain", "--untracked-files=no"],
                       capture_output=True, text=True, check=True).stdout.strip()
if dirty:
    sys.exit("tree has uncommitted changes, commit them first:\n" + dirty)

anchor = "\tvolatile uint32_t *s9pmu = NULL;\n"
if src.count(anchor) != 1:
    sys.exit("anchor not found exactly once (%d)" % src.count(anchor))

block = '''\tif (getCPUNumber() == 4) {
\t\t/* S9M3: Samsung's pmucal_lpm_init CLUSTER1 fields, before the first M3 CPU_ON */
\t\tstatic const uint32_t m3off[6] = { 0x1088, 0x2114, 0x2180, 0x21EC, 0x2258, 0x2384 };
\t\tstatic const uint32_t m3mask[6] = { 0xFF000000u, 3u, 3u, 3u, 3u, 3u };
\t\tstatic const uint32_t m3val[6] = { 0x8D000000u, 2u, 2u, 2u, 2u, 2u };
\t\tvolatile uint8_t *pm = (volatile uint8_t *)ml_io_map(0x14060000ULL, 0x3000);
\t\tfor (int i = 0; i < 6; i++) {
\t\t\tvolatile uint32_t *r = (volatile uint32_t *)(pm + m3off[i]);
\t\t\tuint32_t old = *r;
\t\t\t*r = (old & ~m3mask[i]) | m3val[i];
\t\t\t__builtin_arm_dsb(DSB_SY);
\t\t\tuint32_t now = *r;
\t\t\tIOLog(CPU_PORT_NAME " S9M3 off=0x%x %x->%x (want %x)\\n", (unsigned)m3off[i],
\t\t\t   (unsigned)old, (unsigned)now, (unsigned)((old & ~m3mask[i]) | m3val[i]));
\t\t}
\t\tIOLog(CPU_PORT_NAME " S9M3 st 2000=%x 2004=%x 2040=%x 2044=%x 2380=%x\\n",
\t\t   (unsigned)*(volatile uint32_t *)(pm + 0x2000), (unsigned)*(volatile uint32_t *)(pm + 0x2004),
\t\t   (unsigned)*(volatile uint32_t *)(pm + 0x2040), (unsigned)*(volatile uint32_t *)(pm + 0x2044),
\t\t   (unsigned)*(volatile uint32_t *)(pm + 0x2380));
\t}
'''
src = src.replace(anchor, block + anchor)
open(path, "w").write(src)

diff = subprocess.run(["git", "-C", tree, "diff", "--", rel], capture_output=True,
                      text=True, check=True).stdout
if not diff:
    sys.exit("empty diff?")
open(out, "w").write(diff)
chk = subprocess.run(["git", "-C", tree, "apply", "-R", "--check", os.path.abspath(out)],
                     capture_output=True, text=True)
print("hunks:", diff.count("\n@@"), "| reverse-apply check:", "OK" if chk.returncode == 0 else chk.stderr)
print("wrote", out)
