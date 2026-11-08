#!/usr/bin/env python3
"""Find dyld's load slide from sampled return addresses; show code around pc.

usage: python3 findbase.py /tmp/dyld_dis.txt
Disassembly made with: llvm-objdump --macho --arch=arm64 -d /tmp/dyld
"""
import re
import sys
from collections import Counter

PC = 0x1007a9990
LR = 0x10079ff2c
BT = [0x1007cb778, 0x1007cded0, 0x1007ac238]
rets = [LR] + BT

path = sys.argv[1] if len(sys.argv) > 1 else '/tmp/dyld_dis.txt'
rx = re.compile(r'^\s*([0-9a-f]+):\t(?:[0-9a-f]{2} ){3}[0-9a-f]{2}\t(\S+)\t?(.*)$')
order, ins = [], {}
for line in open(path, errors='replace'):
    m = rx.match(line)
    if m:
        a = int(m.group(1), 16)
        ins[a] = (m.group(2), m.group(3).strip())
        order.append(a)
print(f'{len(ins)} instructions, first {order[0]:#x}, last {order[-1]:#x}')
calls = {a for a, (mn, _) in ins.items() if mn in ('bl', 'blr', 'blraa', 'blrab', 'blraaz', 'blrabz')}
print(f'{len(calls)} call instructions')

cand = Counter()
for a in calls:
    s = (LR - 4) - a
    if s % 0x1000 == 0:
        cand[s] += 1
scores = []
for s in cand:
    hits = sum(1 for r in rets if (r - 4 - s) in calls)
    pc_ok = (PC - s) in ins
    scores.append((hits, pc_ok, s))
scores.sort(reverse=True)
print('best candidates (hits of 4 return addrs, pc valid, slide):')
for hits, pc_ok, s in scores[:5]:
    print(f'  hits={hits} pc_ok={pc_ok} slide={s:#x} -> dyld text base={order[0] + s:#x}')

hits, pc_ok, s = scores[0]
if hits < 3:
    print('No convincing slide: send me this output.')
    sys.exit(0)
pcv = PC - s
idx = order.index(pcv) if pcv in ins else None
print(f'\nUsing slide {s:#x}. pc maps to file addr {pcv:#x}')
for name, r in [('lr', LR)] + [(f'bt{i}', b) for i, b in enumerate(BT)]:
    v = r - 4 - s
    print(f'{name}: call at {v:#x}: {ins.get(v)}')
if idx is not None:
    print('\ncode around pc (>> marks pc):')
    for a in order[max(0, idx - 28):idx + 8]:
        mn, ops = ins[a]
        print(f"{'>>' if a == pcv else '  '} {a:x}: {mn}\t{ops}")
