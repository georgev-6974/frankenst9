import glob, sys
out = "xnu/patches/0141-s9-entry-markers.patch"
import os
if os.path.exists(out): sys.exit("already exists")
L = open("xnu/patches/0065-sweet-smp-psci.patch", encoding="utf-8", errors="surrogateescape").read().split("\n")
i = [k for k, l in enumerate(L) if l == "+Lsweet_secondary_el1:"]
if len(i) != 1: sys.exit("anchor found %d times" % len(i))
i = i[0]
for need, off in (("+Lsweet_secondary_bad_el:", -2), ("+\tb\t\t.", -1), ("+\tmsr\t\tSPSel, #1", 2), ("+\tb\t\tEXT(LowResetVectorBase)", 3), ("+#endif /* SWEET */", 4)):
    if L[i + off] != need: sys.exit("unexpected line at %+d: %r" % (off, L[i + off]))
for p in glob.glob("xnu/patches/*.patch"):
    if p.endswith("0065-sweet-smp-psci.patch"): continue
    t = open(p, encoding="utf-8", errors="surrogateescape").read()
    if "Lsweet_secondary_el1" in t or "b\t\tEXT(LowResetVectorBase)" in t: sys.exit("another patch touches the anchor: " + p)
c = lambda k: " " + L[k][1:]
mark = lambda v: ["+\tMOV64\tx2, 0x89f00020", "+\tmov\t\tw3, #0x%x" % v, "+\tstr\t\tw3, [x2]"]
body = [c(i - 2), c(i - 1), c(i)] + mark(0x7702) + [c(i + 1), c(i + 2)] + mark(0x7703) + [c(i + 3), c(i + 4), " "]
hdr = ["diff --git osfmk/arm64/start.s osfmk/arm64/start.s", "--- a/osfmk/arm64/start.s", "+++ b/osfmk/arm64/start.s", "@@ -320,8 +320,14 @@"]
open(out, "w", encoding="utf-8", errors="surrogateescape").write("\n".join(hdr + body) + "\n")
print("ok, wrote", out)
