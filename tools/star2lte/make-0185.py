#!/usr/bin/env python3
"""0185: the S9+ battery read for iOS (SweetBattery), no new boot arg.

Why: iokit/Kernel/arm/SweetBattery.cpp already publishes an IOPMPowerSource and calls dreamlte_battery_read().
On STAR2LTE that function was a stub returning -1, so SweetBattery fell back to "100 %, AC, full". 0184 proved the
battery bus works (gauge 0x36, charger 0x69). This patch makes the function real. SweetBattery.cpp is NOT changed.

What it does:
  1. dreamlte_battery_read() (STAR2LTE) calls the new s9bat_read(), defined after s9bat_rd / s9t_msg;
  2. s9bat_init(), once: the 0184 setup (CMU gates on, USI word 4, gpm14-0/gpm15-0 to function 2 with no pull, bus reset),
     every register read first with the nofault probe; if anything faults or the idle FIFO is not empty it stays off;
  3. s9bat_read(): gauge 0x36 regs 0x00 status, 0x06 RepSOC (1/256 %), 0x09 VCELL (78.125 uV), 0x0A current
     (312.5 uA per step, > 0 while charging = IOPMPowerSource's sign); charger 0x69 regs 0xB2 (bits 6:5 = USB / wireless
     input) and 0xB4 (low nibble 0-2 charging, 3-4 full); a failed charger read means "not connected", the gauge
     values are still reported; the voltage must be 2800..4600 mV or the fallback is used;
  3b. temperature is NOT read (the gauge's register is not the real one on this phone; SweetBattery keeps 25 C);
  4. the touch thread and the battery now do not share transfer state: s9t_msg takes the address of the battery bus
     from s9bat_addr and s9t_reset takes its input clock from s9bat_clk, chosen by the bus mapping (r == s9bat_bus).
     Touch code and the survey are unchanged (their bus is a different mapping);
  5. the service stays OFF while the boot arg s9survey is set (the survey drives the same bus), so boot normally
     without s9survey to get the battery in iOS;
  6. the first 40 reads (30 s apart) and every change of cable/charging are logged as "S9BAT svc: ...".

usage: do NOT run this by hand: s9push 0185 battery-service  (it commits the tree first and runs this generator)
"""
import pathlib
import re
import subprocess
import sys

SRC = "bsd/dev/a5xelte_touch.c"

DECL = '''static vm_offset_t s9bat_bus;          /* the battery bus mapping once the service is up (0 before) */
static uint32_t s9bat_addr, s9bat_clk = 400;   /* its target address and input clock; used only for s9bat_bus */
'''

CODE = r'''/* ---- 0185: the S9+ battery for SweetBattery (iokit/Kernel/arm/SweetBattery.cpp) ---- */
#define S9BAT_GAUGE     0x36u
#define S9BAT_CHARGER   0x69u

static int s9bat_state;     /* 0 not tried, 1 up, -1 off */

/* register read of the battery bus: address register, repeated start, then len bytes (what 0184 proved) */
static int
s9b_read(uint32_t addr, uint8_t reg, uint8_t *buf, uint32_t len)
{
    uint32_t e = 1;

    for (int attempt = 0; attempt < 2 && e != 0; attempt++) {
        s9bat_addr = addr;
        e = s9t_msg(s9bat_bus, false, &reg, 1, false);
        if (e == 0) {
            e = s9t_msg(s9bat_bus, true, buf, len, true);
        }
    }
    return e ? -1 : 0;
}

/* a 16-bit little-endian gauge register */
static int
s9b_rd16(uint8_t reg, uint32_t *v)
{
    uint8_t b[2] = { 0, 0 };

    if (s9b_read(S9BAT_GAUGE, reg, b, 2)) {
        return -1;
    }
    *v = (uint32_t)b[0] | ((uint32_t)b[1] << 8);
    return 0;
}

static int
s9bat_init(void)
{
    static const uint32_t gates[] = { 0x2014, 0x20a8, 0x20ac, 0x2074 };
    uint32_t sv = 0, div, ipclk = 400, con, pud;
    vm_offset_t bi, gp, cu, cm;
    unsigned i;

    (void)PE_parse_boot_argn("s9survey", &sv, sizeof(sv));
    if (sv) {
        printf("S9BAT svc: off while s9survey is set\n");
        return -1;
    }
    bi = ml_io_map(0x14360000, 0x1000);
    gp = ml_io_map(0x14220000, 0x1000);
    cu = ml_io_map(0x14212000, 0x1000);
    cm = ml_io_map(0x14200000, 0x4000);
    if (!bi || !gp || !cu || !cm) {
        printf("S9BAT svc: mapping failed\n");
        return -1;
    }
    for (i = 0; i < 4; i++) {
        if (s9bat_rd(cm, gates[i]) == 0xdeadfa17u) {
            printf("S9BAT svc: clock gate register faulted, off\n");
            return -1;
        }
    }
    if (s9bat_rd(cm, 0x3050) == 0xdeadfa17u || s9bat_rd(cu, 0x30) == 0xdeadfa17u) {
        printf("S9BAT svc: Q-channel or USI register faulted, off\n");
        return -1;
    }
    for (i = 0; i < 2; i++) {
        uint32_t o = i ? 0x1a0 : 0x180;     /* gpm15 / gpm14, from the dt alias order (confirmed by 0184) */

        if (s9bat_rd(gp, o) == 0xdeadfa17u || s9bat_rd(gp, o + 8) == 0xdeadfa17u) {
            printf("S9BAT svc: pin register +%03x faulted, off\n", o);
            return -1;
        }
    }
    for (i = 0; i < 4; i++) {
        a5touch_write(cm, gates[i], a5touch_read(cm, gates[i]) | (3u << 20));
    }
    a5touch_write(cm, 0x3050, a5touch_read(cm, 0x3050) | 3u);
    a5touch_write(cu, 0x30, 4);
    for (i = 0; i < 2; i++) {
        uint32_t o = i ? 0x1a0 : 0x180;

        con = a5touch_read(gp, o);
        pud = a5touch_read(gp, o + 8);
        a5touch_write(gp, o, (con & ~0xfu) | 2u);
        a5touch_write(gp, o + 8, pud & ~3u);
    }
    div = s9bat_rd(cm, 0x1814);
    if (div != 0xdeadfa17u) {
        ipclk = 400u / ((div & 0xfu) + 1u);
    }
    if (ipclk < 26 || ipclk > 400) {
        ipclk = 400;
    }
    s9bat_clk = ipclk;
    s9bat_bus = bi;
    s9t_reset(bi);
    if (!(a5touch_read(bi, 0x30) & (1u << 24))) {
        printf("S9BAT svc: FIFO_STAT shows RX not empty while idle: block is dead, off\n");
        s9bat_bus = 0;
        return -1;
    }
    printf("S9BAT svc: bus up, input clock %u MHz\n", ipclk);
    return 0;
}

static int
s9bat_read(unsigned *percent, unsigned *mv, int *ma, int *external, int *charging, int *full)
{
    static unsigned calls;
    static int last_ext = -1, last_chg = -1;
    uint8_t ok = 0, dtls = 0x0f;
    uint32_t status = 0, soc = 0, vcell = 0, cur = 0;
    bool chg_ok;
    unsigned pct;

    if (s9bat_state == 0) {
        s9bat_state = (s9bat_init() == 0) ? 1 : -1;
    }
    if (s9bat_state < 0) {
        return -1;
    }
    if (s9b_rd16(0x00, &status) || s9b_rd16(0x06, &soc) || s9b_rd16(0x09, &vcell) || s9b_rd16(0x0a, &cur)) {
        if (calls < 40) {
            printf("S9BAT svc: gauge read failed\n");
        }
        calls++;
        return -1;
    }
    chg_ok = !s9b_read(S9BAT_CHARGER, 0xb2, &ok, 1) && !s9b_read(S9BAT_CHARGER, 0xb4, &dtls, 1);
    if (!chg_ok) {
        ok = 0;
        dtls = 0x0f;
    }
    if (status & (1u << 3)) {
        return -1;      /* the gauge says: no battery */
    }
    pct = (unsigned)(soc >> 8) + (((soc & 0xffu) >= 128) ? 1u : 0u);
    *percent = pct > 100 ? 100 : pct;
    *mv = (unsigned)((uint64_t)vcell * 78125u / 1000000u);
    *ma = (int)((int16_t)cur) * 3125 / 10000;       /* 312.5 uA per step; > 0 while charging */
    *external = (ok & (3u << 5)) != 0;              /* the USB input or the wireless one */
    dtls &= 0x0f;
    *charging = *external && dtls <= 2;
    *full = *external && (dtls == 3 || dtls == 4);
    if (calls < 40 || *external != last_ext || *charging != last_chg) {
        printf("S9BAT svc: %u%% %u mV %d mA ext=%d chg=%d full=%d (soc %04x vcell %04x cur %04x b2 %02x b4 %02x "
            "charger %s)\n", *percent, *mv, *ma, *external, *charging, *full, (unsigned)soc, (unsigned)vcell,
            (unsigned)cur, ok, dtls, chg_ok ? "ok" : "read failed");
    }
    calls++;
    last_ext = *external;
    last_chg = *charging;
    return (*mv >= 2800 && *mv <= 4600) ? 0 : -1;
}

'''

STUB_RE = re.compile(
    r"int\ndreamlte_battery_read\(unsigned \*percent, unsigned \*mv, int \*ma,\s+"
    r"int \*external, int \*charging, int \*full\)\n\{\n"
    r"\s*\(void\)percent;[^\n]*\n\s*return -1;\n\}\n")

NEW_STUB = '''static int s9bat_read(unsigned *percent, unsigned *mv, int *ma, int *external, int *charging, int *full);

int
dreamlte_battery_read(unsigned *percent, unsigned *mv, int *ma,
    int *external, int *charging, int *full)
{
\treturn s9bat_read(percent, mv, ma, external, charging, full);
}
'''


def once(text, needle, what):
    n = text.count(needle)
    if n != 1:
        sys.exit("%s: expected exactly once, found %d" % (what, n))


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    tree = pathlib.Path(sys.argv[1])
    out = pathlib.Path(sys.argv[2])
    f = tree / SRC
    if not f.is_file():
        sys.exit("not found: %s" % f)
    dirty = subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                           capture_output=True, text=True, check=True).stdout.strip()
    if dirty:
        sys.exit("tree not clean (s9push commits it first; do not run this by hand):\n%s" % dirty)
    text = f.read_text()
    if "s9bat_read(" in text:
        sys.exit("already applied (s9bat_read exists)")
    if "S9BAT: pin write" not in text:
        sys.exit("0184 is not in this tree (no 'S9BAT: pin write')")

    # 1. the stub -> forward declaration + call
    stubs = STUB_RE.findall(text)
    if len(stubs) != 1:
        sys.exit("STAR2LTE battery stub: expected exactly once, found %d" % len(stubs))
    text = STUB_RE.sub(lambda m: NEW_STUB, text, count=1)

    # 2. per-bus settings for the battery bus
    m = re.search(r"static uint32_t s9t_ipclk_mhz = 200;[^\n]*\n", text)
    if not m or len(re.findall(r"static uint32_t s9t_ipclk_mhz = 200;", text)) != 1:
        sys.exit("s9t_ipclk_mhz declaration not found exactly once")
    text = text[:m.end()] + DECL + text[m.end():]

    old_div = "    uint32_t div = s9t_ipclk_mhz * 1000000u / (400000u * 15u);\n"
    old_n = "    uint32_t n = (9u * s9t_ipclk_mhz) / ((div + 1u) * 10u), m, scl_h, start_hd;\n"
    old_addr = "    a5touch_write(r, 0x70, s9t_addr << 10);\n"
    for needle, what in ((old_div, "s9t_reset div"), (old_n, "s9t_reset n"), (old_addr, "s9t_msg address")):
        once(text, needle, what)
    clk = "((r == s9bat_bus) ? s9bat_clk : s9t_ipclk_mhz)"
    text = text.replace(old_div, "    uint32_t div = %s * 1000000u / (400000u * 15u);\n" % clk)
    text = text.replace(old_n, "    uint32_t n = (9u * %s) / ((div + 1u) * 10u), m, scl_h, start_hd;\n" % clk)
    text = text.replace(old_addr, "    a5touch_write(r, 0x70, ((r == s9bat_bus) ? s9bat_addr : s9t_addr) << 10);\n")

    # 3. the new code, after s9bat_rd / s9t_msg and before the survey's test
    anchor = "static void\ns9bat_test(void)\n{"
    once(text, anchor, "s9bat_test")
    if text.find("s9bat_rd(vm_offset_t") < 0 or text.find("s9bat_rd(vm_offset_t") > text.find(anchor):
        sys.exit("s9bat_rd is not defined before s9bat_test")
    if CODE.count("{") != CODE.count("}") or NEW_STUB.count("{") != NEW_STUB.count("}"):
        sys.exit("unbalanced braces in the new C code")
    text = text.replace(anchor, CODE + anchor)
    f.write_text(text)

    diff = subprocess.run(["git", "-C", str(tree), "diff", "--no-color"], capture_output=True, check=True).stdout
    out.write_bytes(diff)
    print("wrote %s (%d bytes, %d lines)" % (out, len(diff), diff.count(b"\n")))


if __name__ == "__main__":
    main()
