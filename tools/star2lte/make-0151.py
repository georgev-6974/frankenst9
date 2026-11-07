#!/usr/bin/env python3
"""make-0151: log PSCI AFFINITY_INFO after CPU_ON for cpu>=4 (diagnostic only).

Probes three targets 8 times over ~0.8 s: the one actually used for CPU_ON,
0x10000 (M3 if MT bit set, Aff2=1) and 0x400 (old ADT placeholder).
Result per probe: 0 ON, 1 OFF, 2 ON_PENDING, <0 PSCI error.

usage: python3 tools/star2lte/make-0151.py TREE_DIR OUT_PATCH
  e.g. python3 tools/star2lte/make-0151.py WORK3/xnu (pwd)/xnu/patches/0151-s9-psci-affinity-diag.patch
Edits SweetCPU.cpp only. Refuses to run twice. UNTESTED (not run on the real tree).
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
if "S9AFF" in src:
    sys.exit("already applied (S9AFF)")

a1 = "class SweetCPU : public IOCPU {"
a2 = '\tIOLog(CPU_PORT_NAME " CPU: cpu=%u PSCI CPU_ON rc=%d\\n", getCPUNumber(), rc);\n'
if src.count(a1) != 1 or src.count(a2) != 1:
    sys.exit("anchors not found exactly once: %d %d" % (src.count(a1), src.count(a2)))

helper = '''/* S9AFF: PSCI AFFINITY_INFO (0 ON, 1 OFF, 2 ON_PENDING, <0 error) */
static int32_t
sweet_psci_aff_info(uint64_t target)
{
	register uint64_t x0 __asm__("x0") = 0xC4000004ULL;
	register uint64_t x1 __asm__("x1") = target;
	register uint64_t x2 __asm__("x2") = 0;
	__asm__ volatile("smc #0" : "+r"(x0), "+r"(x1), "+r"(x2) : :
	   "x3", "x4", "x5", "x6", "x7", "x8", "x9", "x10", "x11", "x12", "x13",
	   "x14", "x15", "x16", "x17", "cc", "memory");
	return (int32_t)x0;
}

'''
diag = '''\tif (getCPUNumber() >= 4) {
\t\tfor (int k = 0; k < 8; k++) {
\t\t\tIOLog(CPU_PORT_NAME " S9AFF cpu=%u k=%d tgt=%d 0x10000=%d 0x400=%d\\n",
\t\t\t   getCPUNumber(), k,
\t\t\t   sweet_psci_aff_info(SWEET_PSCI_TARGET(cpu->phys_id)),
\t\t\t   sweet_psci_aff_info(0x10000ULL), sweet_psci_aff_info(0x400ULL));
\t\t\tfor (int j = 0; j < 10; j++) {
\t\t\t\tIODelay(10000);
\t\t\t}
\t\t}
\t}
'''
src = src.replace(a1, helper + a1).replace(a2, a2 + diag)
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
