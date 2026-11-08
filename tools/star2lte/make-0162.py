#!/usr/bin/env python3
# make-0162.py TREE OUT.patch
# Time the CPU copy of a swap surface into fPixels (SweetFramebuffer.cpp).
# Logs "SWEET FBTIME" for the first 5 copies, then every 50th: microseconds, w, h.
# Needs a clean tree (commit the previous edit first). Leaves the edit uncommitted.
# UNTESTED: not compiled, not run on the phone.
import re, subprocess, sys, pathlib

tree = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()

if subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                  capture_output=True, text=True, check=True).stdout.strip():
    sys.exit("tree not clean: git -C %s commit -am '<previous number>'" % tree)

f = tree / "iokit/Kernel/arm/SweetFramebuffer.cpp"
s = f.read_text()

# 1. timer start, just before the copy block
pat1 = re.compile(r"(\n)([ \t]*)(if \(src != 0 && bpe == 4\) \{\s*\n\s*for \(int32_t y = 0; y < h; y\+\+\) \{)")
m1 = pat1.findall(s)
if len(m1) != 1:
    sys.exit("expected exactly one copy-loop start, found %d" % len(m1))
s = pat1.sub(lambda m: m.group(1) + m.group(2) + "uint64_t sweet_t0 = mach_absolute_time();\n" + m.group(2) + m.group(3), s)

# 2. log, between the end of the copy block and s->release()
pat2 = re.compile(r"(\(size_t\)w \* 4\);\s*\}\s*\})([ \t]*\n)([ \t]*)(s->release\(\);)")
m2 = pat2.findall(s)
if len(m2) != 1:
    sys.exit("expected exactly one copy-loop end + s->release(), found %d" % len(m2))

def add_log(m):
    ind = m.group(3)
    log = (
        "\n" + ind + "{\n"
        + ind + "\tstatic uint32_t sweet_cp_n;\n"
        + ind + "\tuint64_t sweet_dt = mach_absolute_time() - sweet_t0;\n"
        + ind + "\tsweet_cp_n++;\n"
        + ind + "\tif (src != 0 && bpe == 4 && (sweet_cp_n <= 5 || (sweet_cp_n % 50) == 0)) {\n"
        + ind + "\t\tIOLog(\"SWEET FBTIME: n %u copy %llu us (ticks %llu) w %d h %d\\n\",\n"
        + ind + "\t\t    sweet_cp_n, (unsigned long long)(sweet_dt / 26), (unsigned long long)sweet_dt, w, h);\n"
        + ind + "\t}\n"
        + ind + "}"
    )
    return m.group(1) + log + m.group(2) + ind + m.group(4)

s = pat2.sub(add_log, s)
f.write_text(s)

diff = subprocess.run(["git", "-C", str(tree), "diff"], capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff")
out.write_text(diff)
print("wrote", out)
