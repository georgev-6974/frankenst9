#!/usr/bin/env python3
"""Patch 0148 (diagnostic only): boot-arg s9nocpuon=1 makes SweetCPU::startCPU
log a line and return WITHOUT calling PSCI CPU_ON, so cpu 1 never wakes.

Run from the project folder:  python3 tools/star2lte/make-0148.py WORK2
WORK2 must be clean. Patches 0145, 0146 and 0147 are applied inside WORK2 first,
so the new patch is generated and checked on top of them; WORK2 is reset afterwards.
"""
import os
import re
import subprocess
import sys


def die(msg):
    print('STOP: ' + msg)
    sys.exit(1)


def git(*args):
    return subprocess.run(['git', '-C', tree] + list(args),
                          capture_output=True, text=True, check=False)


repo = os.getcwd()
tree = os.path.join(repo, sys.argv[1] if len(sys.argv) > 1 else 'WORK2', 'xnu')
if not os.path.isdir(os.path.join(tree, '.git')):
    die(tree + ' is not a git tree')
if git('status', '--porcelain').stdout.strip():
    die('WORK2 tree is not clean (run: git -C WORK2/xnu reset --hard)')

prior = [os.path.join(repo, 'xnu/patches', n) for n in (
    '0145-s9-core-mpidr.patch', '0146-s9-ticket-diag.patch', '0147-s9-cpu-regs-diag.patch')]
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
pat = re.compile(
    r'(IOLog\(CPU_PORT_NAME " CPU: cpu=%u CPU_ON target=0x%x entry_pa=0x%llx context=%u\\n",'
    r'\s*getCPUNumber\(\), cpu->phys_id, \(uint64_t\)entry, getCPUNumber\(\)\);)')
if len(pat.findall(c)) != 1:
    git('reset', '-q', '--hard')
    die('CPU_ON IOLog statement found %d times, need exactly 1' % len(pat.findall(c)))
add = '''
\t{
\t\tuint32_t s9skip = 0;
\t\tif (PE_parse_boot_argn("s9nocpuon", &s9skip, sizeof(s9skip)) && s9skip != 0) {
\t\t\tIOLog(CPU_PORT_NAME " CPU: cpu=%u s9nocpuon: NOT calling PSCI CPU_ON\\n", getCPUNumber());
\t\t\treturn KERN_SUCCESS;
\t\t}
\t}'''
c = pat.sub(lambda mo: mo.group(1) + add, c)
open(f, 'w').write(c)

diff = git('diff').stdout
if not diff.strip():
    git('reset', '-q', '--hard')
    die('no diff produced')
out = os.path.join(repo, 'xnu/patches/0148-s9-nocpuon.patch')
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
    die('0148 does not apply on top of 0145+0146+0147:\n' + r.stderr)
print('OK: wrote xnu/patches/0148-s9-nocpuon.patch (checked on top of 0145-0147)')
