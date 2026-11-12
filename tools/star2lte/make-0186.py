#!/usr/bin/env python3
"""0186: battery fast poll. SweetBattery timer 1 s on A5XELTE (30 s elsewhere), publish only on change
(or every 30th call); s9bat_read reads the charger bytes every call and the gauge every 30th call or when
the charger bytes change. Usage: make-0186.py TREE OUT.patch (TREE = clean WORK3/xnu)."""
import os, subprocess, sys

tree, out = sys.argv[1], sys.argv[2]
if subprocess.run(["git", "-C", tree, "status", "--porcelain", "--untracked-files=no"],
                  capture_output=True, text=True).stdout.strip():
    sys.exit("tree not clean: git -C %s commit -am '0185' first" % tree)

def edit(path, pairs):
    s = open(path).read()
    for old, new in pairs:
        if s.count(old) != 1:
            sys.exit("anchor count %d in %s:\n%s" % (s.count(old), path, old[:120]))
        s = s.replace(old, new)
    open(path, "w").write(s)

touch = os.path.join(tree, "bsd/dev/a5xelte_touch.c")
bat = None
for d, _, fs in os.walk(os.path.join(tree, "iokit")):
    if "SweetBattery.cpp" in fs:
        bat = os.path.join(d, "SweetBattery.cpp")
if not bat or not os.path.exists(touch):
    sys.exit("files not found")

edit(touch, [
("    uint32_t status = 0, soc = 0, vcell = 0, cur = 0;\n",
 "    static uint32_t status, soc, vcell, cur;      /* gauge values, refreshed every 30th call or on a charger change */\n"
 "    static uint8_t last_ok = 0xff, last_dtls = 0xff;\n"
 "    static unsigned since;\n"
 "    static bool have;\n"),
("""    if (s9b_rd16(0x00, &status) || s9b_rd16(0x06, &soc) || s9b_rd16(0x09, &vcell) || s9b_rd16(0x0a, &cur)) {
        if (calls < 40) {
            printf("S9BAT svc: gauge read failed\\n");
        }
        calls++;
        return -1;
    }
    chg_ok = !s9b_read(S9BAT_CHARGER, 0xb2, &ok, 1) && !s9b_read(S9BAT_CHARGER, 0xb4, &dtls, 1);
    if (!chg_ok) {
        ok = 0;
        dtls = 0x0f;
    }
""",
"""    chg_ok = !s9b_read(S9BAT_CHARGER, 0xb2, &ok, 1) && !s9b_read(S9BAT_CHARGER, 0xb4, &dtls, 1);
    if (!chg_ok) {
        ok = 0;
        dtls = 0x0f;
    }
    if (!have || since >= 30 || ok != last_ok || dtls != last_dtls) {
        if (s9b_rd16(0x00, &status) || s9b_rd16(0x06, &soc) || s9b_rd16(0x09, &vcell) || s9b_rd16(0x0a, &cur)) {
            if (calls < 40) {
                printf("S9BAT svc: gauge read failed\\n");
            }
            calls++;
            return -1;
        }
        have = true;
        since = 0;
    } else {
        since++;
    }
    last_ok = ok;
    last_dtls = dtls;
"""),
("""    printf("S9BAT svc: bus up, input clock %u MHz\\n", ipclk);
    return 0;
""",
"""    printf("S9BAT svc: bus up, input clock %u MHz\\n", ipclk);
    printf("S9BAT svc: charger 1 s, gauge 30 s\\n");
    return 0;
"""),
])

edit(bat, [
("#define SWEET_BAT_MAH 3000u\n",
 "#define SWEET_BAT_MAH 3000u\n#if defined(ARM64_BOARD_CONFIG_A5XELTE)\n#define SWEET_BAT_POLL_MS 1000\n"
 "#else\n#define SWEET_BAT_POLL_MS 30000\n#endif\n"),
("""	if (fReal && dreamlte_battery_read(&pct, &s8mv, &s8ma, &ext, &chg, &full) == 0) {
		publish(full ? 100 : pct, s8mv, s8ma, ext != 0, ext != 0, chg != 0, full != 0, true, true);
	} else {
		publish(100, 4200, 0, true, true, false, true, false, false);
	}
#else
""",
"""	static unsigned last_pct = 999, since_pub;
	static int last_ext = -1, last_chg = -1, last_full = -1;
	if (fReal && dreamlte_battery_read(&pct, &s8mv, &s8ma, &ext, &chg, &full) == 0) {
		/* polled every second: publish only on a visible change, else every 30th call */
		if (pct != last_pct || ext != last_ext || chg != last_chg || full != last_full || ++since_pub >= 30) {
			publish(full ? 100 : pct, s8mv, s8ma, ext != 0, ext != 0, chg != 0, full != 0, true, true);
			last_pct = pct;
			last_ext = ext;
			last_chg = chg;
			last_full = full;
			since_pub = 0;
		}
	} else if (last_pct != 1000) {
		publish(100, 4200, 0, true, true, false, true, false, false);
		last_pct = 1000;
	}
#else
"""),
("\t\tsender->setTimeoutMS(30000);\n", "\t\tsender->setTimeoutMS(SWEET_BAT_POLL_MS);\n"),
("\t\t\tfTimer->setTimeoutMS(30000);\n", "\t\t\tfTimer->setTimeoutMS(SWEET_BAT_POLL_MS);\n"),
])

d = subprocess.run(["git", "-C", tree, "diff"], capture_output=True, text=True).stdout
open(out, "w").write(d)
print("wrote %s (%d lines)" % (out, d.count("\n")))
