#!/usr/bin/env python3
"""Decode the star2lte loader log (LDRLOG area in USERDATA).

  ldrlog.py AREA.bin [OUT.txt]

AREA.bin = the 64 blocks (4 KiB each) directly below the kernel's 1025-block
ring at the end of USERDATA (see shim/star2lte/ufs_probe.c, ufs_log_write).
Block 0: "LDRLOG\\0\\0", u32 version, u32 text length, u64 flush sequence.
"""
import struct, sys

data = open(sys.argv[1], 'rb').read()
magic, version, length, seq = struct.unpack_from('<8sIIQ', data, 0)
if magic != b'LDRLOG\0\0':
    sys.exit('no LDRLOG header (loader never flushed, or wrong area)')
length = min(length, len(data) - 4096)
text = data[4096:4096 + length].decode('utf-8', 'replace').replace('\r', '')
print(f'# version {version}, {length} bytes, flush #{seq}', file=sys.stderr)
if len(sys.argv) > 2:
    open(sys.argv[2], 'w').write(text)
else:
    sys.stdout.write(text)
