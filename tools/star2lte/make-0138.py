import re, sys
def rd(p): return open(p, encoding="utf-8", errors="surrogateescape").read().split("\n")
def wr(p, L): open(p, "w", encoding="utf-8", errors="surrogateescape").write("\n".join(L))
norm = lambda l: " ".join(l[1:].split()) if l.startswith("+") else None
p65 = "xnu/patches/0065-sweet-smp-psci.patch"; p25 = "xnu/patches/0125-star2lte.patch"
A = rd(p65)
if any("0x89f00018" in l for l in A): sys.exit("already patched")
def one(t):
    h = [i for i, l in enumerate(A) if norm(l) == t]
    if len(h) != 1: sys.exit("anchor %r found %d times" % (t, len(h)))
    return h[0]
def m(v): return ["+\tMOV64\tx2, 0x89f00018", "+\tmov\tw3, #0x%x" % v, "+\tstr\tw3, [x2]"]
ins = [(one("msr DAIFSet, #0xf") + 1, 0x7702), (one("Lsweet_secondary_el1:") + 1, 0x7703),
       (one("mrs x1, ICC_SRE_EL2"), 0x7704), (one("msr ICC_SRE_EL2, x1") + 1, 0x7705),
       (one("eret"), 0x7706), (one("b EXT(LowResetVectorBase)"), 0x7707)]
n = 0
for pos, v in sorted(ins, reverse=True):
    A[pos:pos] = m(v); n += 3
h = [i for i, l in enumerate(A) if l.startswith("@@ -279,6 +279,56 @@")]
if len(h) != 1: sys.exit("0065 hunk header found %d times" % len(h))
A[h[0]] = A[h[0]].replace("+279,56 @@", "+279,%d @@" % (56 + n))
B = rd(p25); c = 0
for i, l in enumerate(B):
    if "IODelay(1000)" in l and "tv)[6] == 0" in l:
        B[i] = l.replace(" && ((volatile uint32_t *)tv)[6] == 0", "").replace("i < 1000", "i < 2000"); c += 1
    if "if (fl != 0x7701) panic(" in l:
        B[i] = l.replace("if (fl != 0x7701) ", ""); c += 1
if c != 2: sys.exit("0125 edits: expected 2 lines, changed %d (nothing written)" % c)
wr(p65, A); wr(p25, B); print("ok: %d marker lines in 0065, 2 lines in 0125" % n)
