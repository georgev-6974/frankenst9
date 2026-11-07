#!/usr/bin/env python3
"""Patch 0147 (diagnostic only): every CPU prints SCTLR/TCR/MAIR/TTBR1/ACTLR_EL1
in SweetCPU::initCPU so cpu 0 and cpu 1 can be compared.

Run from the project folder:  python3 tools/star2lte/make-0147.py WORK2
WORK2 must be clean. The script applies patches 0145 and 0146 inside WORK2 first,
so the new patch is generated and checked on top of them, then resets WORK2.
"""
import os
import re
import subprocess
import sys


def die(msg):
    print('STOP: ' + msg)
    sys.exit(1)


def git(*args, check=True):
    return subprocess.run(['git', '-C', tree] + list(args),
                          capture_output=True, text=True, check=False)


repo = os.getcwd()
tree = os.path.join(repo, sys.argv[1] if len(sys.argv) > 1 else 'WORK2', 'xnu')
if not os.path.isdir(os.path.join(tree, '.git')):
    die(tree + ' is not a git tree')
if git('status', '--porcelain').stdout.strip():
    die('WORK2 tree is not clean (run: git -C WORK2/xnu reset --hard)')

prior = [os.path.join(repo, 'xnu/patches', n)
         for n in ('0145-s9-core-mpidr.patch', '0146-s9-ticket-diag.patch')]
for p in prior:
    if not os.path.exists(p):
        die('missing ' + p)
    r = git('apply', p)
    if r.returncode != 0:
        git('reset', '-q', '--hard')
        die('could not apply ' + os.path.basename(p) + ':\n' + r.stderr)
git('add', '-A')

f = os.path.join(tree, 'iokit/Kernel/arm/SweetCPU.cpp')
c = open(f).read()
pat = re.compile(r'(kprintf\(CPU_PORT_NAME " CPU: cpu=%u entered initCPU[^;]*;)')
m = pat.findall(c)
if len(m) != 1:
    git('reset', '-q', '--hard')
    die('initCPU "entered initCPU" kprintf found %d times, need exactly 1' % len(m))
add = '''
\tkprintf(CPU_PORT_NAME " CPU: cpu=%u SCTLR=%llx TCR=%llx MAIR=%llx TTBR1=%llx ACTLR=%llx\\n",
\t   getCPUNumber(), (unsigned long long)__builtin_arm_rsr64("SCTLR_EL1"),
\t   (unsigned long long)__builtin_arm_rsr64("TCR_EL1"),
\t   (unsigned long long)__builtin_arm_rsr64("MAIR_EL1"),
\t   (unsigned long long)__builtin_arm_rsr64("TTBR1_EL1"),
\t   (unsigned long long)__builtin_arm_rsr64("ACTLR_EL1"));'''
c = pat.sub(lambda mo: mo.group(1) + add, c)
open(f, 'w').write(c)

diff = git('diff').stdout
if not diff.strip():
    git('reset', '-q', '--hard')
    die('no diff produced')
out = os.path.join(repo, 'xnu/patches/0147-s9-cpu-regs-diag.patch')
open(out, 'w').write(diff)

git('reset', '-q', '--hard')
for p in prior:
    r = git('apply', p)
    if r.returncode != 0:
        git('reset', '-q', '--hard')
        die('re-apply of ' + os.path.basename(p) + ' failed:\n' + r.stderr)
r = git('apply', '--check', out)
git('reset', '-q', '--hard')
if r.returncode != 0:
    os.remove(out)
    die('0147 does not apply on top of 0145+0146:\n' + r.stderr)
print('OK: wrote xnu/patches/0147-s9-cpu-regs-diag.patch (checked on top of 0145+0146)')
