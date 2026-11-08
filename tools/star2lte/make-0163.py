#!/usr/bin/env python3
# make-0163.py TREE OUT.patch
# Boot-arg sweettap=x,y,secs : inject a tap through sweet_hid_touch's SweetHIDTouch.
#   x,y   = PANEL pixels (1440x2960 native), secs = delay before the first tap and
#           between taps. 30 taps at most. Each tap = down, 150 ms, up. Logs
#           "SWEET HID: sweettap n at px,py (hook hx,hy)".
# Hook grid (A5XELTE branch in SweetHID.cpp): 1080x1920, no offsets; else 1080x2400.
# Needs a clean tree (git -C TREE commit -am 0162 first). Leaves the edit uncommitted.
# UNTESTED: not compiled, not run on the phone.
import re, subprocess, sys, pathlib

tree = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()

if subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                  capture_output=True, text=True, check=True).stdout.strip():
    sys.exit("tree not clean: git -C %s commit -am '<previous number>'" % tree)

f = tree / "iokit/Kernel/arm/hid/SweetHID.cpp"
s = f.read_text()
if "sweettap" in s:
    sys.exit("sweettap already present")


def tabify(t):
    return re.sub(r"(?m)^((?:    )+)", lambda m: "\t" * (len(m.group(1)) // 4), t)


FUNC = tabify(r'''/*
 * sweettap=x,y,secs: injected tap for bring-up. x,y in panel pixels (1440x2960).
 */
static IOTimerEventSource *gSweetTapTimer;
static int gSweetTapX, gSweetTapY, gSweetTapSecs, gSweetTapN, gSweetTapStage;

static void
sweetTapFired(OSObject *owner, IOTimerEventSource *sender)
{
    (void)owner;
    int hx = gSweetTapX * 1080 / 1440;
#if defined(ARM64_BOARD_CONFIG_A5XELTE)
    int hy = gSweetTapY * 1920 / 2960;
#else
    int hy = gSweetTapY * 2400 / 2960;
#endif
    if (!gSweetTouch) {
        return;
    }
    if (gSweetTapStage == 0) {
        IOLog("SWEET HID: sweettap %d at %d,%d (hook %d,%d)\n", gSweetTapN + 1,
           gSweetTapX, gSweetTapY, hx, hy);
        gSweetTouch->touch(0, true, hx, hy);
        gSweetTapStage = 1;
        sender->setTimeoutMS(150);
    } else {
        gSweetTouch->touch(0, false, hx, hy);
        gSweetTapStage = 0;
        if (++gSweetTapN < 30) {
            sender->setTimeoutMS((UInt32)gSweetTapSecs * 1000);
        }
    }
}

''')

START = tabify(r'''    {
        char tapArg[48];
        if (PE_parse_boot_arg_str("sweettap", tapArg, sizeof(tapArg))) {
            int v[3] = { 0, 0, 0 }, k = 0;
            for (const char *p = tapArg; *p && k < 3; p++) {
                if (*p >= '0' && *p <= '9') {
                    v[k] = v[k] * 10 + (*p - '0');
                } else if (*p == ',') {
                    k++;
                }
            }
            if (k >= 2 && v[2] > 0) {
                gSweetTapX = v[0];
                gSweetTapY = v[1];
                gSweetTapSecs = v[2];
                gSweetTapTimer = IOTimerEventSource::timerEventSource(this, &sweetTapFired);
                if (gSweetTapTimer && _hidWorkLoop->addEventSource(gSweetTapTimer) == kIOReturnSuccess) {
                    gSweetTapTimer->setTimeoutMS((UInt32)v[2] * 1000);
                    IOLog("SWEET HID: sweettap armed %d,%d every %d s\n", v[0], v[1], v[2]);
                }
            } else {
                IOLog("SWEET HID: sweettap needs x,y,secs\n");
            }
        }
    }
''')

# 1. static timer + callback, just before SweetHIDTouch::start
pat1 = re.compile(r"\n(bool\nSweetHIDTouch::start\(IOService \*provider\)\n)")
if len(pat1.findall(s)) != 1:
    sys.exit("expected exactly one SweetHIDTouch::start, found %d" % len(pat1.findall(s)))
s = pat1.sub(lambda m: "\n" + FUNC + m.group(1), s)

# 2. arm the timer in start(), just before the "touch registered" log
pat2 = re.compile(r'\n([ \t]*)(IOLog\("SWEET HID: touch registered\\n"\);)')
if len(pat2.findall(s)) != 1:
    sys.exit("expected exactly one 'touch registered' log, found %d" % len(pat2.findall(s)))
s = pat2.sub(lambda m: "\n" + START + m.group(1) + m.group(2), s)

f.write_text(s)

diff = subprocess.run(["git", "-C", str(tree), "diff"], capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff")
out.write_text(diff)
print("wrote", out)
