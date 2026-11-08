#!/usr/bin/env python3
# make-0164.py TREE OUT.patch
# S9+ survey (bsd/dev/a5xelte_touch.c, STAR2LTE only). Boot-arg s9survey=N:
#   1 = passive: log the six USI mode registers (0x10411000 page), dump the pin block
#       0x10430000 (hsi2c10 pins, gpp1) and the always-on block 0x14050000 (gpa0/1/2:
#       keys, touch IRQ) once, then for ~150 s log every CHANGED word of the AON block
#       ("S9SURVEY AON +off old -> new"). Press/hold each key to see its register + bit.
#   2 = level 1 + read the I2C controller 0x104B0000 registers, then probe the chip at
#       0x48 (reads command 0x55 and 0x52, S6SY761-lineage commands, only the ACK
#       matters). Clock 200 MHz (Linux value). NO rail, clock or pin is written.
#       RISK: if S-Boot left the I2C block clock-gated the first read may hang the boot.
# Needs a clean tree (git -C TREE commit -am 0163 first). Leaves the edit uncommitted.
# UNTESTED: not built by CI, not run on the phone. Register offsets are guesses to be
# confirmed by the log.
import re, subprocess, sys, pathlib

tree = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()

if subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                  capture_output=True, text=True, check=True).stdout.strip():
    sys.exit("tree not clean: git -C %s commit -am '<previous number>'" % tree)

f = tree / "bsd/dev/a5xelte_touch.c"
s = f.read_text()
if "s9survey" in s:
    sys.exit("s9survey already present")


def tabify(t):
    return re.sub(r"(?m)^((?:    )+)", lambda m: "\t" * (len(m.group(1)) // 4), t)


BLOCK = tabify(r'''
#if defined(STAR2LTE)
/*
 * S9+ survey (patch 0164). Boot-arg s9survey=1 passive, =2 also probes the
 * touch chip. Nothing here writes a rail, clock or pin register.
 */
#define S9_AON_PA       0x14050000u
#define S9_PIN_PA       0x10430000u
#define S9_USI_PA       0x10411000u
#define S9_I2C_PA       0x104b0000u
#define S9_I2C_CLKIN    200000000u
#define S9_I2C_SCL_HZ   400000u
#define S9_TS_ADDR      0x48u

static void
s9survey_dump(const char *tag, vm_offset_t base, unsigned len)
{
    for (unsigned o = 0; o < len; o += 16) {
        printf("S9SURVEY %s +%03x: %08x %08x %08x %08x\n", tag, o,
           a5touch_read(base, o), a5touch_read(base, o + 4),
           a5touch_read(base, o + 8), a5touch_read(base, o + 12));
    }
}

static void
s9i2c_reset(vm_offset_t bus)
{
    a5touch_write(bus, 0x00, a5touch_read(bus, 0x00) | (1u << 31));
    a5touch_write(bus, 0x00, a5touch_read(bus, 0x00) & ~(1u << 31));
    unsigned ftl = (a5touch_read(bus, 0x40) >> 16) & 7;
    unsigned temp = S9_I2C_CLKIN / S9_I2C_SCL_HZ - (ftl + 3) * 2;
    unsigned div = temp / 512;
    unsigned cyc = (temp + ((ftl + 3) % (div + 1)) * 2) / (div + 1) - 2;
    unsigned l = cyc * 64 / 100, h = cyc - l;
    a5touch_write(bus, 0x60, l << 24 | l << 16 | l << 8);
    a5touch_write(bus, 0x64, (l / 2) << 24 | l << 8 | h);
    a5touch_write(bus, 0x68, div << 16 | cyc);
    a5touch_write(bus, 0x6c, l / 2);
    a5touch_write(bus, 0x48, a5touch_read(bus, 0x48) & ~(1u << 31));
    a5touch_write(bus, 0x00, 0x9);
    a5touch_write(bus, 0x08, 0xf);
    a5touch_write(bus, 0x40, a5touch_read(bus, 0x40) | (1u << 31));
}

static bool
s9i2c_wait_done(vm_offset_t bus)
{
    for (unsigned us = 0; us < 20000; us++) {
        uint32_t st = a5touch_read(bus, 0x24);
        if (st & 0xf80u) {
            a5touch_write(bus, 0x24, st);
            if (st & 0xf00u) {
                printf("S9SURVEY i2c INT_STATUS %#x (abort/no-ack/no-dev/timeout)\n", st);
            }
            return !(st & 0xf00u);
        }
        delay(1);
    }
    printf("S9SURVEY i2c wait_done timed out, INT_STATUS %#x\n", a5touch_read(bus, 0x24));
    return false;
}

/* Write one command byte, then read rlen bytes (repeated start), STOP at the end. */
static bool
s9i2c_cmd_read(vm_offset_t bus, uint8_t cmd, uint8_t *r, unsigned rlen)
{
    a5touch_write(bus, 0x24, a5touch_read(bus, 0x24));
    a5touch_write(bus, 0x70, S9_TS_ADDR << 10);
    a5touch_write(bus, 0x20, 0xf80u);
    a5touch_write(bus, 0x04, 3);
    a5touch_write(bus, 0x00, 0x9 | 0x80);
    a5touch_write(bus, 0x44, 1u | (1u << 31));
    for (unsigned n = 0; n < 1000 && (a5touch_read(bus, 0x30) & (1u << 7)); n++) {
        delay(1);
    }
    a5touch_write(bus, 0x34, cmd);
    if (!s9i2c_wait_done(bus)) {
        goto fail;
    }
    a5touch_write(bus, 0x04, 3);
    a5touch_write(bus, 0x00, 0x9 | 0x40);
    a5touch_write(bus, 0x44, (1u << 16) | (1u << 17) | rlen | (1u << 31));
    for (unsigned i = 0; i < rlen; i++) {
        unsigned n = 0;
        while ((a5touch_read(bus, 0x30) & (1u << 24)) && n++ < 20000) {
            delay(1);
        }
        if (a5touch_read(bus, 0x30) & (1u << 24)) {
            goto fail;
        }
        r[i] = (uint8_t)a5touch_read(bus, 0x38);
    }
    if (!s9i2c_wait_done(bus)) {
        goto fail;
    }
    a5touch_write(bus, 0x00, 0x9);
    return true;
fail:
    s9i2c_reset(bus);
    return false;
}

static void
s9survey_thread(void *arg, wait_result_t result)
{
    int level = (int)(intptr_t)arg;
    vm_offset_t aon = ml_io_map(S9_AON_PA, 0x1000);
    vm_offset_t pin = ml_io_map(S9_PIN_PA, 0x1000);
    vm_offset_t usi = ml_io_map(S9_USI_PA, 0x1000);
    uint32_t prev[64];
    unsigned shown = 0;
    (void)result;
    if (!aon || !pin || !usi) {
        printf("S9SURVEY: MMIO mapping failed (aon %lx pin %lx usi %lx)\n",
           (unsigned long)aon, (unsigned long)pin, (unsigned long)usi);
        thread_terminate_self();
        return;
    }
    printf("S9SURVEY: start level %d\n", level);
    printf("S9SURVEY USI modes: 04=%08x 0c=%08x 14=%08x 1c=%08x 24=%08x 2c=%08x\n",
       a5touch_read(usi, 0x04), a5touch_read(usi, 0x0c), a5touch_read(usi, 0x14),
       a5touch_read(usi, 0x1c), a5touch_read(usi, 0x24), a5touch_read(usi, 0x2c));
    s9survey_dump("PIN", pin, 0x100);
    s9survey_dump("AON", aon, 0x100);

    if (level >= 2) {
        vm_offset_t i2c = ml_io_map(S9_I2C_PA, 0x1000);
        uint8_t b[3] = { 0, 0, 0 };
        if (!i2c) {
            printf("S9SURVEY: I2C mapping failed\n");
        } else {
            printf("S9SURVEY: reading I2C regs (a hang here = block clock gated)\n");
            s9survey_dump("I2C", i2c, 0x80);
            s9i2c_reset(i2c);
            if (s9i2c_cmd_read(i2c, 0x55, b, 1)) {
                printf("S9SURVEY: chip ACKed at 0x48, cmd 0x55 -> %02x\n", b[0]);
                if (s9i2c_cmd_read(i2c, 0x52, b, 3)) {
                    printf("S9SURVEY: cmd 0x52 -> %02x %02x %02x\n", b[0], b[1], b[2]);
                }
            } else {
                printf("S9SURVEY: no ACK from 0x48 (rails off, pins not muxed or clock/timing wrong)\n");
            }
        }
    }

    for (unsigned i = 0; i < 64; i++) {
        prev[i] = a5touch_read(aon, i * 4);
    }
    for (unsigned t = 0; t < 300; t++) {          /* ~150 s */
        for (unsigned k = 0; k < 100; k++) {
            a5touch_sleep_5ms();
        }
        for (unsigned i = 0; i < 64; i++) {
            uint32_t v = a5touch_read(aon, i * 4);
            if (v != prev[i] && shown < 400) {
                printf("S9SURVEY AON +%03x %08x -> %08x\n", i * 4, prev[i], v);
                shown++;
            }
            prev[i] = v;
        }
    }
    printf("S9SURVEY: done\n");
    thread_terminate_self();
}

static void
s9survey_start(void)
{
    int level = 0;
    thread_t thread;
    (void)PE_parse_boot_argn("s9survey", &level, sizeof(level));
    if (level <= 0) {
        return;
    }
    if (kernel_thread_start(s9survey_thread, (void *)(intptr_t)level, &thread) == KERN_SUCCESS) {
        thread_deallocate(thread);
    } else {
        printf("S9SURVEY: thread start failed\n");
    }
}
#endif /* S9SURVEY */
''')

# 1. survey code after the STAR2LTE battery stub, before a5xelte_touch_probe
pat1 = re.compile(r"(#endif /\* STAR2LTE \*/\n)")
if len(pat1.findall(s)) != 1:
    sys.exit("expected exactly one '#endif /* STAR2LTE */', found %d" % len(pat1.findall(s)))
s = pat1.sub(lambda m: m.group(1) + BLOCK, s)

# 2. call it at the top of a5xelte_touch_probe
pat2 = re.compile(r"(#if defined\(DREAMLTE\) && !defined\(STAR2LTE\)\n\tdreamlte_touch_start\(\);[^\n]*\n#endif\n)(\tint enabled = A5_TOUCH_DEFAULT;)")
if len(pat2.findall(s)) != 1:
    sys.exit("expected exactly one probe-entry anchor, found %d" % len(pat2.findall(s)))
s = pat2.sub(lambda m: m.group(1) + "#if defined(STAR2LTE)\n\ts9survey_start();\n#endif\n" + m.group(2), s)

f.write_text(s)

diff = subprocess.run(["git", "-C", str(tree), "diff"], capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff")
out.write_text(diff)
print("wrote", out)
