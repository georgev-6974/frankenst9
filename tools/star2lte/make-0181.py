import subprocess, sys
tree, out = sys.argv[1], sys.argv[2]
f = tree + "/bsd/dev/a5xelte_touch.c"
s = open(f).read()

def rep(old, new):
    global s
    if s.count(old) != 1:
        sys.exit("expected 1 match, found %d for: %r" % (s.count(old), old[:40]))
    s = s.replace(old, new)

# forward declarations: the survey thread is defined before the ACPM helpers
rep("static void\ns9survey_thread(",
    "static bool s9a_setup(void);\nstatic int s9a_pmic_read(uint32_t type, uint32_t reg, uint8_t *v);\n"
    "static void s9t_ms(unsigned n);\n\nstatic void\ns9survey_thread(")
# read-only RTC dump (ACPM PMIC block 2), twice, 2 s apart, no writes
rep('\t\tprintf("S9SURVEY P5: done\\n");\n',
'''\t\t/* 0181: S2MPS18 RTC (ACPM type 2, regs 0..0xB), read-only, twice 2 s apart */
\t\tif (s9a_setup()) {
\t\t\tfor (int pass = 0; pass < 2; pass++) {
\t\t\t\tuint8_t r[12] = { 0 };
\t\t\t\tint nb = 0;
\t\t\t\tfor (uint32_t i = 0; i < 12; i++) {
\t\t\t\t\tif (s9a_pmic_read(2, i, &r[i]) != 0) {
\t\t\t\t\t\tnb++;
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\tprintf("S9SURVEY RTC%d: bad %d CTRL %02x UPD %02x CAP %02x MS %02x S %02x M %02x H %02x W %02x D %02x MO %02x Y %02x\\n",
\t\t\t\t   pass, nb, r[0], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11]);
\t\t\t\ts9t_ms(2000);
\t\t\t}
\t\t} else {
\t\t\tprintf("S9SURVEY RTC: ACPM setup failed\\n");
\t\t}
\t\tprintf("S9SURVEY P5: done\\n");
''')
open(f, "w").write(s)
d = subprocess.run(["git", "-C", tree, "diff", "--", "bsd/dev/a5xelte_touch.c"],
                   capture_output=True, text=True, check=True).stdout
open(out, "w").write(d)
print("ok:", out, len(d.splitlines()), "diff lines")
