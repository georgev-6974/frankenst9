#!/usr/bin/env python3
"""make-0152: diff the S9+ PMU block (0x14060000, first 16 KiB) around PSCI CPU_ON.

For cpu 1 (works) and cpu 4 (M3, does not start): snapshot 4096 words before
CPU_ON, wait 300 ms after it, log up to 40 changed words as
  S9PMU cpu=N off=0xOFFSET OLD->NEW
Compare the cpu 1 and cpu 4 lists to see which PMU words firmware touches.

Needs 0151 already committed in TREE_DIR (git diff must contain only 0152):
  git -C WORK3/xnu commit -am "0151"
usage: python3 tools/star2lte/make-0152.py TREE_DIR OUT_PATCH
UNTESTED (not run on the real tree). Reading the PMU block could in theory
SError if a sub-range is secure-only; the first 16 KiB is the usual register area.
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
if "S9PMU" in src:
    sys.exit("already applied (S9PMU)")
if "S9AFF" not in src:
    sys.exit("0151 (S9AFF) not in tree: apply/commit 0151 first")

dirty = subprocess.run(["git", "-C", tree, "status", "--porcelain", "--untracked-files=no"],
                       capture_output=True, text=True, check=True).stdout.strip()
if dirty:
    sys.exit("tree has uncommitted changes, commit them first:\n" + dirty)

a_helper = "/* S9AFF: PSCI AFFINITY_INFO"
a_rc = "\tint32_t rc = sweet_psci_cpu_on(SWEET_PSCI_TARGET(cpu->phys_id), entry, getCPUNumber());\n"
a_log = '\tIOLog(CPU_PORT_NAME " CPU: cpu=%u PSCI CPU_ON rc=%d\\n", getCPUNumber(), rc);\n'
for name, a in (("helper", a_helper), ("rc", a_rc), ("log", a_log)):
    if src.count(a) != 1:
        sys.exit("anchor %s not found exactly once (%d)" % (name, src.count(a)))

glob = "/* S9PMU: snapshot of the PMU block before CPU_ON */\nstatic uint32_t s9pmu_snap[4096];\n\n"
before = '''\tvolatile uint32_t *s9pmu = NULL;
\tif (getCPUNumber() == 1 || getCPUNumber() == 4) {
\t\ts9pmu = (volatile uint32_t *)ml_io_map(0x14060000ULL, 0x4000);
\t\tfor (int w = 0; w < 4096; w++) {
\t\t\ts9pmu_snap[w] = s9pmu[w];
\t\t}
\t}
'''
after = '''\tif (s9pmu) {
\t\tfor (int j = 0; j < 30; j++) {
\t\t\tIODelay(10000);
\t\t}
\t\tint n = 0;
\t\tfor (int w = 0; w < 4096; w++) {
\t\t\tuint32_t v = s9pmu[w];
\t\t\tif (v != s9pmu_snap[w] && n < 40) {
\t\t\t\tIOLog(CPU_PORT_NAME " S9PMU cpu=%u off=0x%x %x->%x\\n", getCPUNumber(),
\t\t\t\t   (unsigned)(w * 4), (unsigned)s9pmu_snap[w], (unsigned)v);
\t\t\t\tn++;
\t\t\t}
\t\t}
\t\tIOLog(CPU_PORT_NAME " S9PMU cpu=%u done, %d changed (max 40 shown)\\n", getCPUNumber(), n);
\t}
'''
src = src.replace(a_helper, glob + a_helper).replace(a_rc, before + a_rc).replace(a_log, a_log + after)
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
