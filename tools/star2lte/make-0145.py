#!/usr/bin/env python3
"""Patch 0145: S9+ A55 cores use MPIDR_EL1 numbering (core in Aff1).

Run from the project folder:  python3 tools/star2lte/make-0145.py WORK2
Edits tools/mkadt_star2lte.py and, inside the fresh patched tree WORK2/xnu,
iokit/Kernel/arm/SweetCPU.cpp, then writes xnu/patches/0145-s9-core-mpidr.patch.
Stops with STOP: on any mismatch, changing nothing it cannot undo.
"""
import os
import re
import subprocess
import sys


def die(msg):
    print('STOP: ' + msg)
    sys.exit(1)


repo = os.getcwd()
tree = os.path.join(repo, sys.argv[1] if len(sys.argv) > 1 else 'WORK2', 'xnu')
if not os.path.isdir(os.path.join(tree, '.git')):
    die(tree + ' is not a git tree (run prep-xnu-tree.sh first)')
st = subprocess.run(['git', '-C', tree, 'status', '--porcelain'],
                    capture_output=True, text=True).stdout.strip()
if st:
    die('WORK2 tree is not clean:\n' + st)

# ---- 1. ADT generator -------------------------------------------------
p = os.path.join(repo, 'tools/mkadt_star2lte.py')
s = open(p).read()
if 'SWEET_CORE_AFF1' in s:
    print('mkadt_star2lte.py already edited, skipping')
else:
    edits = [
        ("M3 = dict(name='samsung,exynos-m3', cluster=1, base=0x100,",
         "M3 = dict(name='samsung,exynos-m3', cluster=1, base=0x400,"),
        ("order.append((c, c['base'] + core, core))",
         "order.append((c, c['base'] + (core << 8), core))  # SWEET_CORE_AFF1"),
        ("if boot_mpidr & 0x100:", "if boot_mpidr >= 0x400:"),
    ]
    for old, new in edits:
        if s.count(old) != 1:
            die('mkadt_star2lte.py: text not found exactly once: ' + old)
        s = s.replace(old, new)
    open(p, 'w').write(s)
    print('mkadt_star2lte.py edited')

# ---- 2. SweetCPU.cpp in the patched tree ------------------------------
f = os.path.join(tree, 'iokit/Kernel/arm/SweetCPU.cpp')
if not os.path.exists(f):
    die('missing ' + f)
c = open(f).read()

pat = re.compile(
    r'uint32_t boot_cluster = A5_BOOT_MPIDR & 0x100U;\s*'
    r'uint32_t expected_mpidr = cpu->cpu_id < 4 \? boot_cluster \+ cpu->cpu_id :\s*'
    r'\(boot_cluster \^ 0x100U\) \+ cpu->cpu_id - 4;')
if len(pat.findall(c)) != 1:
    die('expected_mpidr block not found exactly once in SweetCPU.cpp')
c = pat.sub(
    'uint32_t boot_cluster = 0U; /* A55 cluster boots; MPIDR Aff1 = core */\n'
    '\tuint32_t expected_mpidr = cpu->cpu_id < 4 ?\n'
    '\t   boot_cluster + (cpu->cpu_id << 8) :\n'
    '\t   boot_cluster + 0x400U + ((cpu->cpu_id - 4) << 8);', c)

call = re.compile(r'sweet_psci_cpu_on\(\s*cpu->phys_id\s*,')
found = call.findall(c)
if len(found) != 2:
    print('sweet_psci_cpu_on calls found: %d' % len(found))
    for i, line in enumerate(c.splitlines(), 1):
        if 'sweet_psci_cpu_on' in line:
            print('%d: %s' % (i, line))
    die('need exactly two sweet_psci_cpu_on(cpu->phys_id, ...) calls; paste the lines above')
c = call.sub('sweet_psci_cpu_on(SWEET_PSCI_TARGET(cpu->phys_id),', c)

lines = c.split('\n')
last_inc = max((i for i, l in enumerate(lines) if l.startswith('#include')), default=-1)
if last_inc < 0:
    die('no #include line in SweetCPU.cpp')
macro = [
    '',
    '#if defined(STAR2LTE)',
    '/* Exynos 9810: MPIDR_EL1 has the core in Aff1 (A55 0x000-0x300; M3 0x400-0x700',
    ' * is a PLACEHOLDER, not measured). Firmware PSCI CPU_ON uses the Linux DT',
    ' * numbering (A55 0-3, M3 0x100-0x103). */',
    '#define SWEET_PSCI_TARGET(p) ((p) < 0x400U ? ((p) >> 8) : (0x100U + (((p) - 0x400U) >> 8)))',
    '#else',
    '#define SWEET_PSCI_TARGET(p) (p)',
    '#endif',
]
lines[last_inc + 1:last_inc + 1] = macro
open(f, 'w').write('\n'.join(lines))

# ---- 3. write the patch and verify it re-applies ----------------------
diff = subprocess.run(['git', '-C', tree, 'diff'], capture_output=True, text=True).stdout
if not diff.strip():
    die('no diff produced')
out = os.path.join(repo, 'xnu/patches/0145-s9-core-mpidr.patch')
open(out, 'w').write(diff)
subprocess.run(['git', '-C', tree, 'checkout', '--', '.'], check=True)
r = subprocess.run(['git', '-C', tree, 'apply', '--check', out], capture_output=True, text=True)
if r.returncode != 0:
    os.remove(out)
    die('patch does not re-apply:\n' + r.stderr)
print('OK: wrote xnu/patches/0145-s9-core-mpidr.patch (%d lines)' % diff.count('\n'))
