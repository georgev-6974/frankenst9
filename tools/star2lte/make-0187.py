#!/usr/bin/env python3
# make-0187.py TREE OUT.patch
# Bixby (key 3): tap (<600 ms) = Home as before; hold (>=600 ms) = ringer toggle.
# Ringer event = keyboardEvent page 0x0B usage 0x2E (GUESS, iOS 6 era wiki).
# Boot arg s9ringer: 0 = old behaviour (Bixby = Home on press), 1 = hold posts
# state as down flag (default), 2 = hold posts a down/up pulse per toggle.
# Log lines: "SWEET HID: ringer ...". UNTESTED: not built, not run.
import subprocess, sys, pathlib

tree = pathlib.Path(sys.argv[1]).resolve()
out = pathlib.Path(sys.argv[2]).resolve()

if subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                  capture_output=True, text=True, check=True).stdout.strip():
    sys.exit("tree not clean: git -C %s commit -am '<previous number>'" % tree)

f = tree / "iokit/Kernel/arm/hid/SweetHID.cpp"
s = f.read_text()
if "sweet_hid_key_plain" in s:
    sys.exit("0187 already applied")

def rep(s, old, new):
    if s.count(old) != 1:
        sys.exit("expected one match, found %d for:\n%s" % (s.count(old), old))
    return s.replace(old, new)

s = rep(s, "static SweetHIDButtons *gSweetButtons;\n",
        "static SweetHIDButtons *gSweetButtons;\nstatic UInt32 gSweetKeyPage = kHIDPage_Consumer;\n")

s = rep(s, "IOHIDEvent::keyboardEvent(mach_absolute_time(), kHIDPage_Consumer, usage, down)",
        "IOHIDEvent::keyboardEvent(mach_absolute_time(), gSweetKeyPage, usage, down)")

s = rep(s, 'extern "C" void\nsweet_hid_key(int key, int down)\n{',
        'static void\nsweet_hid_key_plain(int key, int down)\n{')

new_fn = r'''extern "C" void absolutetime_to_nanoseconds(uint64_t, uint64_t *);

extern "C" void
sweet_hid_key(int key, int down)
{
	static uint64_t t_down;
	static int have_down;
	static int silent;
	static int mode = -1;

	if (key != 3) {
		sweet_hid_key_plain(key, down);
		return;
	}
	if (mode < 0) {
		int v = 1;
		if (!PE_parse_boot_argn("s9ringer", &v, sizeof(v))) {
			v = 1;
		}
		mode = v;
	}
	if (mode == 0) {
		sweet_hid_key_plain(key, down);
		return;
	}
	if (down) {
		t_down = mach_absolute_time();
		have_down = 1;
		return;
	}
	if (!have_down) {
		return;
	}
	have_down = 0;

	uint64_t ns = 0;
	absolutetime_to_nanoseconds(mach_absolute_time() - t_down, &ns);
	if (ns < 600000000ull) {
		sweet_hid_key_plain(3, 1);
		sweet_hid_key_plain(3, 0);
		return;
	}

	silent = !silent;
	IOLog("SWEET HID: ringer toggle, silent=%d mode=%d (page 0x0B usage 0x2E)\n", silent, mode);
	if (gSweetButtons) {
		gSweetKeyPage = 0x0B;
		if (mode == 2) {
			gSweetButtons->key(0x2E, true);
			gSweetButtons->key(0x2E, false);
		} else {
			gSweetButtons->key(0x2E, silent != 0);
		}
		gSweetKeyPage = kHIDPage_Consumer;
	}
}

'''
s = rep(s, 'extern "C" void\nsweet_hid_touch(int finger',
        new_fn + 'extern "C" void\nsweet_hid_touch(int finger')

f.write_text(s)
diff = subprocess.run(["git", "-C", str(tree), "diff"], capture_output=True, text=True, check=True).stdout
if not diff:
    sys.exit("empty diff")
out.write_text(diff)
print("wrote", out)
