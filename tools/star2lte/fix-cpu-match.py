#!/usr/bin/env python3
"""Let the SweetCPU driver match the S9+ boot cluster (ADT-only workaround).

  python3 tools/star2lte/fix-cpu-match.py [tools/mkadt_star2lte.py]

Cause: patch 0086 gives SweetCPU `IONameMatch = 'arm,cortex-a53'` on A5XELTE.
The S9+ ADT cpu nodes say 'arm,cortex-a55' / 'samsung,exynos-m3', so no
SweetCPU is created, ml_set_max_cpus() is never called and the main thread
sleeps forever in ml_wait_max_cpus(). This adds 'arm,cortex-a53' as a second
compatible string on the boot-cluster (A55) nodes only, like the S8 ADT where
only the A53 cluster matched. Idempotent. Proper fix: widen the personality in
the kernel patch (see STAR2LTE_PROGRESS.md).
"""
import sys

p = sys.argv[1] if len(sys.argv) > 1 else "tools/mkadt_star2lte.py"
t = open(p).read()
if "arm,cortex-a53" in t:
    print("already applied: %s mentions arm,cortex-a53" % p)
    sys.exit(0)
old = "('compatible', mkadt.cstr(cluster_info['name']) + mkadt.cstr('ARM,v8')),"
new = ("('compatible', mkadt.cstr(cluster_info['name']) +\n"
       "         (mkadt.cstr('arm,cortex-a53') if cluster_info is A55 else b'') +  # SweetCPU matches a53 (patch 0086)\n"
       "         mkadt.cstr('ARM,v8')),")
if t.count(old) != 1:
    sys.exit("anchor not found exactly once (found %d); edit by hand" % t.count(old))
open(p, "w").write(t.replace(old, new))
print("patched", p)
