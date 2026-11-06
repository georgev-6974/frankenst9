#!/usr/bin/env python3
"""Add a swap diagnostic to xnu/patches/0046-sweet-iosurface-iomfb.patch (in place).

Logs, for the first 8 swaps and then every 256th: why a copy is skipped
(src==0) or 64 sampled pixels (how many are non-black), so we can tell
"black frame" from "scanout skipped".

usage: python3 tools/star2lte/make-0133.py xnu/patches/0046-sweet-iosurface-iomfb.patch
Revert with: git checkout xnu/patches/0046-sweet-iosurface-iomfb.patch
"""
import re
import sys

path = sys.argv[1]
lines = open(path, encoding="utf-8", errors="surrogateescape").read().split("\n")

ANCHOR = "+\t\tif (src != 0 && bpe == 4) {"
hits = [i for i, l in enumerate(lines) if l == ANCHOR]
if len(hits) != 1:
    sys.exit("anchor found %d times (need exactly 1); not changed" % len(hits))
a = hits[0]
if any("SWEET FBDIAG" in l for l in lines):
    sys.exit("already patched")

# nearest hunk header above the anchor must be a whole-file add: @@ -0,0 +1,N @@
h = a
while h >= 0 and not lines[h].startswith("@@"):
    h -= 1
m = re.match(r"^@@ -0,0 \+1,(\d+) @@", lines[h]) if h >= 0 else None
if not m:
    sys.exit("hunk above anchor is not '@@ -0,0 +1,N @@'; not changed")

new = r'''
		{
			static uint32_t sweet_dbg_n;
			sweet_dbg_n++;
			if (sweet_dbg_n <= 8 || (sweet_dbg_n & 0xff) == 0) {
				if (src == 0 || bpe != 4) {
					IOLog("SWEET FBDIAG: n %u SKIP src %lx bpe %u ew %u eh %u mem %p last %llu len %llu w %d h %d\n",
					   sweet_dbg_n, (unsigned long)src, bpe, (unsigned)s->elementWidth,
					   (unsigned)s->elementHeight, (void *)s->memory, (unsigned long long)last,
					   (unsigned long long)(s->memory ? s->memory->getLength() : 0), w, h);
				} else {
					uint32_t nz = 0, first = 0, mid = 0, px;
					for (uint32_t i = 0; i < 64; i++) {
						uint32_t yy = (uint32_t)(((uint64_t)i * (uint32_t)h) / 64);
						uint32_t xx = (uint32_t)((i * 37u) % (uint32_t)w);
						memcpy(&px, (const void *)(src + s->offset + (uint64_t)(sy + yy) * s->bytesPerRow +
						   (uint64_t)(sx + xx) * 4), 4);
						if (i == 0) {
							first = px;
						}
						if (i == 32) {
							mid = px;
						}
						if ((px & 0x00ffffffu) != 0) {
							nz++;
						}
					}
					IOLog("SWEET FBDIAG: n %u ok nonblack %u/64 px0 0x%x px32 0x%x w %d h %d dst %d,%d\n",
					   sweet_dbg_n, nz, first, mid, w, h, dx, dy);
				}
			}
		}'''.split("\n")[1:]
ins = ["+" + l for l in new]
lines[a:a] = ins
lines[h] = "@@ -0,0 +1,%d @@%s" % (int(m.group(1)) + len(ins), lines[h][m.end():])
open(path, "w", encoding="utf-8", errors="surrogateescape").write("\n".join(lines))
print("inserted %d lines before line %d; hunk now +1,%d" % (len(ins), a + 1, int(m.group(1)) + len(ins)))
