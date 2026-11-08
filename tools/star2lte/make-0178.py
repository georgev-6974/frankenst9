#!/usr/bin/env python3
# make-0178.py TREE OUT.patch
# Fix for 0177 (chip never answered, err 1 = our timeout, INT_STATUS no flags):
# the other project's hsi2c driver clears USI_CON (+0xC4, reset value 1 holds the block in reset) before the
# controller reset, sets the timing from a 200 MHz input clock at 400 kHz, and runs a message as
# FIFO_CTL(triggers) / CTL(master|rx|tx) / ADDR / INT_EN / AUTO_CONF(len,read,stop) then RUN as a second write.
# This replaces our s9t_wait/s9t_write/s9t_read with that sequence, adds s9t_reset (used at stage 4) and a
# register dump on the first 3 failures. Needs a clean tree with 0177 committed. UNTESTED, not built.
import subprocess, sys, pathlib

tree = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()

if subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                  capture_output=True, text=True, check=True).stdout.strip():
    sys.exit("tree not clean: git -C %s commit -am '0177'" % tree)

f = tree / "bsd/dev/a5xelte_touch.c"
s = f.read_text()
if "s9t_thread" not in s:
    sys.exit("0177 not in this tree")
if "s9t_msg" in s:
    sys.exit("0178 already applied")

start = "/* ---- I2C: our own write (with STOP)"
end = "/* ---- events (layout from the S6SY761 driver"
if s.count(start) != 1 or s.count(end) != 1:
    sys.exit("region markers: %d / %d" % (s.count(start), s.count(end)))
i0 = s.index(start)
i1 = s.index(end)
if i1 < i0:
    sys.exit("markers out of order")

new_region = r'''/* ---- I2C (0178): the sequence of the other project's hsi2c driver; quiet except the first 3 failures ---- */
static uint32_t s9t_last_err;
static unsigned s9t_dumped;

static void
s9t_reset(vm_offset_t r)
{
    uint32_t div = 200u * 1000000u / (400000u * 15u);
    uint32_t n = (9u * 200u) / ((div + 1u) * 10u), m, scl_h, start_hd;

    a5touch_write(r, 0xc4, 0);                     /* USI_CON: its reset value 1 holds the block in reset */
    a5touch_write(r, 0x24, a5touch_read(r, 0x24));
    a5touch_write(r, 0x00, a5touch_read(r, 0x00) | (1u << 31));
    delay(10);
    a5touch_write(r, 0x00, a5touch_read(r, 0x00) & ~(1u << 31));
    if (n > 7) {
        n = 7;
    }
    scl_h = (0xffffffffu >> n << n) & 0xff;
    m = n ? n - 1 : 0;
    start_hd = (0xffffffffu >> m << m) & 0xff;
    a5touch_write(r, 0x68, (a5touch_read(r, 0x68) & ~(0xffu << 16)) | (div & 0xff) << 16);
    a5touch_write(r, 0x64, (a5touch_read(r, 0x64) & ~0xffu) | scl_h);
    a5touch_write(r, 0x60, (a5touch_read(r, 0x60) & ~(0xffu << 16)) | start_hd << 16);
    a5touch_write(r, 0x00, 1u << 3);
    a5touch_write(r, 0x08, 0xffffff);
    a5touch_write(r, 0x48, a5touch_read(r, 0x48) & ~(1u << 31));
    a5touch_write(r, 0x40, a5touch_read(r, 0x40) | (1u << 31));
}

static uint32_t
s9t_msg(vm_offset_t r, bool reading, uint8_t *buf, uint32_t len, bool stop)
{
    uint32_t trigger = len < 8 ? len : 8, done = 0, status = 0;
    bool finished = false;

    a5touch_write(r, 0x24, a5touch_read(r, 0x24));
    a5touch_write(r, 0x04, 0x3u | trigger << 4 | trigger << 16);
    a5touch_write(r, 0x00, (1u << 3) | (reading ? (1u << 6) : (1u << 7)));
    a5touch_write(r, 0x70, S9_TS_ADDR << 10);
    a5touch_write(r, 0x20, 0xf80u);
    a5touch_write(r, 0x44, len | (reading ? (1u << 16) : 0) | (stop ? (1u << 17) : 0));
    a5touch_write(r, 0x44, a5touch_read(r, 0x44) | (1u << 31));
    for (unsigned n = 0; n < 200000; n++) {
        uint32_t fifo = a5touch_read(r, 0x30);
        status = a5touch_read(r, 0x24);
        if (status & 0xf00u) {
            finished = true;
            break;
        }
        if (reading) {
            while (done < len && !(fifo & (1u << 24))) {
                buf[done++] = (uint8_t)a5touch_read(r, 0x38);
                fifo = a5touch_read(r, 0x30);
            }
            if (done == len) {
                finished = true;
                break;
            }
        } else {
            while (done < len && !(fifo & (1u << 7))) {
                a5touch_write(r, 0x34, buf[done++]);
                fifo = a5touch_read(r, 0x30);
            }
            if (done == len && (status & 0x80u) && (fifo & (1u << 8))) {
                finished = true;
                break;
            }
        }
        delay(5);
    }
    for (unsigned n = 0; n < 20000 && stop && (a5touch_read(r, 0x50) & (1u << 17)); n++) {
        delay(5);
    }
    if ((status & 0xf00u) || !finished) {
        uint32_t err = (status & 0xf00u) ? (status & 0xf00u) : 1;
        if (s9t_dumped < 3) {
            s9t_dumped++;
            printf("S9TOUCH i2c fail (%s len %u done %u): CTL %08x FIFO_CTL %08x INT_EN %08x INT_STAT %08x "
                "FIFO_STAT %08x CONF %08x AUTO %08x TIMEOUT %08x TRANS %08x FS1 %08x FS2 %08x FS3 %08x ADDR %08x "
                "USI_CON %08x\n", reading ? "read" : "write", len, done, a5touch_read(r, 0x00),
                a5touch_read(r, 0x04), a5touch_read(r, 0x20), a5touch_read(r, 0x24), a5touch_read(r, 0x30),
                a5touch_read(r, 0x40), a5touch_read(r, 0x44), a5touch_read(r, 0x48), a5touch_read(r, 0x50),
                a5touch_read(r, 0x60), a5touch_read(r, 0x64), a5touch_read(r, 0x68), a5touch_read(r, 0x70),
                a5touch_read(r, 0xc4));
        }
        s9t_reset(r);
        return err;
    }
    return 0;
}

static uint32_t
s9t_write(vm_offset_t bus, const uint8_t *d, unsigned len)
{
    uint8_t tmp[8];
    uint32_t e;

    if (len > sizeof(tmp)) {
        return 2;
    }
    for (unsigned i = 0; i < len; i++) {
        tmp[i] = d[i];
    }
    e = s9t_msg(bus, false, tmp, len, true);
    if (e) {
        s9t_last_err = e;
    }
    return e;
}

static uint32_t
s9t_read(vm_offset_t bus, uint8_t cmd, uint8_t *r, unsigned rlen)
{
    uint32_t e = 1;

    for (int attempt = 0; attempt < 2 && e != 0; attempt++) {
        e = s9t_msg(bus, false, &cmd, 1, true);
        if (e == 0) {
            e = s9t_msg(bus, true, r, rlen, true);
        }
    }
    if (e) {
        s9t_last_err = e;
    }
    return e;
}

'''
s = s[:i0] + new_region + s[i1:]

# the old s9t_last_err declaration lived inside the replaced region, so nothing is declared twice

old_reset = r'''    s9i2c_reset(i2c);

    printf("S9TOUCH 5: ask the chip at 0x%x\n", (unsigned)S9_TS_ADDR);'''
new_reset = r'''    printf("S9TOUCH 4: USI_CON %08x before reset\n", a5touch_read(i2c, 0xc4));
    s9t_reset(i2c);
    printf("S9TOUCH 4: after reset USI_CON %08x CTL %08x FS1 %08x FS2 %08x FS3 %08x\n", a5touch_read(i2c, 0xc4),
        a5touch_read(i2c, 0x00), a5touch_read(i2c, 0x60), a5touch_read(i2c, 0x64), a5touch_read(i2c, 0x68));

    printf("S9TOUCH 5: ask the chip at 0x%x\n", (unsigned)S9_TS_ADDR);'''
if s.count(old_reset) != 1:
    sys.exit("stage 4 anchor: found %d" % s.count(old_reset))
s = s.replace(old_reset, new_reset)

f.write_text(s)

diff = subprocess.run(["git", "-C", str(tree), "diff"], capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff")
out.write_text(diff)
print("wrote", out)
