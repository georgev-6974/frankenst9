import difflib, os, subprocess, sys
src, out = "/tmp/xnu-orig/osfmk/arm64/start.s", "xnu/patches/0142-s9-reset-markers.patch"
if os.path.exists(out): sys.exit("already exists")
A = open(src).read().splitlines(True)
r = [i for i, l in enumerate(A) if l.startswith("LEXT(reset_vector)")]
if len(r) != 1: sys.exit("reset_vector found %d times" % len(r))
def find(name, pred):
    h = [i for i in range(r[0], r[0] + 110) if pred(A[i])]
    if len(h) != 1: sys.exit("%s found %d times; nothing written" % (name, len(h)))
    return h[0]
i1 = find("DAIFSet", lambda l: "DAIFSet" in l and "DAIFSC_ALL" in l)
i2 = find("Lfound", lambda l: l.strip() == "Lfound_cpu_data_entry:")
i3 = find("blr", lambda l: l.split() == ["blr", "x0"])
i4 = find("Lskip", lambda l: l.startswith("Lskip_cpu_reset_handler:"))
mk = lambda v: ["\tMOV64\tx10, 0x89f00020\n", "\tmov\t\tw11, #0x%x\n" % v, "\tstr\t\tw11, [x10]\n"]
B = list(A)
for pos, v in sorted([(i3, 0x7708), (i4 + 1, 0x7707), (i2 + 1, 0x7706), (i1 + 1, 0x7704)], reverse=True):
    B[pos:pos] = mk(v)
d = list(difflib.unified_diff(A, B, "a/osfmk/arm64/start.s", "b/osfmk/arm64/start.s", n=3))
open(out, "w").write("diff --git osfmk/arm64/start.s osfmk/arm64/start.s\n" + "".join(d))
r = subprocess.run(["git", "-C", "/tmp/xnu-orig", "apply", "--check", os.path.abspath(out)], capture_output=True, text=True)
print("ok, wrote", out, "| apply check:", "PASS" if r.returncode == 0 else "FAIL " + r.stderr[:300])
