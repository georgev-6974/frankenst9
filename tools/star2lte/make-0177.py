#!/usr/bin/env python3
# make-0177.py TREE OUT.patch
# Real touch for the S9+ (boot-arg s9touch=1: log raw events only, s9touch=2: also feed sweet_hid_touch).
# Stages, each logged as "S9TOUCH ...", stop at the first hard failure (no panic by design):
#   1 map  2 ACPM init (channel 2 = PMIC)  3 read LDO35/LDO43, switch on if off  4 USI word + pins + I2C reset
#   5 probe 0x48 (power-cycle the rails up to 2 times if no ACK)  6 chip init  7 polled event loop.
# Facts from the other project (HakiOS, S9): ACPM mailbox 0x14100000, SRAM 0x02039000 (+0x3000 up), initdata +0x7F00,
# PMIC block 1 regs LDO35 0x6c / LDO43 0x74 (on = bits 7:6 set), S6SY761 command set. NOT measured on our boot.
# Boot-args: s9touch=1|2, s9touch_w / s9touch_h = HID output range (default 1440 x 2960).
# Needs a clean tree (git -C TREE commit -am 0176 first). UNTESTED, not built.
import subprocess, sys, pathlib

tree = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()

if subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                  capture_output=True, text=True, check=True).stdout.strip():
    sys.exit("tree not clean: git -C %s commit -am '0176'" % tree)

f = tree / "bsd/dev/a5xelte_touch.c"
s = f.read_text()
if "level == 13" not in s:
    sys.exit("0175 not in this tree")
if "s9t_thread" in s:
    sys.exit("0177 already applied")

end_anchor = "#endif /* S9SURVEY */\n"
if s.count(end_anchor) != 1:
    sys.exit("S9SURVEY endif anchor: found %d" % s.count(end_anchor))
call_anchor = "#if defined(STAR2LTE)\n\ts9survey_start();\n#endif\n"
if s.count(call_anchor) != 1:
    sys.exit("probe call anchor: found %d" % s.count(call_anchor))

block = r'''
/* ---- S9TOUCH (0177): ACPM rails + polled S6SY761 (sec_ts) on hsi2c@104B0000 ---- */
#define S9A_MBOX_PA     0x14100000UL
#define S9A_SRAM_PA     0x02039000UL
#define S9A_SRAM_FIRST  0x3000u
#define S9A_SRAM_SIZE   0x30000u
#define S9A_INITDATA    0x7f00u
#define S9A_CH          2u
#define S9A_CH_SIZE     0x48u
#define S9T_LDO35       0x6c
#define S9T_LDO43       0x74
#define S9T_FINGERS     10

static vm_offset_t s9a_mbox, s9a_sram;
static struct {
    bool usable;
    uint32_t in_rear, in_front, in_base, out_rear, out_front, out_base, len, elem, seq;
} s9a_c;

static inline uint32_t
s9a_rd(uint32_t off)
{
    return *(volatile uint32_t *)(s9a_sram + (off - S9A_SRAM_FIRST));
}

static inline void
s9a_wr(uint32_t off, uint32_t v)
{
    *(volatile uint32_t *)(s9a_sram + (off - S9A_SRAM_FIRST)) = v;
}

static inline uint32_t
s9a_mrd(uint32_t off)
{
    return *(volatile uint32_t *)(s9a_mbox + off);
}

static inline void
s9a_mwr(uint32_t off, uint32_t v)
{
    *(volatile uint32_t *)(s9a_mbox + off) = v;
}

static bool
s9a_ok(uint32_t off, uint32_t bytes)
{
    return off >= S9A_SRAM_FIRST && off <= S9A_SRAM_SIZE && bytes <= S9A_SRAM_SIZE - off && (off & 3) == 0;
}

static uint8_t
s9a_byte(uint32_t off)
{
    return (uint8_t)(s9a_rd(off & ~3u) >> (8 * (off & 3)));
}

static bool
s9a_text(uint32_t off, uint32_t len)
{
    for (uint32_t i = 0; i < len; i++) {
        uint8_t c = s9a_byte(off + i);
        if (c == 0) {
            return i > 0;
        }
        if (c < 0x20 || c > 0x7e) {
            return false;
        }
    }
    return true;
}

static void
s9a_drain(void)
{
    uint32_t front = s9a_rd(s9a_c.out_front);
    if (front < s9a_c.len && s9a_rd(s9a_c.out_rear) != front) {
        s9a_wr(s9a_c.out_rear, front);
    }
    s9a_mwr(0x20, 1u << S9A_CH);
}

static bool
s9a_take(uint32_t seq, uint32_t cmd[4])
{
    uint32_t rear = s9a_rd(s9a_c.out_rear), front = s9a_rd(s9a_c.out_front);
    bool found = false;

    if (rear >= s9a_c.len || front >= s9a_c.len || (rear == front && !(s9a_mrd(0x28) & (1u << S9A_CH)))) {
        return false;
    }
    for (uint32_t i = rear; i != front; i = (i + 1) % s9a_c.len) {
        uint32_t slot = s9a_c.out_base + i * s9a_c.elem;
        if (((s9a_rd(slot) >> 16) & 0x3fu) == seq) {
            for (uint32_t w = 0; w < 4; w++) {
                cmd[w] = s9a_rd(slot + 4 * w);
            }
            found = true;
        }
    }
    s9a_drain();
    return found;
}

static int
s9a_request(uint32_t cmd[4])
{
    uint32_t sent[4], front, next;

    if (!s9a_c.usable) {
        return 1;
    }
    for (int w = 0; w < 4; w++) {
        sent[w] = cmd[w];
    }
    for (int send = 0; send < 3; send++) {
        s9a_drain();
        front = s9a_rd(s9a_c.in_front);
        if (front >= s9a_c.len) {
            return 2;
        }
        next = (front + 1) % s9a_c.len;
        for (unsigned n = 0; n < 400 && s9a_rd(s9a_c.in_rear) == next; n++) {
            delay(50);
        }
        if (s9a_rd(s9a_c.in_rear) == next) {
            continue;
        }
        s9a_c.seq = s9a_c.seq % 63 + 1;
        sent[0] = (sent[0] & ~(0x3fu << 16)) | (s9a_c.seq << 16);
        for (uint32_t w = 0; w < 4; w++) {
            s9a_wr(s9a_c.in_base + front * s9a_c.elem + 4 * w, sent[w]);
        }
        __builtin_arm_dsb(0xf);
        s9a_wr(s9a_c.in_front, next);
        __builtin_arm_dsb(0xf);
        s9a_mwr(0x08, 1u << (16 + S9A_CH));
        for (unsigned n = 0; n < 12000; n++) {
            if (s9a_take(s9a_c.seq, cmd)) {
                return 0;
            }
            delay(50);
        }
    }
    return 3;
}

static int
s9a_pmic_read(uint32_t type, uint32_t reg, uint8_t *v)
{
    uint32_t cmd[4] = { (type & 0xf) << 8 | (reg & 0xff), 0, 0, 0 };
    int e = s9a_request(cmd);
    if (e == 0 && (cmd[1] >> 24) != 0) {
        e = 5;
    }
    if (e == 0) {
        *v = (uint8_t)(cmd[1] >> 8);
    }
    return e;
}

static int
s9a_pmic_update(uint32_t type, uint32_t reg, uint8_t value, uint8_t mask)
{
    uint32_t cmd[4] = { (type & 0xf) << 8 | (reg & 0xff), 2u | (uint32_t)value << 8 | (uint32_t)mask << 16, 0, 0 };
    int e = s9a_request(cmd);
    return (e == 0 && (cmd[1] >> 24) != 0) ? 5 : e;
}

static bool
s9a_setup(void)
{
    uint32_t t = 0, table, count, ap_max;
    char ver[26], built[26];

    s9a_mbox = ml_io_map(S9A_MBOX_PA, 0x1000);
    s9a_sram = ml_io_map(S9A_SRAM_PA + S9A_SRAM_FIRST, S9A_SRAM_SIZE - S9A_SRAM_FIRST);
    if (!s9a_mbox || !s9a_sram) {
        printf("S9TOUCH acpm: mapping failed\n");
        return false;
    }
    if (s9_probe_read32(s9a_mbox + 0x28, &t) ||
        s9_probe_read32(s9a_sram + (S9A_INITDATA - S9A_SRAM_FIRST) + 0x08, &t) ||
        s9_probe_read32(s9a_sram + (S9A_INITDATA - S9A_SRAM_FIRST) + 0x6c, &t)) {
        printf("S9TOUCH acpm: mailbox or SRAM initdata read faulted\n");
        return false;
    }
    if (!s9a_text(S9A_INITDATA + 0x6c, 25)) {
        printf("S9TOUCH acpm: no firmware text at initdata +0x6c; words:\n");
        for (uint32_t o = 0; o < 0x80; o += 0x20) {
            printf("S9TOUCH acpm: +%x: %08x %08x %08x %08x %08x %08x %08x %08x\n", S9A_INITDATA + o,
                s9a_rd(S9A_INITDATA + o), s9a_rd(S9A_INITDATA + o + 4), s9a_rd(S9A_INITDATA + o + 8),
                s9a_rd(S9A_INITDATA + o + 12), s9a_rd(S9A_INITDATA + o + 16), s9a_rd(S9A_INITDATA + o + 20),
                s9a_rd(S9A_INITDATA + o + 24), s9a_rd(S9A_INITDATA + o + 28));
        }
        return false;
    }
    for (uint32_t i = 0; i < 25; i++) {
        ver[i] = (char)s9a_byte(S9A_INITDATA + 0x6c + i);
        built[i] = (char)s9a_byte(S9A_INITDATA + 0x6c + 25 + i);
    }
    ver[25] = 0;
    built[25] = 0;
    table = s9a_rd(S9A_INITDATA + 0x08);
    count = s9a_rd(S9A_INITDATA + 0x0c);
    ap_max = s9a_rd(S9A_INITDATA + 0x18);
    printf("S9TOUCH acpm: firmware \"%s\" built \"%s\": %u channels at +%x, %u the AP's\n", ver, built, count, table,
        ap_max);
    if (ap_max > count || count > 64 || ap_max > 16 || !s9a_ok(table, count * S9A_CH_SIZE)) {
        printf("S9TOUCH acpm: channel table not where it may be read\n");
        return false;
    }
    for (uint32_t i = 0; i < ap_max; i++) {
        uint32_t at = table + i * S9A_CH_SIZE, id = s9a_rd(at) & 0xff;
        printf("S9TOUCH acpm: ch %u owner %u type %u len %u elem %u poll %u in +%x out +%x\n", id, s9a_rd(at + 0x08),
            s9a_rd(at + 0x0c), s9a_rd(at + 0x34), s9a_rd(at + 0x38), s9a_rd(at + 0x44), s9a_rd(at + 0x18),
            s9a_rd(at + 0x30));
        if (id == S9A_CH) {
            s9a_c.in_rear = s9a_rd(at + 0x10);
            s9a_c.in_front = s9a_rd(at + 0x14);
            s9a_c.in_base = s9a_rd(at + 0x18);
            s9a_c.out_rear = s9a_rd(at + 0x28);
            s9a_c.out_front = s9a_rd(at + 0x2c);
            s9a_c.out_base = s9a_rd(at + 0x30);
            s9a_c.len = s9a_rd(at + 0x34);
            s9a_c.elem = s9a_rd(at + 0x38);
            s9a_c.usable = s9a_c.len > 1 && s9a_c.len <= 64 && s9a_c.elem >= 16 && s9a_c.elem <= 256 &&
                s9a_ok(s9a_c.in_rear, 4) && s9a_ok(s9a_c.in_front, 4) && s9a_ok(s9a_c.out_rear, 4) &&
                s9a_ok(s9a_c.out_front, 4) && s9a_ok(s9a_c.in_base, s9a_c.len * s9a_c.elem) &&
                s9a_ok(s9a_c.out_base, s9a_c.len * s9a_c.elem);
        }
    }
    if (!s9a_c.usable) {
        printf("S9TOUCH acpm: channel 2 missing, a single-slot buffer, or outside the SRAM: not usable\n");
        return false;
    }
    s9a_drain();
    printf("S9TOUCH acpm: channel 2 usable\n");
    return true;
}

static void
s9t_ms(unsigned n)
{
    while (n--) {
        delay(1000);
    }
}

static bool
s9t_ldo(uint8_t reg, bool on)
{
    uint8_t v = 0xee;
    if (s9a_pmic_update(1, reg, on ? 0xc0 : 0, 0xc0) != 0 || s9a_pmic_read(1, reg, &v) != 0) {
        printf("S9TOUCH ldo %02x %s: ACPM request failed\n", reg, on ? "on" : "off");
        return false;
    }
    if (((v & 0xc0) == 0xc0) != on) {
        printf("S9TOUCH ldo %02x %s: reads back %02x\n", reg, on ? "on" : "off", v);
        return false;
    }
    return true;
}

/* Android's order (sec_ts_power): AVDD off, 4 ms, DVDD off; DVDD on, 1 ms, AVDD on */
static bool
s9t_power_cycle(void)
{
    bool ok = s9t_ldo(S9T_LDO43, false);
    s9t_ms(4);
    ok = s9t_ldo(S9T_LDO35, false) && ok;
    s9t_ms(2000);
    ok = s9t_ldo(S9T_LDO35, true) && ok;
    s9t_ms(1);
    ok = s9t_ldo(S9T_LDO43, true) && ok;
    return ok;
}

/* ---- I2C: our own write (with STOP) and read (write cmd + STOP, then read + STOP), quiet on failure ---- */
static uint32_t
s9t_wait(vm_offset_t bus)
{
    for (unsigned us = 0; us < 20000; us++) {
        uint32_t st = a5touch_read(bus, 0x24);
        if (st & 0xf80u) {
            a5touch_write(bus, 0x24, st);
            return (st & 0xf00u) ? st : 0;
        }
        delay(1);
    }
    return 1;
}

static uint32_t
s9t_write(vm_offset_t bus, const uint8_t *d, unsigned len)
{
    uint32_t e;

    a5touch_write(bus, 0x24, a5touch_read(bus, 0x24));
    a5touch_write(bus, 0x70, S9_TS_ADDR << 10);
    a5touch_write(bus, 0x20, 0xf80u);
    a5touch_write(bus, 0x04, 3);
    a5touch_write(bus, 0x00, 0x9 | 0x80);
    a5touch_write(bus, 0x44, len | (1u << 17) | (1u << 31));
    for (unsigned i = 0; i < len; i++) {
        unsigned n = 0;
        while ((a5touch_read(bus, 0x30) & (1u << 7)) && n++ < 1000) {
            delay(1);
        }
        a5touch_write(bus, 0x34, d[i]);
    }
    e = s9t_wait(bus);
    a5touch_write(bus, 0x00, 0x9);
    if (e) {
        s9i2c_reset(bus);
    }
    return e;
}

static uint32_t s9t_last_err;

static uint32_t
s9t_read(vm_offset_t bus, uint8_t cmd, uint8_t *r, unsigned rlen)
{
    uint32_t e = 1;

    for (int attempt = 0; attempt < 2 && e != 0; attempt++) {
        e = s9t_write(bus, &cmd, 1);
        if (e) {
            continue;
        }
        a5touch_write(bus, 0x24, a5touch_read(bus, 0x24));
        a5touch_write(bus, 0x70, S9_TS_ADDR << 10);
        a5touch_write(bus, 0x20, 0xf80u);
        a5touch_write(bus, 0x04, 3);
        a5touch_write(bus, 0x00, 0x9 | 0x40);
        a5touch_write(bus, 0x44, (1u << 16) | (1u << 17) | rlen | (1u << 31));
        for (unsigned i = 0; i < rlen; i++) {
            unsigned n = 0;
            while ((a5touch_read(bus, 0x30) & (1u << 24)) && n++ < 20000) {
                delay(1);
            }
            if (a5touch_read(bus, 0x30) & (1u << 24)) {
                e = 2;
                break;
            }
            r[i] = (uint8_t)a5touch_read(bus, 0x38);
        }
        if (e == 0) {
            e = s9t_wait(bus);
        }
        a5touch_write(bus, 0x00, 0x9);
        if (e) {
            s9i2c_reset(bus);
        }
    }
    if (e) {
        s9t_last_err = e;
    }
    return e;
}

/* ---- events (layout from the S6SY761 driver of the other project) ---- */
static bool s9t_down[S9T_FINGERS];
static uint32_t s9t_lx[S9T_FINGERS], s9t_ly[S9T_FINGERS];
static uint32_t s9t_res_x = 4096, s9t_res_y = 4096, s9t_out_w = 1440, s9t_out_h = 2960;
static int s9t_mode;
static unsigned s9t_log_left = 60;
static uint64_t s9t_events, s9t_downs;

static void
s9t_all_up(void)
{
    for (int f = 0; f < S9T_FINGERS; f++) {
        if (s9t_down[f]) {
            s9t_down[f] = false;
            if (s9t_mode >= 2) {
                sweet_hid_touch(f, 0, (int)s9t_lx[f], (int)s9t_ly[f]);
            }
        }
    }
}

static void
s9t_event(vm_offset_t i2c, const uint8_t *e)
{
    uint32_t kind = e[0] & 3;

    if (s9t_log_left > 0) {
        s9t_log_left--;
        printf("S9TOUCH ev %02x %02x %02x %02x %02x %02x %02x %02x\n", e[0], e[1], e[2], e[3], e[4], e[5], e[6], e[7]);
    }
    if (kind == 0) {
        uint32_t id = (e[0] >> 2) & 0xf, state = e[0] >> 6;
        uint32_t x = (uint32_t)e[1] << 4 | e[3] >> 4, y = (uint32_t)e[2] << 4 | (e[3] & 0xf);
        uint32_t ox, oy;

        if (id == 0 || id > S9T_FINGERS || state == 0) {
            return;
        }
        id--;
        ox = x >= s9t_res_x - 1 ? s9t_out_w - 1 : x * (s9t_out_w - 1) / (s9t_res_x - 1);
        oy = y >= s9t_res_y - 1 ? s9t_out_h - 1 : y * (s9t_out_h - 1) / (s9t_res_y - 1);
        s9t_events++;
        if (state == 3) {
            if (s9t_down[id]) {
                s9t_down[id] = false;
                if (s9t_mode >= 2) {
                    sweet_hid_touch((int)id, 0, (int)s9t_lx[id], (int)s9t_ly[id]);
                }
            }
        } else {
            if (!s9t_down[id]) {
                s9t_down[id] = true;
                s9t_downs++;
            }
            s9t_lx[id] = ox;
            s9t_ly[id] = oy;
            if (s9t_mode >= 2) {
                sweet_hid_touch((int)id, 1, (int)ox, (int)oy);
            }
        }
    } else if (kind == 1) {
        uint32_t type = (e[0] >> 2) & 0xf, sid = e[1];
        uint8_t c;

        if ((type == 2 || type == 7) && sid == 0 && e[2] == 0x20) {
            printf("S9TOUCH chip restarted itself: sense on again\n");
            s9t_all_up();
            c = 0x10;
            (void)s9t_write(i2c, &c, 1);
        } else if (type == 1 && sid == 1) {
            printf("S9TOUCH chip event queue was full: cleared\n");
            s9t_all_up();
            c = 0x62;
            (void)s9t_write(i2c, &c, 1);
        }
    }
}

/* one event, then the rest it says are waiting; false if nothing */
static bool
s9t_poll(vm_offset_t i2c)
{
    uint8_t one[8], rest[8 * 31];
    uint32_t left, e;

    e = s9t_read(i2c, 0x60, one, 8);
    if (e != 0) {
        return false;
    }
    if (one[0] == 0) {
        return false;
    }
    s9t_event(i2c, one);
    left = one[7] & 0x3f;
    if (left == 0) {
        return true;
    }
    if (left > 31) {
        uint8_t c = 0x62;
        s9t_all_up();
        (void)s9t_write(i2c, &c, 1);
        return true;
    }
    if (s9t_read(i2c, 0x61, rest, left * 8) != 0) {
        return true;
    }
    for (uint32_t i = 0; i < left; i++) {
        s9t_event(i2c, rest + i * 8);
    }
    return true;
}

static bool
s9t_probe(vm_offset_t i2c, uint8_t *st, unsigned tries, unsigned gap_ms)
{
    for (unsigned t = 0; t < tries; t++) {
        if (s9t_read(i2c, 0x55, st, 1) == 0) {
            return true;
        }
        s9t_ms(gap_ms);
    }
    return false;
}

static void
s9t_thread(void *arg, __unused wait_result_t wr_)
{
    vm_offset_t i2c, usi, pin, aon;
    uint32_t u0 = 0, con, pud, bad = 0;
    uint8_t a[16], c;
    bool acpm_ok, ok;

    s9t_mode = (int)(intptr_t)arg;
    printf("S9TOUCH 1: start, mode %d\n", s9t_mode);
    i2c = ml_io_map(S9_I2C_PA, 0x1000);
    usi = ml_io_map(0x10411000, 0x1000);
    pin = ml_io_map(0x10430000, 0x1000);
    aon = ml_io_map(0x14050000, 0x1000);
    if (!i2c || !usi || !pin || !aon) {
        printf("S9TOUCH 1: mapping failed\n");
        goto out;
    }

    printf("S9TOUCH 2: ACPM init\n");
    acpm_ok = s9a_setup();
    if (acpm_ok) {
        uint8_t l35 = 0xee, l43 = 0xee;
        printf("S9TOUCH 3: rails\n");
        if (s9a_pmic_read(1, S9T_LDO35, &l35) != 0 || s9a_pmic_read(1, S9T_LDO43, &l43) != 0) {
            printf("S9TOUCH 3: PMIC read failed (ACPM request error)\n");
            acpm_ok = false;
        } else {
            printf("S9TOUCH 3: LDO35 %02x LDO43 %02x (on = bits 7:6 set)\n", l35, l43);
            if ((l35 & 0xc0) != 0xc0 || (l43 & 0xc0) != 0xc0) {
                printf("S9TOUCH 3: a rail is off: switching on\n");
                ok = s9t_ldo(S9T_LDO35, true);
                s9t_ms(1);
                ok = s9t_ldo(S9T_LDO43, true) && ok;
                printf("S9TOUCH 3: rails on %s\n", ok ? "ok" : "FAILED");
                s9t_ms(100);
            }
        }
    } else {
        printf("S9TOUCH 3: no ACPM: rails untouched, trying the bus anyway\n");
    }

    printf("S9TOUCH 4: USI word, pins, I2C reset\n");
    if (s9_probe_read32(usi + 0x1c, &u0)) {
        printf("S9TOUCH 4: usi +1c read faulted\n");
        goto out;
    }
    a5touch_write(usi, 0x1c, 4);
    con = a5touch_read(pin, 0x20);
    pud = a5touch_read(pin, 0x28);
    a5touch_write(pin, 0x20, (con & ~0x00ff0000u) | 0x00220000u);
    a5touch_write(pin, 0x28, (pud & ~0x00000f00u) | 0x00000f00u);
    printf("S9TOUCH 4: usi+1c %08x -> %08x, gpp1 CON %08x PUD %08x DAT %08x\n", u0, a5touch_read(usi, 0x1c),
        a5touch_read(pin, 0x20), a5touch_read(pin, 0x28), a5touch_read(pin, 0x24));
    s9i2c_reset(i2c);

    printf("S9TOUCH 5: ask the chip at 0x%x\n", (unsigned)S9_TS_ADDR);
    ok = s9t_probe(i2c, a, 30, 100);
    for (unsigned cycle = 1; !ok && acpm_ok && cycle <= 2; cycle++) {
        printf("S9TOUCH 5: no answer (err %x, DAT %08x): rails off/on, cycle %u of 2\n", s9t_last_err,
            a5touch_read(pin, 0x24), cycle);
        if (!s9t_power_cycle()) {
            break;
        }
        s9t_ms(100);
        ok = s9t_probe(i2c, a, 120, 100);
    }
    if (!ok) {
        printf("S9TOUCH 5: NO ANSWER (err %x, DAT %08x): bus or rails or address\n", s9t_last_err,
            a5touch_read(pin, 0x24));
        goto out;
    }
    printf("S9TOUCH 5: CHIP ANSWERS, boot status %02x (%s)\n", a[0],
        a[0] == 0x20 ? "firmware runs" : a[0] == 0x10 ? "in boot loader" : "unknown");
    if (a[0] != 0x20) {
        goto out;
    }

    printf("S9TOUCH 6: chip init\n");
    if (s9t_read(i2c, 0x52, a, 3) == 0) {
        printf("S9TOUCH 6: id %02x %02x %02x\n", a[0], a[1], a[2]);
    }
    if (s9t_read(i2c, 0x21, a, 1) == 0) {
        printf("S9TOUCH 6: firmware check %02x (%s)\n", a[0], (a[0] & 0x80) ? "good" : "BAD");
    }
    if (s9t_read(i2c, 0x23, a, 11) == 0) {
        uint32_t x = (uint32_t)a[0] << 8 | a[1], y = (uint32_t)a[2] << 8 | a[3];
        printf("S9TOUCH 6: panel %u x %u, %u TX x %u RX\n", x, y, a[8], a[9]);
        if (x > 1 && y > 1) {
            s9t_res_x = x;
            s9t_res_y = y;
        }
    }
    {
        uint32_t w = 0, h = 0;
        (void)PE_parse_boot_argn("s9touch_w", &w, sizeof(w));
        (void)PE_parse_boot_argn("s9touch_h", &h, sizeof(h));
        if (w > 1 && h > 1) {
            s9t_out_w = w;
            s9t_out_h = h;
        }
    }
    c = 0x10;
    if (s9t_write(i2c, &c, 1) != 0) {
        printf("S9TOUCH 6: sense on FAILED (err %x)\n", s9t_last_err);
        goto out;
    }
    s9t_ms(10);
    c = 0x62;
    (void)s9t_write(i2c, &c, 1);

    printf("S9TOUCH 7: polling, chip grid %u x %u, output range %u x %u, %s\n", s9t_res_x, s9t_res_y, s9t_out_w,
        s9t_out_h, s9t_mode >= 2 ? "feeding HID" : "log only");
    for (unsigned tick = 1;; tick++) {
        bool irq = (a5touch_read(aon, 0x24) & 1u) == 0;
        bool got = false;
        if (irq) {
            for (int rounds = 0; rounds < 4; rounds++) {
                if (!s9t_poll(i2c)) {
                    break;
                }
                got = true;
            }
        } else if ((tick & 3) == 0) {
            got = s9t_poll(i2c);
        }
        (void)got;
        if (s9t_last_err != 0) {
            bad++;
            s9t_last_err = 0;
        }
        if (tick % 15000 == 0) {
            printf("S9TOUCH 7: a minute: %u events, %u downs, %u failed transfers\n", (unsigned)s9t_events,
                (unsigned)s9t_downs, bad);
        }
        if (bad > 3000) {
            printf("S9TOUCH 7: too many failed transfers: giving up\n");
            s9t_all_up();
            break;
        }
        s9t_ms(4);
    }
out:
    printf("S9TOUCH: thread ends\n");
    thread_terminate(current_thread());
}

static void
s9t_start(void)
{
    int mode = 0;
    thread_t thread;
    (void)PE_parse_boot_argn("s9touch", &mode, sizeof(mode));
    if (mode <= 0) {
        return;
    }
    if (kernel_thread_start(s9t_thread, (void *)(intptr_t)mode, &thread) == KERN_SUCCESS) {
        thread_deallocate(thread);
    } else {
        printf("S9TOUCH: thread start failed\n");
    }
}
'''

s = s.replace(end_anchor, block + end_anchor)
s = s.replace(call_anchor, "#if defined(STAR2LTE)\n\ts9survey_start();\n\ts9t_start();\n#endif\n")
f.write_text(s)

diff = subprocess.run(["git", "-C", str(tree), "diff"], capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff")
out.write_text(diff)
print("wrote", out)
