#!/usr/bin/env python3
# make-0160.py TREE OUT.patch
# Heartbeat (0126 hb_row) stops drawing once sweet_console_muted is set.
# Needs a clean tree (commit the previous edit first). Leaves the edit uncommitted.
import subprocess, sys, pathlib

tree = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()

if subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                  capture_output=True, text=True, check=True).stdout.strip():
    sys.exit("tree not clean: git -C %s commit -am '<previous number>'" % tree)

hits = subprocess.run(["git", "-C", str(tree), "grep", "-l", "^hb_row(unsigned row", "--", "pexpert"],
                      capture_output=True, text=True).stdout.split()
if len(hits) != 1:
    sys.exit("expected exactly 1 file with hb_row, got: %r" % hits)
f = tree / hits[0]
s = f.read_text()

old = "static void\nhb_row(unsigned row, uint32_t value)\n{\n\tif (!hb_fb) {\n\t\treturn;\n\t}\n"
new = ("/* Set by AppleCLCD once the GUI presents (patch 0067). */\n"
       "extern int sweet_console_muted;\n\n"
       "static void\nhb_row(unsigned row, uint32_t value)\n{\n"
       "\tif (!hb_fb || sweet_console_muted) {\n\t\treturn;\n\t}\n")
if s.count(old) != 1:
    sys.exit("hb_row block not found exactly once in %s" % f)
f.write_text(s.replace(old, new))

diff = subprocess.run(["git", "-C", str(tree), "diff"], capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff")
out.write_text(diff)
print("wrote", out, "edited", hits[0])
