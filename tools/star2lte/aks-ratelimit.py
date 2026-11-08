import sys
p = sys.argv[1]
s = open(p).read()
old = '+\tIOLog("SWEET AKS: %s sel %u arg0'
new = '+\tstatic uint32_t sweet_aks_n; if (++sweet_aks_n < 600 || sweet_aks_n % 500 == 0) IOLog("SWEET AKS: %s sel %u arg0'
if s.count(old) != 1:
    sys.exit("expected exactly 1 match, found %d; nothing changed" % s.count(old))
open(p, "w").write(s.replace(old, new))
print("ok: AKS log now limited to the first 600 calls, then 1 in 500")
