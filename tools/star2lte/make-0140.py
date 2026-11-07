import sys
p25, p101, p115 = "xnu/patches/0125-star2lte.patch", "xnu/patches/0101-a5xelte-cpu-identity.patch", "xnu/patches/0115-a5xelte-eight-core-topology.patch"
def rd(p): return open(p, encoding="utf-8", errors="surrogateescape").read()
def wr(p, s): open(p, "w", encoding="utf-8", errors="surrogateescape").write(s)
B, C, D = rd(p25), rd(p101), rd(p115)
if "EL=0x%x" in C: sys.exit("already patched")
def sub(s, old, new, n, name):
    if s.count(old) != n: sys.exit("%s: found %d times, expected %d; nothing written" % (name, s.count(old), n))
    return s.replace(old, new)
B = sub(B, "static const uint32_t code[6] = { 0x100000C3, 0x528EE022, 0xB9000062, 0xD5033F9F, 0x58000081, 0xD61F0020 };",
           "static const uint32_t code[8] = { 0x10000103, 0x528EE022, 0xB9000062, 0xD5384244, 0xB9000464, 0xD5033F9F, 0x58000081, 0xD61F0020 };", 1, "code")
B = sub(B, "for (int i = 0; i < 6; i++) t[i] = code[i];", "for (int i = 0; i < 8; i++) t[i] = code[i];", 1, "loop")
B = sub(B, "t[6] = 0; t[7] = 0; t[8] = (uint32_t)real; t[9] = (uint32_t)(real >> 32);",
           "t[8] = 0; t[9] = 0; t[10] = (uint32_t)real; t[11] = (uint32_t)(real >> 32);", 1, "data")
OLD = 'S9FLAG=0x%x", i, ((volatile uint32_t *)ml_io_map(0x89f00000ULL, 0x1000))[6]);'
NEW = 'S9FLAG=0x%x EL=0x%x", i, ((volatile uint32_t *)ml_io_map(0x89f00000ULL, 0x1000))[8], ((volatile uint32_t *)ml_io_map(0x89f00000ULL, 0x1000))[9]);'
C = sub(C, OLD, NEW, 1, "0101 panic"); D = sub(D, OLD, NEW, 1, "0115 panic")
wr(p25, B); wr(p101, C); wr(p115, D); print("ok")
