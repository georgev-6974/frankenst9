#!/usr/bin/env python3
"""make-0157: ml_get_cpu_number_local()/ml_get_cluster_number_local(): map an M3's raw MPIDR to the ADT id.

0156 boot with 8 cpus: cpu 5 panicked in machine_routines.c:1259
  assert(cpu_id <= ml_get_max_cpu_number())   (cpu_id = -1 as unsigned: no ADT phys_id matched)
and cpu 4 (raw MPIDR 0x100) was identified as logical cpu 1 (the A55 with the same low 16 bits),
so it never stored its own GIC mask ("S9IPI: GICv2 target CPU4 unavailable (mask 0)").
Fix: sweet_norm_mpidr(): if MIDR_EL1 implementer == 0x53 (Exynos M3; claim from danstronics'
notes, MIDR 0x531f0020), return 0x400 + ((mpidr & 0xff) << 8) (ADT: M3 core n = 0x400 + (n << 8)),
else the raw value. Same mapping as 0155 (start.s). Applied unconditionally: only changes
behaviour on Samsung M-cores.

Needs 0156 committed in TREE_DIR:  git -C WORK3/xnu commit -am "0156"
usage: python3 tools/star2lte/make-0157.py TREE_DIR OUT_PATCH
UNTESTED (not compiled).
"""
import subprocess, sys, os

tree, out = sys.argv[1], sys.argv[2]
rel = "osfmk/arm64/machine_routines.c"
path = os.path.join(tree, rel)
src = open(path).read()
if "sweet_norm_mpidr" in src:
    sys.exit("already applied (sweet_norm_mpidr)")

dirty = subprocess.run(["git", "-C", tree, "status", "--porcelain", "--untracked-files=no"],
                       capture_output=True, text=True, check=True).stdout.strip()
if dirty:
    sys.exit("tree has uncommitted changes, commit them first:\n" + dirty)

a_fn = "int\nml_get_cpu_number(uint32_t phys_id)\n{\n"
a_cpu = "\tcpu_id = ml_get_cpu_number((uint32_t)mpidr_el1_value);\n"
a_clu = "\tcluster_id = ml_get_cluster_number((uint32_t)mpidr_el1_value);\n"
for name, a in (("fn", a_fn), ("cpu", a_cpu), ("cluster", a_clu)):
    if src.count(a) != 1:
        sys.exit("anchor %s not found exactly once (%d)" % (name, src.count(a)))

helper = '''/* sweet_norm_mpidr: raw MPIDR_EL1 -> ADT phys id. An Exynos M3 (MIDR implementer 0x53) reads
 * 0x100+core, which collides with A55 core 1; the ADT gives it 0x400 + (core << 8). */
static uint32_t
sweet_norm_mpidr(uint64_t mpidr)
{
	uint64_t midr = 0;
	MRS(midr, "MIDR_EL1");
	if (((midr >> 24) & 0xff) == 0x53) {
		return 0x400U + (uint32_t)((mpidr & 0xff) << 8);
	}
	return (uint32_t)mpidr;
}

'''
src = (src.replace(a_fn, helper + a_fn)
       .replace(a_cpu, "\tcpu_id = ml_get_cpu_number(sweet_norm_mpidr(mpidr_el1_value));\n")
       .replace(a_clu, "\tcluster_id = ml_get_cluster_number(sweet_norm_mpidr(mpidr_el1_value));\n"))
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
