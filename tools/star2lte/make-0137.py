import re, sys
p = "xnu/patches/0125-star2lte.patch"
L = open(p, encoding="utf-8", errors="surrogateescape").read().split("\n")
if any("S9TRAMP" in l for l in L):
    sys.exit("already patched")
a = [i for i, l in enumerate(L) if l == "+\t\tentry = (vm_offset_t)TRAMP_PA;"]
if len(a) != 1:
    sys.exit("anchor found %d times" % len(a))
h = [i for i, l in enumerate(L) if re.match(r"@@ -296,7 \+301,\d+ @@", l)]
if len(h) != 1:
    sys.exit("hunk header found %d times" % len(h))
blk = '''  {
    int32_t drc = sweet_psci_cpu_on(cpu->phys_id, entry, getCPUNumber());
    for (int i = 0; i < 1000 && ((volatile uint32_t *)tv)[6] == 0; i++) IODelay(1000);
    uint32_t fl = ((volatile uint32_t *)tv)[6];
    if (fl != 0x7701) panic("S9TRAMP flag=0x%x rc=%d real=0x%llx tramp=0x%llx", fl, drc, real, TRAMP_PA);
  }'''.split("\n")
new = ["+\t\t" + re.sub(r"^( {2})+", lambda m: "\t" * (len(m.group(0)) // 2), x) for x in blk]
L[a[0] + 1:a[0] + 1] = new
n = int(re.match(r"@@ -296,7 \+301,(\d+) @@", L[h[0]]).group(1))
L[h[0]] = L[h[0]].replace("+301,%d @@" % n, "+301,%d @@" % (n + len(new)))
open(p, "w", encoding="utf-8", errors="surrogateescape").write("\n".join(L))
print("ok, inserted", len(new), "lines")
