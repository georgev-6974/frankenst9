import re, sys
def rd(p): return open(p, encoding="utf-8", errors="surrogateescape").read().split("\n")
def wr(p, L): open(p, "w", encoding="utf-8", errors="surrogateescape").write("\n".join(L))
p25, p101, p115 = "xnu/patches/0125-star2lte.patch", "xnu/patches/0101-a5xelte-cpu-identity.patch", "xnu/patches/0115-a5xelte-eight-core-topology.patch"
B = rd(p25); C = rd(p101); D = rd(p115)
if any("S9FLAG" in l for l in C + D): sys.exit("already patched")
d = [i for i, l in enumerate(B) if "int32_t drc = sweet_psci_cpu_on" in l]
if len(d) != 1: sys.exit("early-panic block found %d times" % len(d))
d = d[0]
if "{" not in B[d-1] or "}" not in B[d+4] or "panic" not in B[d+3]: sys.exit("early-panic block shape differs; nothing written")
del B[d-1:d+5]
h = [i for i, l in enumerate(B) if re.match(r"@@ -296,7 \+301,\d+ @@", l)]
if len(h) != 1: sys.exit("0125 hunk header found %d times" % len(h))
n = int(re.match(r"@@ -296,7 \+301,(\d+) @@", B[h[0]]).group(1))
B[h[0]] = B[h[0]].replace("+301,%d @@" % n, "+301,%d @@" % (n - 6))
OLD = 'startup timeout (reset/MMU/GIC/SGI)", i);'
NEW = 'startup timeout (reset/MMU/GIC/SGI) S9FLAG=0x%x", i, ((volatile uint32_t *)ml_io_map(0x89f00000ULL, 0x1000))[6]);'
c = 0
for L in (C, D):
    for i, l in enumerate(L):
        if OLD in l and "CPU_PORT_NAME" in l and l[:1] in "+ ":
            L[i] = l.replace(OLD, NEW); c += 1
if c != 2: sys.exit("panic line: expected 2 edits (0101 + and 0115 context), got %d; nothing written" % c)
wr(p25, B); wr(p101, C); wr(p115, D); print("ok")
