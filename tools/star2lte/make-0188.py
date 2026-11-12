#!/usr/bin/env python3
# make-0188.py TREE OUT.patch
# Ringer event page/usage from boot args s9rpage / s9ruse (default 0x0B / 0x2E).
# Applies on top of 0187. UNTESTED.
import subprocess, sys, pathlib

tree = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()

if subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                  capture_output=True, text=True, check=True).stdout.strip():
    sys.exit("tree not clean: git -C %s commit -am '<previous number>'" % tree)

f = tree / "iokit/Kernel/arm/hid/SweetHID.cpp"
s = f.read_text()
if "s9rpage" in s:
    sys.exit("0188 already applied")

def rep(s, old, new):
    if s.count(old) != 1:
        sys.exit("expected one match, found %d for:\n%s" % (s.count(old), old))
    return s.replace(old, new)

s = rep(s, "\tstatic int mode = -1;\n",
        "\tstatic int mode = -1;\n\tstatic int rpage = 0x0B, ruse = 0x2E;\n")
s = rep(s, "\t\tmode = v;\n\t}\n",
        "\t\tmode = v;\n"
        "\t\tif (!PE_parse_boot_argn(\"s9rpage\", &rpage, sizeof(rpage))) {\n\t\t\trpage = 0x0B;\n\t\t}\n"
        "\t\tif (!PE_parse_boot_argn(\"s9ruse\", &ruse, sizeof(ruse))) {\n\t\t\truse = 0x2E;\n\t\t}\n"
        "\t}\n")
s = rep(s, r'IOLog("SWEET HID: ringer toggle, silent=%d mode=%d (page 0x0B usage 0x2E)\n", silent, mode);',
        r'IOLog("SWEET HID: ringer toggle, silent=%d mode=%d page 0x%x usage 0x%x\n", silent, mode, rpage, ruse);')
s = rep(s, "gSweetKeyPage = 0x0B;", "gSweetKeyPage = (UInt32)rpage;")
s = rep(s, "gSweetButtons->key(0x2E, true);", "gSweetButtons->key((UInt32)ruse, true);")
s = rep(s, "gSweetButtons->key(0x2E, false);", "gSweetButtons->key((UInt32)ruse, false);")
s = rep(s, "gSweetButtons->key(0x2E, silent != 0);", "gSweetButtons->key((UInt32)ruse, silent != 0);")

f.write_text(s)
diff = subprocess.run(["git", "-C", str(tree), "diff"], capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff")
out.write_text(diff)
print("wrote", out)
