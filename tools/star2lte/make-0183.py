#!/usr/bin/env python3
"""0183: battery bus (hsi2c_40 of CMGP) done properly, survey level 5 only.

Why: in 0182 every address "ACKed" and read 00. With the block's clock gated all registers read 0,
FIFO_STAT bit 24 (RX empty) reads 0 = "not empty", s9t_msg pops a 00 and calls it success.

What this does (s9survey=5):
  1. dumps the CMGP pin block (read only, nofault) so we can see which banks really are on function 2;
  2. reads the CMU_CMGP gates / Q-channel / divider and the USI mode word with the nofault probe;
     if one faults it writes NOTHING;
  3. forces the four gates on (bits 20+21), Q-channel |= 3, USI word 0x14212030 = 4  (claim: HakiOS);
  4. input clock = 400 / ((CMU div & 0xf) + 1) MHz (boot-arg s9bat_ipclk=N overrides), reset;
  5. sanity: idle FIFO_STAT must have RX-empty (bit 24) set, else "block is dead", no scan;
  6. control scan of addresses that cannot exist; any ACK = test broken, stop;
  7. real scan 0x08..0x77, then register reads for 0x25 0x36 0x66 0x69.
No pin writes. s9t_reset gets s9t_ipclk_mhz (default 200: touch is unchanged).

usage: make-0183.py WORK3/xnu OUT.patch      (tree must be clean: git -C WORK3/xnu commit -am 0182)
"""
import pathlib
import re
import subprocess
import sys

SRC = "bsd/dev/a5xelte_touch.c"

HELPERS = r'''/* 0183: nofault register read for the battery test; 0xdeadfa17 = the read faulted */
static uint32_t
s9bat_rd(vm_offset_t base, uint32_t off)
{
    uint32_t v = 0;

    if (s9_probe_read32(base + off, &v)) {
        return 0xdeadfa17u;
    }
    return v;
}

/* register read, first with a repeated start, then with STOP + START */
static bool
s9bat_read_reg(vm_offset_t bi, uint8_t addr, uint8_t reg, uint8_t *b, bool *rs)
{
    for (int pass = 0; pass < 2; pass++) {
        bool stop = (pass == 1);
        uint32_t e;

        s9t_addr = addr;
        s9t_last_err = 0;
        b[0] = b[1] = 0xee;
        e = s9t_msg(bi, false, &reg, 1, stop);
        if (e == 0) {
            e = s9t_msg(bi, true, b, 2, true);
        }
        if (e == 0) {
            *rs = !stop;
            return true;
        }
    }
    return false;
}

'''

TEST = r'''static void
s9bat_test(void)
{
    static const uint32_t gates[] = { 0x2014, 0x20a8, 0x20ac, 0x2074 };
    static const uint8_t ctl[] = { 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x7c, 0x7d, 0x7e, 0x7f };
    static const uint8_t devs[] = { 0x25, 0x36, 0x66, 0x69 };
    static const uint8_t regs[] = { 0x00, 0x01, 0x02, 0x05, 0x06, 0x08, 0x09, 0x0a };
    vm_offset_t bi = ml_io_map(0x14360000, 0x1000);
    vm_offset_t gp = ml_io_map(0x14220000, 0x1000);
    vm_offset_t cu = ml_io_map(0x14212000, 0x1000);
    vm_offset_t cm = ml_io_map(0x14200000, 0x4000);
    uint32_t arg = 0, div, ipclk = 400;
    uint8_t b[2];
    uint8_t acks[24];
    unsigned nacks = 0, bad = 0, i, k;
    bool rs;

    if (!bi || !gp || !cu || !cm) {
        printf("S9BAT: mapping failed\n");
        return;
    }

    /* 1. pin banks, read only */
    for (uint32_t o = 0; o < 0x400; o += 0x20) {
        printf("S9BAT: pins +%03x CON %08x DAT %08x PUD %08x\n", o, s9bat_rd(gp, o), s9bat_rd(gp, o + 4),
            s9bat_rd(gp, o + 8));
    }

    /* 2. clock and USI registers, read only */
    printf("S9BAT: cmu before: gates %08x %08x %08x %08x qch %08x div %08x mux %08x\n", s9bat_rd(cm, gates[0]),
        s9bat_rd(cm, gates[1]), s9bat_rd(cm, gates[2]), s9bat_rd(cm, gates[3]), s9bat_rd(cm, 0x3050),
        s9bat_rd(cm, 0x1814), s9bat_rd(cm, 0x1018));
    printf("S9BAT: usi +20: %08x %08x %08x %08x %08x %08x %08x %08x\n", s9bat_rd(cu, 0x20), s9bat_rd(cu, 0x24),
        s9bat_rd(cu, 0x28), s9bat_rd(cu, 0x2c), s9bat_rd(cu, 0x30), s9bat_rd(cu, 0x34), s9bat_rd(cu, 0x38),
        s9bat_rd(cu, 0x3c));
    for (i = 0; i < 4; i++) {
        if (s9bat_rd(cm, gates[i]) == 0xdeadfa17u) {
            bad++;
        }
    }
    if (s9bat_rd(cm, 0x3050) == 0xdeadfa17u || s9bat_rd(cu, 0x30) == 0xdeadfa17u) {
        bad++;
    }
    if (bad) {
        printf("S9BAT: a clock or USI register faulted: nothing written, stop\n");
        return;
    }

    /* 3. clocks on, USI to I2C */
    for (i = 0; i < 4; i++) {
        a5touch_write(cm, gates[i], a5touch_read(cm, gates[i]) | (3u << 20));
    }
    a5touch_write(cm, 0x3050, a5touch_read(cm, 0x3050) | 3u);
    a5touch_write(cu, 0x30, 4);
    printf("S9BAT: cmu after: gates %08x %08x %08x %08x qch %08x, usi +30 %08x\n", a5touch_read(cm, gates[0]),
        a5touch_read(cm, gates[1]), a5touch_read(cm, gates[2]), a5touch_read(cm, gates[3]),
        a5touch_read(cm, 0x3050), a5touch_read(cu, 0x30));

    /* 4. input clock, reset */
    div = s9bat_rd(cm, 0x1814);
    if (div != 0xdeadfa17u) {
        ipclk = 400u / ((div & 0xfu) + 1u);
    }
    (void)PE_parse_boot_argn("s9bat_ipclk", &arg, sizeof(arg));
    if (arg) {
        ipclk = arg;
    }
    if (ipclk < 26 || ipclk > 400) {
        ipclk = 400;
    }
    s9t_ipclk_mhz = ipclk;
    printf("S9BAT: input clock taken as %u MHz\n", ipclk);
    s9t_reset(bi);
    printf("S9BAT: after reset USI_CON %08x CTL %08x INT_STAT %08x FIFO_STAT %08x FS1 %08x FS2 %08x FS3 %08x\n",
        a5touch_read(bi, 0xc4), a5touch_read(bi, 0x00), a5touch_read(bi, 0x24), a5touch_read(bi, 0x30),
        a5touch_read(bi, 0x60), a5touch_read(bi, 0x64), a5touch_read(bi, 0x68));

    /* 5. sanity: an idle block has an empty RX FIFO */
    if (!(a5touch_read(bi, 0x30) & (1u << 24))) {
        printf("S9BAT: FIFO_STAT shows RX not empty while idle: block is dead (clock or reset), no scan\n");
        goto out;
    }

    /* 6. control scan: these addresses cannot exist */
    bad = 0;
    for (i = 0; i < sizeof(ctl); i++) {
        s9t_addr = ctl[i];
        s9t_last_err = 0;
        if (s9t_msg(bi, true, b, 1, true) == 0) {
            printf("S9BAT: control 0x%02x ACKED (test is broken)\n", ctl[i]);
            bad++;
        }
    }
    printf("S9BAT: control scan: %u of %u wrongly ACKed\n", bad, (unsigned)sizeof(ctl));
    if (bad) {
        goto out;
    }

    /* 7. real scan, then registers */
    for (uint32_t a = 0x08; a < 0x78 && nacks <= sizeof(acks); a++) {
        s9t_addr = a;
        s9t_last_err = 0;
        if (s9t_msg(bi, true, b, 1, true) == 0 && s9t_last_err == 0) {
            printf("S9BAT: ACK at 0x%02x (read %02x)\n", a, b[0]);
            if (nacks < sizeof(acks)) {
                acks[nacks] = (uint8_t)a;
            }
            nacks++;
        }
    }
    printf("S9BAT: scan done, %u ACKs\n", nacks);
    for (i = 0; i < nacks && i < sizeof(acks); i++) {
        bool known = false;

        for (k = 0; k < sizeof(devs); k++) {
            if (acks[i] == devs[k]) {
                known = true;
            }
        }
        if (!known) {
            continue;
        }
        for (k = 0; k < sizeof(regs); k++) {
            if (s9bat_read_reg(bi, acks[i], regs[k], b, &rs)) {
                printf("S9BAT: %02x reg %02x -> %02x %02x (%s)\n", acks[i], regs[k], b[0], b[1],
                    rs ? "repeated start" : "stop then start");
            } else {
                printf("S9BAT: %02x reg %02x failed\n", acks[i], regs[k]);
            }
        }
    }
out:
    s9t_ipclk_mhz = 200;
    s9t_addr = S9_TS_ADDR;
    s9t_last_err = 0;
}

'''


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
        sys.exit("tree not clean, run: git -C %s commit -am 0182\n%s" % (tree, dirty))
    text = f.read_text()
    if "s9t_ipclk_mhz" in text:
        sys.exit("already applied (s9t_ipclk_mhz exists)")

    # s9t_reset: input clock becomes a variable (default 200, touch unchanged)
    old1 = "    uint32_t div = 200u * 1000000u / (400000u * 15u);\n"
    old2 = "    uint32_t n = (9u * 200u) / ((div + 1u) * 10u), m, scl_h, start_hd;\n"
    if text.count(old1) != 1 or text.count(old2) != 1:
        sys.exit("s9t_reset timing lines not found exactly once")
    text = text.replace(old1, "    uint32_t div = s9t_ipclk_mhz * 1000000u / (400000u * 15u);\n")
    text = text.replace(old2, "    uint32_t n = (9u * s9t_ipclk_mhz) / ((div + 1u) * 10u), m, scl_h, start_hd;\n")
    m = re.search(r"static void\ns9t_reset\(vm_offset_t r\)\n\{", text)
    if not m:
        sys.exit("s9t_reset definition not found")
    text = text[:m.start()] + "static uint32_t s9t_ipclk_mhz = 200;   /* input clock of the bus being reset, MHz */\n\n" + \
        text[m.start():]

    # s9bat_test: replace the whole function
    m = re.search(r"static void\ns9bat_test\(void\)\n\{", text)
    if not m:
        sys.exit("s9bat_test definition not found")
    end = text.find("static void\ns9t_thread(void *arg", m.end())
    if end < 0:
        sys.exit("s9t_thread not found after s9bat_test")
    if text.find("s9_probe_read32") < 0 or text.find("s9_probe_read32") > m.start():
        sys.exit("s9_probe_read32 is not declared before s9bat_test")
    for new in (HELPERS, TEST):
        if new.count("{") != new.count("}"):
            sys.exit("unbalanced braces in the new C code")
    text = text[:m.start()] + HELPERS + TEST + text[end:]
    f.write_text(text)

    diff = subprocess.run(["git", "-C", str(tree), "diff", "--no-color"], capture_output=True, check=True).stdout
    out.write_bytes(diff)
    print("wrote %s (%d bytes, %d lines)" % (out, len(diff), diff.count(b"\n")))


if __name__ == "__main__":
    main()
