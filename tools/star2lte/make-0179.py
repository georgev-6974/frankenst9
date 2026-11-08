import subprocess, sys
tree, out = sys.argv[1], sys.argv[2]
f = tree + "/bsd/dev/a5xelte_touch.c"
s = open(f).read()

def rep(old, new):
    global s
    if s.count(old) != 1:
        sys.exit("expected 1 match, found %d for: %r" % (s.count(old), old[:50]))
    s = s.replace(old, new)

# 1. sleeping wait for the poll loop (same pattern as a5touch_sleep_5ms)
rep("""static bool
s9t_ldo(uint8_t reg, bool on)
""", """static int s9t_sleep_ev;

static void
s9t_sleep_ms(unsigned n)
{
    uint64_t deadline;
    clock_interval_to_deadline(n, NSEC_PER_MSEC, &deadline);
    (void)assert_wait_deadline(&s9t_sleep_ev, THREAD_UNINT, deadline);
    thread_block(THREAD_CONTINUE_NULL);
}

static bool
s9t_ldo(uint8_t reg, bool on)
""")
rep("        s9t_ms(4);\n    }\nout:", "        s9t_sleep_ms(4);\n    }\nout:")
# 2. default output range 1080 x 1920 (boot-args s9touch_w/h still override)
rep("uint32_t w = 0, h = 0;\n        (void)PE_parse_boot_argn(\"s9touch_w\"",
    "uint32_t w = 1080, h = 1920;\n        (void)PE_parse_boot_argn(\"s9touch_w\"")
open(f, "w").write(s)
d = subprocess.run(["git", "-C", tree, "diff", "--", "bsd/dev/a5xelte_touch.c"],
                   capture_output=True, text=True, check=True).stdout
open(out, "w").write(d)
print("ok:", out, len(d.splitlines()), "diff lines")
