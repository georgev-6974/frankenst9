#!/usr/bin/env python3
"""make-0149: all A55 cores share logical cluster 0 (MPIDR Aff1 = core number).

usage: python3 tools/star2lte/make-0149.py TREE_DIR OUT_PATCH
  TREE_DIR  git tree with patches up to 0148 applied AND committed (e.g. WORK3/xnu)
  OUT_PATCH e.g. xnu/patches/0149-s9-cluster-map.patch
Edits osfmk/arm64/machine_routines.c only. Refuses to run twice.
"""
import re, subprocess, sys, os

tree, out = sys.argv[1], sys.argv[2]
path = os.path.join(tree, "osfmk/arm64/machine_routines.c")
src = open(path).read()
if "S9CLUSTER" in src:
    sys.exit("already applied (S9CLUSTER marker found)")

# 1) logical cluster id from the ADT instead of the MPIDR-derived table
pat1 = re.compile(
    r"(?P<i>[ \t]*)cpu->cluster_id = \(\(cluster_phys_to_logical\[phys_cluster_id\] == -1\) \?\s*"
    r"topology_info\.num_clusters : cluster_phys_to_logical\[phys_cluster_id\]\);")
m = pat1.search(src)
if not m or len(pat1.findall(src)) != 1:
    sys.exit("anchor 1 (cpu->cluster_id assignment) not found exactly once")
i = m.group("i")
new1 = (
    "#if defined(A5XELTE)\n"
    f"{i}/* S9CLUSTER: Exynos 9810 A55 cores have MPIDR Aff1 = core number but share\n"
    f"{i} * one cluster; the logical cluster is the ADT cluster-id (A55 = 0). */\n"
    f"{i}cpu->cluster_id = (uint32_t)ml_readprop(child, \"cluster-id\", 0);\n"
    "#else\n" + m.group(0) + "\n#endif")
src = src[:m.start()] + new1 + src[m.end():]

# 2) register every core's physical cluster, not only the first core of a cluster
pat2 = re.compile(
    r"(?P<a>[ \t]*ml_read_reg_range\(child, \"cpm-impl-reg\", &cluster->cpm_IMPL_pa, &cluster->cpm_IMPL_len\);\n"
    r"[ \t]*\}\n)")
m = pat2.search(src)
if not m or len(pat2.findall(src)) != 1:
    sys.exit("anchor 2 (end of cluster->num_cpus == 0 block) not found exactly once")
new2 = (m.group("a") +
        "#if defined(A5XELTE)\n"
        "\t\t/* S9CLUSTER: cores 1-3 join logical cluster 0 but have their own physical Aff1 */\n"
        "\t\tif (cluster_phys_to_logical[phys_cluster_id] == -1) {\n"
        "\t\t\tcluster_phys_to_logical[phys_cluster_id] = cpu->cluster_id;\n"
        "\t\t}\n"
        "#endif\n")
src = src[:m.start()] + new2 + src[m.end():]

open(path, "w").write(src)
diff = subprocess.run(["git", "-C", tree, "diff", "--", "osfmk/arm64/machine_routines.c"],
                      capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff?")
open(out, "w").write(diff)
chk = subprocess.run(["git", "-C", tree, "apply", "-R", "--check", os.path.abspath(out)],
                     capture_output=True, text=True)
print("hunks:", diff.count("\n@@"), "| reverse-apply check:", "OK" if chk.returncode == 0 else chk.stderr)
print("wrote", out)
