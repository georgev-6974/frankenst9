import re, sys
p = sys.argv[1]
lines = open(p).read().split("\n")
target = "+#include <kern/thread_kernel_state.h>"
idx = [i for i, l in enumerate(lines) if l == target]
assert len(idx) == 1, "expected exactly one matching line, found %d" % len(idx)
i = idx[0]
h = max(j for j in range(i) if lines[j].startswith("@@"))
m = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$", lines[h])
assert m, "cannot parse hunk header: " + lines[h]
a, b, c, d, rest = m.groups()
d = int(d if d is not None else 1) - 1
lines[h] = "@@ -%s,%s +%s,%d @@%s" % (a, b if b is not None else "1", c, d, rest)
del lines[i]
open(p, "w").write("\n".join(lines))
print("removed line %d, hunk header now: %s" % (i + 1, lines[h]))
