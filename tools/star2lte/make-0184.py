#!/usr/bin/env python3
"""0184: 0183 plus the two battery-bus pins (gpm14-0, gpm15-0) set to I2C function. Survey level 5 only.

Why: 0183 ran clean (control scan 0 of 10 wrongly ACKed) but the scan found 0 ACKs. The pin dump shows
S-Boot left gpm14/gpm15 as GPIO outputs (CON 1, DAT 1, PUD 0), not function 2.

Bank offsets are derived from the dt alias order (gpm0..7, gpm10..13, gpm14, gpm15, gpm16, gpm17), 0x20 apart:
gpm14 = +0x180, gpm15 = +0x1a0 of pinctrl@14220000. (0182 wrote +0x1c0/+0x1e0 = gpm16/gpm17: wrong banks.)
dt hsi2c40-bus: pins "gpm14-0", "gpm15-0", function 2, pud 0, drv 0.

What changes vs 0183:
  1. the pin dump covers only +160 +180 +1a0 +1c0 (before AND after the write);
  2. after the clocks are on and before the reset: for the banks +180 and +1a0, read CON and PUD with the
     nofault probe; if one faults it writes nothing; else CON low nibble = 2, PUD bits 1:0 = 0, read back.
Everything else is 0183 unchanged. Only the two pin registers of each bank are written (pin 0 only).

usage: make-0184.py WORK3/xnu OUT.patch      (tree must be clean: git -C WORK3/xnu commit -am 0183)
"""
import pathlib
import subprocess
import sys

SRC = "bsd/dev/a5xelte_touch.c"

OLD_DUMP = "    for (uint32_t o = 0; o < 0x400; o += 0x20) {\n"
NEW_DUMP = "    for (uint32_t o = 0x160; o <= 0x1c0; o += 0x20) {\n"

MARK = "    /* 4. input clock, reset */\n"

PINS = r'''    /* 3b. 0184: gpm14-0 / gpm15-0 to function 2, no pull (dt hsi2c40-bus). Banks +0x180 / +0x1a0 are
     * derived from the dt alias order, not measured: the dumps before and after show what really changed. */
    {
        static const uint32_t pbank[] = { 0x180, 0x1a0 };
        unsigned pi;

        for (pi = 0; pi < 2; pi++) {
            uint32_t o = pbank[pi];
            uint32_t con = s9bat_rd(gp, o);
            uint32_t pud = s9bat_rd(gp, o + 8);

            if (con == 0xdeadfa17u || pud == 0xdeadfa17u) {
                printf("S9BAT: pin write +%03x skipped, register faulted\n", o);
                continue;
            }
            printf("S9BAT: pin write +%03x CON %08x PUD %08x -> ", o, con, pud);
            a5touch_write(gp, o, (con & ~0xfu) | 2u);
            a5touch_write(gp, o + 8, pud & ~3u);
            printf("CON %08x PUD %08x\n", a5touch_read(gp, o), a5touch_read(gp, o + 8));
        }
        for (uint32_t o = 0x160; o <= 0x1c0; o += 0x20) {
            printf("S9BAT: pins after +%03x CON %08x DAT %08x PUD %08x\n", o, s9bat_rd(gp, o),
                s9bat_rd(gp, o + 4), s9bat_rd(gp, o + 8));
        }
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
        sys.exit("tree not clean, run: git -C %s commit -am 0183\n%s" % (tree, dirty))
    text = f.read_text()
    if "S9BAT: pin write" in text:
        sys.exit("already applied (pin write exists)")
    if "S9BAT: control scan" not in text:
        sys.exit("0183 is not in this tree (no 'S9BAT: control scan')")
    for needle in (OLD_DUMP, MARK):
        if text.count(needle) != 1:
            sys.exit("expected exactly once, found %d: %r" % (text.count(needle), needle))
    if PINS.count("{") != PINS.count("}"):
        sys.exit("unbalanced braces in the new C code")
    text = text.replace(OLD_DUMP, NEW_DUMP)
    text = text.replace(MARK, PINS + MARK)
    f.write_text(text)

    diff = subprocess.run(["git", "-C", str(tree), "diff", "--no-color"], capture_output=True, check=True).stdout
    out.write_bytes(diff)
    print("wrote %s (%d bytes, %d lines)" % (out, len(diff), diff.count(b"\n")))


if __name__ == "__main__":
    main()
