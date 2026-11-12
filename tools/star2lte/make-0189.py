#!/usr/bin/env python3
# make-0189.py TREE OUT.patch
# Bixby single press toggles ringer (no Home, no hold). On top of 0188.
# s9ringer=3: press posts state as value on page s9rpage / usage s9ruse.
# s9ringer=4: press pulses ALL candidates (0B/2E, 0B/2F, 0C/E2) down+up.
# UNTESTED.
import subprocess, sys, pathlib

tree = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()

if subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                  capture_output=True, text=True, check=True).stdout.strip():
    sys.exit("tree not clean: git -C %s commit -am '<previous number>'" % tree)

f = tree / "iokit/Kernel/arm/hid/SweetHID.cpp"
s = f.read_text()
if "ringer press silent" in s:
    sys.exit("0189 already applied")

old = "\tif (down) {\n\t\tt_down = mach_absolute_time();"
if s.count(old) != 1:
    sys.exit("anchor count %d" % s.count(old))

new = r'''	if (mode >= 3) {
		static const UInt32 cand[3][2] = { {0x0B, 0x2E}, {0x0B, 0x2F}, {0x0C, 0xE2} };
		if (!down) {
			return;
		}
		silent = !silent;
		IOLog("SWEET HID: ringer press silent=%d mode=%d\n", silent, mode);
		if (gSweetButtons) {
			if (mode == 4) {
				for (int i = 0; i < 3; i++) {
					gSweetKeyPage = cand[i][0];
					gSweetButtons->key(cand[i][1], true);
					gSweetButtons->key(cand[i][1], false);
				}
			} else {
				gSweetKeyPage = (UInt32)rpage;
				gSweetButtons->key((UInt32)ruse, silent != 0);
			}
			gSweetKeyPage = kHIDPage_Consumer;
		}
		return;
	}
'''
s = s.replace(old, new + old)
f.write_text(s)
diff = subprocess.run(["git", "-C", str(tree), "diff"], capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff")
out.write_text(diff)
print("wrote", out)
