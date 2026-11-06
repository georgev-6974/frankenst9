import re, sys
p = "xnu/patches/0125-star2lte.patch"
L = open(p, encoding="utf-8", errors="surrogateescape").read().split("\n")
if any("TRAMP_PA" in l for l in L):
    sys.exit("already patched")
h = [i for i, l in enumerate(L) if l.startswith("@@ -296,7 +301,7 @@")]
if len(h) != 1:
    sys.exit("hunk header found %d times" % len(h))
h = h[0]
a = h + 4
if L[a] != "-#if defined(DREAMLTE)":
    sys.exit("anchor line mismatch: %r" % L[a])
blk = r'''#if defined(STAR2LTE)
	{
		const uint64_t TRAMP_PA = 0x89f00000ULL;
		static vm_offset_t tv;
		if (tv == 0) tv = ml_io_map(TRAMP_PA, 0x1000);
		volatile uint32_t *t = (volatile uint32_t *)tv;
		uint64_t real = (uint64_t)ml_static_vtop((vm_offset_t)&sweet_secondary_entry);
		static const uint32_t code[6] = { 0x100000C3, 0x528EE022, 0xB9000062, 0xD5033F9F, 0x58000081, 0xD61F0020 };
		for (int i = 0; i < 6; i++) t[i] = code[i];
		t[6] = 0; t[7] = 0; t[8] = (uint32_t)real; t[9] = (uint32_t)(real >> 32);
		__builtin_arm_dsb(DSB_SY);
		IOLog(CPU_PORT_NAME " CPU: cpu=%u tramp pa=0x%llx -> real entry 0x%llx\n", getCPUNumber(), TRAMP_PA, real);
		entry = (vm_offset_t)TRAMP_PA;
	}
#endif'''.split("\n")
new = ["+" + x for x in blk]
L[a:a] = new
L[h] = L[h].replace("@@ -296,7 +301,7 @@", "@@ -296,7 +301,%d @@" % (7 + len(new)))
open(p, "w", encoding="utf-8", errors="surrogateescape").write("\n".join(L))
print("ok, inserted", len(new), "lines")
