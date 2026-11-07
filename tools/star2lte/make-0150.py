#!/usr/bin/env python3
"""make-0150: MAX_CPU_CLUSTER_PHY_ID = 7 for the A5XELTE board block.

A55 cores have MPIDR Aff1 0..3 and the M3 cores 4..7, so the physical-cluster
table must hold 8 entries (default was MAX_CPU_CLUSTERS - 1 = 1).

usage: python3 tools/star2lte/make-0150.py TREE_DIR OUT_PATCH
  e.g. python3 tools/star2lte/make-0150.py WORK3/xnu (pwd)/xnu/patches/0150-s9-max-cluster-phy-id.patch
Edits pexpert/pexpert/arm64/board_config.h only. Refuses to run twice.
"""
import re, subprocess, sys, os

tree, out = sys.argv[1], sys.argv[2]
path = os.path.join(tree, "pexpert/pexpert/arm64/board_config.h")
src = open(path).read()
if "S9CLUSTER" in src:
    sys.exit("already applied (S9CLUSTER marker found)")

pat = re.compile(r"#endif[ \t]*/\*[ \t]*ARM64_BOARD_CONFIG_A5XELTE[ \t]*\*/")
if len(pat.findall(src)) != 1:
    sys.exit("anchor (#endif /* ARM64_BOARD_CONFIG_A5XELTE */) not found exactly once")
m = pat.search(src)
ins = ("/* S9CLUSTER: MPIDR Aff1 is the core number (A55 0..3, M3 4..7) */\n"
       "#ifndef MAX_CPU_CLUSTER_PHY_ID\n"
       "#define MAX_CPU_CLUSTER_PHY_ID         7\n"
       "#endif\n")
src = src[:m.start()] + ins + src[m.start():]
open(path, "w").write(src)

diff = subprocess.run(["git", "-C", tree, "diff", "--", "pexpert/pexpert/arm64/board_config.h"],
                      capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff?")
open(out, "w").write(diff)
chk = subprocess.run(["git", "-C", tree, "apply", "-R", "--check", os.path.abspath(out)],
                     capture_output=True, text=True)
print("hunks:", diff.count("\n@@"), "| reverse-apply check:", "OK" if chk.returncode == 0 else chk.stderr)
print("wrote", out)
