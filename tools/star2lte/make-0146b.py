#!/usr/bin/env python3
"""Patch 0146 v2 (diagnostic only): the 'Ticket lock ... unexpectedly owned' panic
prints ctid, owner and six return addresses walked from the frame-pointer chain.

Run from the project folder:  python3 tools/star2lte/make-0146b.py WORK2
REPLACES xnu/patches/0146-s9-ticket-diag.patch (same file name, new content).
WORK2 must be a clean tree WITHOUT the old 0146 applied (it is not: WORK2 is built
from the patches that existed before 0145).
"""
import os
import subprocess
import sys


def die(msg):
    print('STOP: ' + msg)
    sys.exit(1)


repo = os.getcwd()
tree = os.path.join(repo, sys.argv[1] if len(sys.argv) > 1 else 'WORK2', 'xnu')
if not os.path.isdir(os.path.join(tree, '.git')):
    die(tree + ' is not a git tree')
st = subprocess.run(['git', '-C', tree, 'status', '--porcelain'],
                    capture_output=True, text=True).stdout.strip()
if st:
    die('WORK2 tree is not clean:\n' + st)

f = os.path.join(tree, 'osfmk/kern/lock_ticket.c')
c = open(f).read()
old = '\tpanic("Ticket lock %p is unexpectedly owned by thread %p", lck, self);'
if c.count(old) != 1:
    die('original panic line not found exactly once (is the old 0146 already applied in WORK2?)')
new = '''\tuintptr_t s9bt[6] = { 0, 0, 0, 0, 0, 0 };
\tuintptr_t *s9fp = (uintptr_t *)__builtin_frame_address(0);
\tfor (int s9i = 0; s9i < 6; s9i++) {
\t\tif (((uintptr_t)s9fp & 0xf) != 0 || (uintptr_t)s9fp < 0xfffffff000000000ULL) {
\t\t\tbreak;
\t\t}
\t\ts9bt[s9i] = s9fp[1];
\t\ts9fp = (uintptr_t *)s9fp[0];
\t}
\tpanic("Ticket lock %p unexpectedly owned: thread %p ctid 0x%x owner 0x%x bt %p %p %p %p %p %p",
\t   lck, self, (uint32_t)self->ctid, (uint32_t)lck->lck_ticket_owner,
\t   (void *)s9bt[0], (void *)s9bt[1], (void *)s9bt[2],
\t   (void *)s9bt[3], (void *)s9bt[4], (void *)s9bt[5]);'''
open(f, 'w').write(c.replace(old, new))

diff = subprocess.run(['git', '-C', tree, 'diff'], capture_output=True, text=True).stdout
if not diff.strip():
    die('no diff produced')
out = os.path.join(repo, 'xnu/patches/0146-s9-ticket-diag.patch')
open(out, 'w').write(diff)
subprocess.run(['git', '-C', tree, 'checkout', '--', '.'], check=True)
r = subprocess.run(['git', '-C', tree, 'apply', '--check', out], capture_output=True, text=True)
if r.returncode != 0:
    die('patch does not re-apply:\n' + r.stderr)
print('OK: rewrote xnu/patches/0146-s9-ticket-diag.patch')
