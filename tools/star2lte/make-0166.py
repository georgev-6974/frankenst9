#!/usr/bin/env python3
# make-0166.py TREE OUT.patch
# S9+ keys: a5xelte_keys.c already has the S8 sampling path (GPA0 +0x24, GPA2 +0x64,
# pins {12,3,4,6}), which matches the bits measured on the S9+ by s9survey (0165):
# volup +024 bit3, voldown +024 bit4, bixby +024 bit6, power +064 bit4.
# Only the base was the S8 one (0x164b0000). This sets the S9+ AON base 0x14050000.
# A5_KEYS_DEFAULT stays 0: enable with boot-arg a5keys=1.
# Needs a clean tree (git -C TREE commit -am 0165 first). Leaves the edit uncommitted.
# UNTESTED: not built by CI, not run on the phone.
import subprocess, sys, pathlib

tree = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()

if subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                  capture_output=True, text=True, check=True).stdout.strip():
    sys.exit("tree not clean: git -C %s commit -am '<previous number>'" % tree)

f = tree / "bsd/dev/a5xelte_keys.c"
s = f.read_text()
if "0x14050000u" in s:
    sys.exit("0166 already applied")

old = ("#if defined(DREAMLTE)\n"
       "#define A5_ALIVE_PA 0x164b0000u            /* Exynos 8895 pinctrl ALIVE */\n"
       "#else\n")
new = ("#if defined(STAR2LTE)\n"
       "#define A5_ALIVE_PA 0x14050000u            /* Exynos 9810 AON, measured by s9survey (0165) */\n"
       "#elif defined(DREAMLTE)\n"
       "#define A5_ALIVE_PA 0x164b0000u            /* Exynos 8895 pinctrl ALIVE */\n"
       "#else\n")
if s.count(old) != 1:
    sys.exit("expected one A5_ALIVE_PA block, found %d" % s.count(old))
f.write_text(s.replace(old, new))

diff = subprocess.run(["git", "-C", str(tree), "diff"], capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff")
out.write_text(diff)
print("wrote", out)
