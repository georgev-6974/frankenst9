#!/usr/bin/env python3
"""Patch 0146 (diagnostic only): make the 'Ticket lock ... unexpectedly owned' panic
print the thread's ctid, the lock's stored owner and the caller address.

Run from the project folder:  python3 tools/star2lte/make-0146.py WORK2
Edits WORK2/xnu/osfmk/kern/lock_ticket.c, writes xnu/patches/0146-s9-ticket-diag.patch.
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
old = 'panic("Ticket lock %p is unexpectedly owned by thread %p", lck, self);'
new = ('panic("Ticket lock %p unexpectedly owned: thread %p ctid 0x%x owner 0x%x from %p",'
       ' lck, self, (uint32_t)self->ctid, (uint32_t)lck->lck_ticket_owner,'
       ' __builtin_return_address(0));')
if c.count(old) != 1:
    die('panic line not found exactly once in lock_ticket.c')
open(f, 'w').write(c.replace(old, new))

diff = subprocess.run(['git', '-C', tree, 'diff'], capture_output=True, text=True).stdout
if not diff.strip():
    die('no diff produced')
out = os.path.join(repo, 'xnu/patches/0146-s9-ticket-diag.patch')
open(out, 'w').write(diff)
subprocess.run(['git', '-C', tree, 'checkout', '--', '.'], check=True)
r = subprocess.run(['git', '-C', tree, 'apply', '--check', out], capture_output=True, text=True)
if r.returncode != 0:
    os.remove(out)
    die('patch does not re-apply:\n' + r.stderr)
print('OK: wrote xnu/patches/0146-s9-ticket-diag.patch')
