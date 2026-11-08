import subprocess, sys
tree, out = sys.argv[1], sys.argv[2]
f = tree + "/bsd/dev/a5xelte_touch.c"
s = open(f).read()
old = '\t\tprintf("S9SURVEY P5: done\\n");\n'
new = '''\t\t/* 0180: battery bus (hsi2c_40 0x14360000, MAX77705 at 0x66), read-only */
\t\t{
\t\t\tvm_offset_t cu = ml_io_map(0x14212000, 0x1000);
\t\t\tvm_offset_t bi = ml_io_map(0x14360000, 0x1000);
\t\t\tvm_offset_t gp = ml_io_map(0x14220000, 0x1000);
\t\t\tprintf("S9SURVEY P5b: battery bus, read-only\\n");
\t\t\tif (cu) {
\t\t\t\ts9survey_pdump("CMGPUSI", cu, 0x20);
\t\t\t}
\t\t\tif (bi) {
\t\t\t\ts9survey_pdump("I2C40", bi, 0x100);
\t\t\t\ts9survey_pdump("I2C40c", bi + 0xc0, 0x20);
\t\t\t}
\t\t\tif (gp) {
\t\t\t\ts9survey_pdump("GPM", gp, 0x200);
\t\t\t}
\t\t}
''' + old
if s.count(old) != 1:
    sys.exit("expected 1 match, found %d" % s.count(old))
open(f, "w").write(s.replace(old, new))
d = subprocess.run(["git", "-C", tree, "diff", "--", "bsd/dev/a5xelte_touch.c"],
                   capture_output=True, text=True, check=True).stdout
open(out, "w").write(d)
print("ok:", out, len(d.splitlines()), "diff lines")
