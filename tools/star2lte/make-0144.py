import os, subprocess, sys, difflib
src, out = "/tmp/xnu-orig/osfmk/arm64/start.s", "xnu/patches/0142-s9-reset-markers.patch"
p101, p115 = "xnu/patches/0101-a5xelte-cpu-identity.patch", "xnu/patches/0115-a5xelte-eight-core-topology.patch"
P = "((volatile uint32_t *)ml_io_map(0x89f00000ULL, 0x1000))"
OLD = 'EL=0x%x", i, ' + P + '[8], ' + P + '[9]);'
NEW = 'EL=0x%x D=%x,%x,%x", i, ' + ', '.join(P + '[%d]' % k for k in (8, 9, 12, 13, 14)) + ');'
rd = lambda p: open(p, encoding="utf-8", errors="surrogateescape").read()
C, D = rd(p101), rd(p115)
if C.count(OLD) != 1 or D.count(OLD) != 1: sys.exit("panic line not found exactly once in 0101/0115 (%d, %d); nothing written" % (C.count(OLD), D.count(OLD)))
A = open(src).read().splitlines(True)
r = [i for i, l in enumerate(A) if l.startswith("LEXT(reset_vector)")]
if len(r) != 1: sys.exit("reset_vector found %d times" % len(r))
def find(name, pred):
    h = [i for i in range(r[0], r[0] + 110) if pred(A[i])]
    if len(h) != 1: sys.exit("%s found %d times; nothing written" % (name, len(h)))
    return h[0]
i1 = find("DAIFSet", lambda l: "DAIFSet" in l and "DAIFSC_ALL" in l)
i0 = find("ldr entries", lambda l: l.split()[:1] == ["ldr"] and "CPU_DATA_ENTRIES" in l)
i2 = find("Lfound", lambda l: l.strip() == "Lfound_cpu_data_entry:")
i5 = find("label 1", lambda l: l.strip() == "1:")
i3 = find("blr", lambda l: l.split() == ["blr", "x0"])
i4 = find("Lskip", lambda l: l.startswith("Lskip_cpu_reset_handler:"))
mk = lambda b: ["\tMOV64\tx10, 0x89f00020\n", "\tldr\t\tw11, [x10]\n", "\torr\t\tw11, w11, #0x%x\n" % b, "\tstr\t\tw11, [x10]\n"]
dat = ["\tMOV64\tx10, 0x89f00030\n", "\tstr\t\tw1, [x10]\n", "\tldr\t\tx9, [x1, #(16 + CPU_DATA_PADDR)]\n", "\tstr\t\tw9, [x10, #4]\n", "\tstr\t\tw15, [x10, #8]\n"]
B = list(A)
for pos, ins in sorted([(i4 + 1, mk(0x800)), (i3, mk(0x80)), (i5 + 1, mk(0x40)), (i2 + 1, mk(0x20)), (i0 + 1, dat), (i1 + 1, mk(0x10))], key=lambda t: t[0], reverse=True):
    B[pos:pos] = ins
d = list(difflib.unified_diff(A, B, "a/osfmk/arm64/start.s", "b/osfmk/arm64/start.s", n=3))
tmp = out + ".new"
open(tmp, "w").write("diff --git osfmk/arm64/start.s osfmk/arm64/start.s\n" + "".join(d))
r = subprocess.run(["git", "-C", "/tmp/xnu-orig", "apply", "--check", os.path.abspath(tmp)], capture_output=True, text=True)
if r.returncode != 0: os.remove(tmp); sys.exit("apply check FAIL: " + r.stderr[:300])
os.replace(tmp, out)
open(p101, "w", encoding="utf-8", errors="surrogateescape").write(C.replace(OLD, NEW))
open(p115, "w", encoding="utf-8", errors="surrogateescape").write(D.replace(OLD, NEW))
print("ok: 0142 regenerated, panic prints D=entries_ptr,cpu1_entry_paddr,mpidr")
