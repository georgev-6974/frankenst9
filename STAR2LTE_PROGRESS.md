# frankenstnine - Galaxy S9+ (SM-G965F, star2lte, Exynos 9810) iOS 16.7 port - PROGRESS

Last rewrite: session 6, 2026-11-10; updated session 7 (same day: code of 0182 read, 0183 written) (merged from the old LATEST 2-6, the 2026-11-05..08 handoffs and HANDOFF session 6). The old file was organized by session and contradicted itself; this one is organized by topic and holds only the final version of each fact. Superseded claims are kept ONLY where they warn against a wrong turn ("was wrong: ...").

Project name: **frankenstnine** (display name only; dirs, patches, code keep `star2lte`). GitHub: user `georgev-6974`, repo `frankenst9` (was `s9plus-ios`). Local folder: `~/Downloads/ios-galaxy-s9plus`. Fork of the S8 (dreamlte) port.

**Labels used everywhere:** **measured** = log/photo/file the user pasted; **user-reported** = the user said so, no log; **claim** = from another project/doc, not checked on our phone; **guess**; **untested**. Build / kernel marker / screen / iOS runtime are separate claims (AGENTS.md).

---

## 1. Goal and where we are

**Goal:** a usable iOS 16.7 on the S9+: touch, keys, clock, battery level, speed; later a real GPU (Mali, huge, no Metal/AGX path: hardware survey first, unrealistic for now).
**Immediate goal:** real battery (and clock) data so iOS can show a charge level. Step one = a working I2C read of the MAX77705 fuel gauge/charger on hsi2c_40. Later: Spotlight loop, iPad-looking apps, Bixby -> ringer.

**State (2026-11-10):**
- iOS 16.7.16 reaches the home screen on 8 cores (kernel 0162+), with root `disabled.plist` applied.
- **Touch works** (S6SY761 over hsi2c10, events reach SpringBoard, used ~20 min, 0 failed transfers over 7+ min). Keys work with `a5keys=1`.
- Slow (CPU-only rendering, expected). Date fixed by boot-arg `s8rtc`.
- Battery I2C: 0182 booted and its scan is **meaningless** (see section 2).

| patch | what | status |
| --- | --- | --- |
| 0038 edit | AKS log limited to first 600 lines, then 1 in 500 (`tools/star2lte/aks-ratelimit.py`) | built+booted; phone "a little" faster |
| 0179 | touch default 1080x1920; touch thread sleeps 4 ms (`assert_wait_deadline`) instead of spinning | built; user-reported (session 7): taps accurate without range boot args |
| 0180 | survey level 5 also dumps battery bus (read-only) | booted, output in section 2 |
| 0181 | survey level 5 also reads S2MPS18 RTC via ACPM type 2 (read-only) | booted, output in section 2 |
| 0182 | survey level 5 also runs `s9bat_test()`: gpm14/15 -> func 2, hsi2c_40 reset, scan ACKs 0x08..0x77, read regs of 0x36/0x66 | built, booted; **WROTE pin CON/PUD of gpm14/15** (guessed bank offsets); results unusable |
| 0183 | `make-0183.py`: CMU_CMGP gates + Q-channel + USI word 0x14212030=4 (all read with nofault probe first), input clock from CMU divider, sanity check (idle FIFO_STAT RX-empty), control scan of impossible addresses, real scan, reg reads of 0x25/0x36/0x66/0x69. **No pin writes.** `s9t_reset` uses `s9t_ipclk_mhz` (default 200, touch unchanged) | written session 7; generator tested on a mock + C compiled against stubs with -Wall -Wextra -Werror; not built in CI, not booted |

**Answered (session 7, user-reported):** taps are accurate without range boot args (0179 ok). iPad symptom: only in the Phone app (dialer digits smaller and centered) and Settings layout looked smaller, like a phone-sized layout on a bigger/odd screen (see section 8). Still unanswered: does the phone feel faster after 0038/0179.

---

## 2. Battery I2C work (current task)

### Hardware (from live.dts + 0180 dump)
- MAX77705 @0x66 on **hsi2c_40 (0x14360000)**; dt names `max77705-fuelgauge` and `max77705-charger`; irq gpa1-6. Pins gpm14-0 / gpm15-0 func 2.
- Pin block **0x14220000**, banks 0x20 apart (guess: gpm14 = +0x1c0, gpm15 = +0x1e0). Both read CON=0 (input), DAT=1, PUD=1, DRV=2 BEFORE the test.
- CMGP USI 0x14212000: +00=0, +04=4, +10=0, +14=4 (which one belongs to hsi2c_40 unknown).
- I2C40 regs 0x00..0xBF all 0; +0xC4 = 1 (held in reset, same state touch was in before 0178).
- Gauge address 0x36 and registers 0x06 (RepSOC) / 0x09 (VCell) are **guesses** from the Snapdragon S9 / max17042 layout.

### 0182 boot result (measured)
- `S9BAT: gpm14 00000002 00000000 gpm15 00000002 00000000` = CON, PUD read back AFTER our write (print order read from the code, session 7), i.e. exactly what we wrote. The registers took the write, which does not prove they are gpm14/15: before the write CON was 0 (input) and the reference says S-Boot leaves these pins on function 2, so the guessed offsets are probably another bank (**we may have set pin 0 of an unrelated bank to function 2**; 0183 writes no pins and dumps all banks).
- `S9BAT: scan done, 112 ACKs`: **every address 0x08..0x77 "ACKed" and read 00.** No real bus does that: the scan proves nothing. The 0x36/0x66 test results were not seen.
- Only two `S9BAT` lines exist besides the ACK lines (`s9pull -g S9BAT` matches=2): no register-read lines under that prefix.
- DAT=1 before the test makes "SDA stuck low" less likely (guess).
- Panic: none this session.

### Why the 0182 scan was meaningless (found by reading `s9bat_test`/`s9t_msg`, session 7; code read + measured symptoms)
- `s9t_msg` read path pops the RX FIFO whenever FIFO_STAT bit 24 (RX empty) is clear. With the block's clock gated every register reads 0, so bit 24 reads 0 = "not empty", the pop returns 00, `done == len` = success. That is exactly "112 ACKs, all read 00". The touch bus worked because its clock was already on.
- `s9bat_test` set up NO CMU gates / Q-channel. Its fallback "CMGP USI +00 = 4" never ran (pass 1 only runs with 0 ACKs) and had the wrong offset anyway (reference: mode word 0x14212030).
- Its only hardware writes: pin banks +0x1c0/+0x1e0 (CON pin0 = 2, PUD pin0 = 0) and the hsi2c_40 reset.
- `s9t_reset` hardcoded a 200 MHz input clock; the reference says this bus is 400 MHz (claim): timing was ~2x too fast. 0183 makes it a variable.
- The old idea "our PUD write removed a pull-up" is probably wrong (the reference also uses PUD 0).

### Facts from the reference driver (hakios.exynos_hsi2c.c; claim, not measured on our phone)
The reference runs on the real S9+ in a WoA port. Its battery bus is USI03 of CMGP; the touch bus is USI03 of PERIC0.
- **Before the first transfer (S-Boot does none of this):** force the bus's CMU clock gates on (write bits 20 and 21 = manual + on, for each gate), Q-channel register |= 3, USI mode word = 4 (I2C), the two pins to function 2 and PUD 0 (dt: pin-pud 0).
- **Reset:** USI_CON(0xC4)=0; clear INT_STAT; pulse CTL bit31 (SW_RST) ~10 us; set timing; CTL=MASTER(bit3); TRAILING=0xffffff; clear TIMEOUT bit31; CONF |= bit31 (auto).
- **Timing:** div = ipclk_MHz*1e6/(bus_hz*15); n = 9*ipclk_MHz/((div+1)*10), max 7. TIMING_FS3 bits 16-23 = div; TIMING_FS2 low byte = (0xFFFFFFFF>>n<<n)&0xff; TIMING_FS1 bits 16-23 = same mask with n-1. Input clock assumed 400 MHz / ((CMU divider&0xf)+1); ours unknown.
- **Message:** clear INT_STAT; FIFO_CTL(0x04) = 3 | trig<<4 | trig<<16 (trig = min(len,8)); CTL = MASTER | RXCHON(bit6) for read or TXCHON(bit7) for write; ADDR(0x70) = addr<<10; INT_EN(0x20) = DONE(bit7) | errors(0xf<<8); AUTO_CONF(0x44) = len | READ(bit16) | STOP(bit17), then |= RUN(bit31). Poll FIFO_STAT(0x30): TX_FULL bit7, TX_EMPTY bit8, RX_EMPTY bit24; FIFO TX 0x34, RX 0x38.
- **Success/failure:** INT_STAT(0x24) bits 8-11 set = abort / no ACK / no device / timeout, then reset the bus. A read succeeds only when all bytes came out of the RX FIFO; a write when DONE and TX_EMPTY. After a STOP wait for TRANS_STATUS(0x50) bit17 (busy) to clear. 1 s timeout.

### Battery-bus values from the reference (claim, hakios.max77705.c + hakios.exynos_hsi2c.h, pasted session 7; 0183 uses them)
- regs 0x14360000 (matches live.dts), USI mode word **0x14212030** (4 = I2C), CMU_CMGP **0x14200000** size 0x4000.
- Gates (bit 20 manual + bit 21 on): +0x2014, +0x20A8, +0x20AC, +0x2074. Q-channel +0x3050 (|= 3). Divider +0x1814, mux +0x1018 (log only; "seen on the phone: divider 0, 400 MHz branch"). +0x2018/+0x201C and Q +0x3008/+0x300C are the ADC's, not ours.
- Pins: the reference writes NONE ("the boot loader talks to the chip, they are set"). Input clock 400 MHz, bus 400 kHz.
- API: message returns 0 / INT_STAT error bits 0xf00 / 1 = own timeout; a failed message resets the bus; read_reg = write reg, repeated start, read.
- Code of `s9t_reset`/`s9t_msg`/`s9bat_test` (0182) was read in session 7 (section above). Optional cross-check, user has not run it: `grep -n -i -E '14200000|14212030|14220000|gpm14|gpm15' star2lte-facts/live.dts | cut -c1-150 | head -30`

### NEXT (in order)
1. `s9push 0183 battery-i2c` (make-0183.py in ~/Downloads; do not run s9install on it first, s9push moves it). Then `s9go out-0183 s9survey=5 a5fb_keep_on=1 s8rtc=(date +%s)`. Verify the stale-kernel trap first: `grep -a -c 'S9BAT: control' xnu/out-0183/kernel.development.a5xelte` >= 1. Then `s9pull -g S9BAT` (no `-v 'ACK at'` any more: ACK lines now matter).
2. Read the result: (a) "block is dead" = clocks/addresses wrong, compare the `cmu before/after` lines; (b) control addresses ACKed = test still broken; (c) a short ACK list (expect 0x25, 0x36, 0x66, 0x69 or some of them) with register values = success. The `pins +xxx` lines show which banks have CON low nibble 2 (the real gpm14/15) and whether S-Boot left them on function 2.
3. If 0x36/0x66 read real values: battery reader (fuel gauge regs from the real chip, not the max17042 guesses), then fake/real battery service for iOS.
4. Backlog: section 10. Optional: `s8rtc=(date +%s)` default in s9go.

### Clock (RTC)
- Boot-arg `s8rtc=(date +%s)` fixes the date (user-reported). Kernel side: patch 0124 PEGetUTCTimeOfDay, A5XELTE only. loader.c has no PMIC read for S9.
- **PMIC RTC (0181, measured):** ACPM type 2 regs read fine (bad 0), CTRL 02, CAP f0, but time = 2018-01-01 12:05:23 PM, identical in two reads 2 s apart: clock UNSET (the other project saw the same). **Decision: do not write the PMIC; use host time.**
- RTC node in dt: `samsung,exynos8-rtc` at 0x141E0000 (not used).

---

## 3. Standing user rules and workflow

The user does NOT know low-level stuff, is new to git/kernels, runs **fish on Arch Linux**.
- Give only what to run/paste; tiny copy-paste answers; one explanation sentence the first time a git/kernel term appears.
- fish: no heredocs (type `bash`, paste, `exit`, or give a file and `cat file >> target`), quote globs like `'*.c'`, no bash `&&` chains (use `; and`), `set VAR value`. A variable named `status` is a fish builtin: never use it. `ls` is an eza alias (no `-t`, use explicit names). Run `.sh` files as `bash path/file.sh`.
- **Ask for files with a ready-to-run `cat` / `find` / `grep` command, never "please attach X".** The user could not find `bsd/` in the root (tree is probably under WORK3, guess): use `find . -path '*WORK3*' -name NAME | head -1`. Ask for exact files/log lines, not typed hex.
- New files arrive in ~/Downloads. Install with `s9install`. Never `funcsave`; after editing a function file `source` it and check the `boot-args:` line of the build output (stale loaded function trap).
- **Confirm every USERDATA write first** (destructive). Run commands from the repo root. Long greps on `$L`: use `s9pull -g` (has a timeout) or `grep -m N`.
- The other project `~/Downloads/ios-s9plus-exynos` (HakiOS) is APSL/GPL: read for facts, write our own code.
- The assistant has no fish and no compiler: everything it writes is untested until CI and the phone. Keep short replies.
- AGENTS.md: no S8 address without a measurement; keep dumps, serials, Apple binaries out of git; never edit `shim/dreamlte`, `tools/dreamlte`, `DREAMLTE_PROGRESS.md`, `NOTES.md`.
- Record every new finding here right away.

### Patch workflow
1. Each `make-NNNN.py` needs a clean tree: `git -C WORK3/xnu commit -am "<previous number>"` first. WORK3/xnu is a detached HEAD; WORK3 = WORK2 + 0145-0148 and later, the tree to diff against (WORK2 alone is stale at 0142). **Never `git add WORK2/` or `WORK3/`** (huge).
2. `python3 tools/star2lte/make-NNNN.py WORK3/xnu (pwd)/xnu/patches/NNNN-name.patch`, `cat` it. Generators edit WORK3/xnu and write the git diff as the patch.
3. `git add ...; git commit -m ...; git push; sleep 2 && gh run watch` (CI kernel build ~9 min; artifact upload timeouts: `gh run rerun RUNID --failed`). Or use `s9push NNNN name` (below).
4. **NEVER add lines to `xnu/patches/0065`** (build 0138 broke the context of 0112+). New edits go in a NEW patch generated with git (`git apply --check` against a clone of xnu-8796.141.3).
5. Boot test: phone in TWRP, `s9go out-NNNN ...`, then force TWRP (POWER+VOL DOWN, then POWER+BIXBY+VOL UP) after the Apple logo (~2 min wait), `s9pull`, `s9pull -g PATTERN`. A panic needs an upright sharp photo.
6. **Stale-kernel trap (hit three times):** `s9go` reuses `xnu/out-NNNN` unless `fresh`. Verify before flashing: `grep -a -c '<marker string>' xnu/out-NNNN/kernel.development.a5xelte` must be >= 1. Plain `s9.sh build` picks the newest file in `xnu/out` (once even a 30-byte `.lse.txt`; fixed with a Mach-O magic check), not `xnu/out-NNNN`.
7. CI build errors: `gh run view <id> --log-failed | grep -a -E '\.(c|cpp|h|m):[0-9]+:[0-9]+: (fatal )?error' | cut -c1-300`.
8. Commit labels in WORK3 can be wrong (two commits named "0162", one is really 0163): harmless, CI only looks at patch files. If 0179-0181 are not committed in WORK3, `s9push` commits them as "before NNNN".

### Fish helpers (all untested by the assistant)
- **s9go**: `s9go out-NNNN [fresh] [N] [boot-args...]`. Default 8 cpus and `a5keys=1` (explicit `a5keys=` in the extras wins). A bare number = cpu count, `fresh` = re-download CI artifact. Waits for the newest CI run, downloads into `xnu/out-NNNN` (reuses it if it holds a kernel), builds with s9.sh, flashes after `yes`. On CI failure prints `s9why RUNID`. Boot args live inside it (section 9).
- **s9pull**: `s9pull [-g PAT]... [-v EXCL]... [-n N [-t]] [-w W] [-c] [-k]`. Without `-g` it pulls and sets `$N`/`$L` (log file). With `-g` the pull output is hidden and ALL matches are shown (cut to 130 chars); `-n N` limits, `-t` takes the last N, `-c` counts, `-k` reuses current `$L`. Repeat `-g`/`-v` for several patterns; loose words are NOT patterns. The `-t` bug (negative index) was fixed and confirmed; the "show all by default" version was delivered but the user has not reported installing it.
- **s9install**: moves `*.fish` (must contain a `function` line) to `~/.config/fish/functions/` and sources them (itself last), `make-NNNN.py` to `~/Downloads/ios-galaxy-s9plus/tools/star2lte/`, `STAR2LTE_PROGRESS.md` to the project root. Strips browser " (1)" suffixes, newest wins, backs up replaced files to `/tmp/s9install-bak`, `-n` = dry run, `S9PROJ` overrides the project path. Delivered, not yet reported run. Install the first time with `mv` plus `source`.
- **s9push** (`s9push NNNN name`): moves make-NNNN.py, commits WORK3, builds the patch, commits, pushes, watches CI. Edited by the user, not seen by the assistant. **Open risk:** if `s9push` itself moves `make-NNNN.py` out of ~/Downloads, `s9install` having moved it first makes `s9push` complain; fix one of them after `cat ~/.config/fish/functions/s9push.fish`.
- **s9why** (user installed, untested): CI failure summary.
- **s9root** (`s9root [IMG]`): writes the root image to sda25 via `adb exec-in` + read-back verify. Pipe test fixed (exec-in dd to /tmp/pipe.bin + `sync; sleep 3`, hash matched). Writes USERDATA: needs explicit yes.
- **s9delta** (`s9delta [IMG]`, `s9delta -p`): compares sda25 vs image in 64 MiB chunks (hash on phone), rewrites only differing chunks after "yes". Workflow: `s9delta -p` BEFORE editing the image, edit, then `s9delta`. Only a valid verifier right after a write and BEFORE the first boot: after a boot, 28/256 chunks differ (0 11 107 186-218 248-255 = iOS rw changes with rootrw=1); do NOT write them back (would roll back HFS+ metadata).
- **s9.sh** (`bash tools/star2lte/s9.sh`): `build [KERNEL]` (make-boot.sh; 57,671,680-byte BOOT limit; writes `out.img`; prints `BUILD OK`), `flash [IMG]` (TWRP only, asks `yes`, writes sda10, reads back SHA-256, refuses without `~/s9-backup/boot-sda10.img`), `pull [NAME]` (decodes LDRLOG + SWEETLOG into `logs/`, NAME defaults to next free vN, last known log v36+), `restore` (writes stock BOOT backup to sda10). Edit the script, not ad-hoc commands, when a step changes. Default ARGS lacks most boot args: pass `env ARGS="..."` when calling it directly.

### Commands (quick reference)
```
mv ~/Downloads/s9push.fish ~/.config/fish/functions/      # once
s9push 0183 battery-i2c
s9go out-0183 s9survey=5 a5fb_keep_on=1 s8rtc=(date +%s)               # survey boot
s9go out-0179 a5fb_keep_on=1 s9touch=2 s8rtc=(date +%s)                # normal boot
s9pull -g S9BAT
```
Undo (phone in TWRP): `adb push ~/s9-backup/boot-sda10.img /tmp/b.img` then `adb shell "dd if=/tmp/b.img of=/dev/block/sda10 bs=1048576 conv=fsync; sync"` (or `s9.sh restore`). Backup `~/s9-backup/boot-sda10.img` 58M, sha256 `c71d2ba9...ed931a`.
Symbolize kernel addresses: `bash tools/dreamlte/sym.sh KERNEL ADDR...` or `~/swift/usr/bin/llvm-symbolizer --obj=KERNEL 0xfffffff0XXXXXXXX` (kernel text is 0xfffffff007...). Disassemble to a file, then `grep -n` / `sed -n 'A,Bp'`.

---

## 4. Hardware facts, S9+ (SM-G965F, bootloader G965FXXUHFVG4)

Sources: TWRP/Android dumps in `star2lte-facts/` (incl. `live.dts`, local, ~400 KB), measured unless marked. Board DT "Samsung Star2 rev26", EXYNOS9810.

- **GIC:** GICv2 (GIC-400), NOT GICv3: `arm,cortex-a15-gic`, GICD 0x10101000, GICC 0x10102000 (the gicd/gicc at 0x17cf1000 is the audio abox_gic). **Timer:** `arm,armv8-timer` 26 MHz, physical timer PPI 14 = INTID 30 (fires every ~17.65 ms, 459023 ticks).
- **CPUs:** cpu0-3 = Cortex-A55 (impl 0x41, part 0xd05), MPIDR_EL1 = **0x8100_0n00** (MT set, core in Aff1: 0x0/0x100/0x200/0x300). cpu4-7 = Samsung Exynos M3 / "Meerkat" (impl 0x53, part 0x002), **core 0 MPIDR 0x80000100** (measured); cores 1-3 = 0x101-0x103 (claim). Boot CPU = 0x81000000 (A55 cluster, `--boot-mpidr 0x0`). PSCI via `smc`, cpu_on 0xc4000003, cpu_off 0x84000002; AFFINITY_INFO (0xC4000004) answers -1 for every target (cannot poll core state). PSCI CPU_ON entry is **32-bit only** (hence the low trampoline). The kernel's /proc/cpuinfo has no `atomics` (LSE unverified).
- **PMU** syscon `samsung,exynos9810-pmu` at **0x14060000** size 0x10000 (the S8 value 0x16480000 is wrong here; PMU steps stay disabled for STAR2LTE). Reading the whole first 16 KiB aborts (likely +0x1030): only known offsets are read. FlexPMU/ACPM sequence CPU/cluster power (inference from debugfs names `flexpmu-dbg/{cpu_status,cur_sequence,lpm_count,mif_always_on,seq_count,seq_status,sw_flag}`, `exynos-pd` has only peripheral domains).
- **RAM:** dt banks 80000000+0x3c800000, c0000000+0x20000000, e1900000+0x1e700000, 0x880000000+2 GiB, 0x900000000+2 GiB. High bank 0x880000000-0x97fffffff = 4 GiB contiguous (6 GiB total). **Firmware-reserved** (12 entries): 0x0fb200000+40MiB, **0x880000000+540MiB (to 0x8a1c00000)**, 0x0f9200000+32MiB, 0x0fda00000+~28MiB, 0x0ff800000+8MiB, 0x0f0000000+146MiB, 0x0af800000+32MiB (rkp), 0x080000000+4KiB, 0x0c0000000+512KiB, 0x0e1900000+30MiB, 0x0b8000000+2MiB (tima), 0x091300000+4KiB (names never matched).
- **Partitions:** BOOT `sda10` (57,671,680 B = 55 MiB), RECOVERY sda11 (65 MiB), DTBO sda9 (8 MiB), EFS sda3, CPEFS sdd1, PERSISTENT sda14, SYSTEM sda18, CACHE sda21, **USERDATA `sda25`** = 50,925,645,824 B (~47.4 GiB). (S8 was sda7/sda24: never reuse.)
- **UFS:** HCI 0x11120000, VS 0x11121100, protector 0x11130000 (identical to S8, S8 UFS code carried over), PHY 0x11124000, io-coherency 0x11010700, FMP present. UFS VER 0x210; first TUR "not ready" cured by SSU wlun ACTIVE. GPT: BOOT 0x4c02-0x8301, SYSTEM 0x10c80-0x26287f, USERDATA 0x309180-0xee47fa.
- **Display:** DECON_F 0x16030000 (command mode, HW trigger, 1440x2960), DECON_T 0x16050000, DSIM 0x16080000, DPP 0x16021000-0x16026000, SYSMMUs 0x160a0000/160b0000/160c0000. **Trigger register DECON_F+0x70 = 0x16030070**: reads 0x3070, we write 0x1281, reads back 0x1001 (the S8 value works). **S-Boot framebuffer 0xcc000000** (`s3cfb.bootloaderfb`), 1440x2960.
- **Touch:** Samsung `sec_ts` dt node at 0x48 on `hsi2c@104B0000`, irq gpa1-0 (`<0x6c 0 0>`), rails `tsp_io` = s2mps18 **LDO35** 1.8 V (reg 0x6c) and `tsp_avdd` = **LDO43** 3.0 V (reg 0x74); sec,regulator_boot_on. The chip actually speaks the Samsung **S6SY761** protocol (see section 7).
- **PMIC:** `s2mps18mfd` + `s2mpb03` behind **ACPM IPC channel 2** (no direct access; no s2mps18 regmap in debugfs), plus `speedy@141C0000`.
- **Keys** (AON block 0x14050000, active low): volup gpa1 bit3, voldown gpa1 bit4, bixby gpa1 bit6 (all +024), power gpa3 bit4 (+064). Bank order gpa0 gpa1 gpa2 gpa3 gpq0 gpa4, 0x20 stride (assumed): gpa1 at +020 (DAT +024), gpa2 +040. pinctrl@10430000 banks gpp0 gpp1 gpp2 gpp3 gpg0 gpg1 gpg2 (gpp1 at +020). Linux codes: power, volup 0x73, voldown 0x72, Bixby 0x2bf. (Earlier "AON +044 = gpa1 DAT" was wrong.)
- **TWRP limits:** no busybox, no /dev/mem (CONFIG_DEVMEM unset, ENXIO), PMU not in regmap debugfs; `mount -t debugfs none /sys/kernel/debug` works (`decon/` dumps empty, `event0` = driver events only). ramoops NOT configured (`mem_address=0 mem_size=0`, pstore empty).
- **ACPM (measured on our boot):** firmware "92dbdb1 yongjin_man" 18:02:42 Jun 11 2018, 18 channels at SRAM +0x5bfc, 13 the AP's. Channel 2 = PMIC, polled queue 5 x 16 B, in +82f0, out +8290. Mailbox 0x14100000 (INTGR0 +08 = 1<<(16+ch), INTCR1 +20, INTSR1 +28); SRAM 0x02039000 (first 0x3000 fault, map from +0x3000), initdata +0x7F00. PMIC request: word0 = (type&0xf)<<8 | reg | seq<<16 (seq 1..63); word1 read = 0, write = 1|val<<8, update = 2|val<<8|mask<<16; reply word1: bits 31:24 error, 15:8 value. Type 1 = S2MPS18 PMIC block, type 2 = RTC.
- **Touch rails (measured):** after S-Boot LDO35 (0x6c) = 0x2c and LDO43 (0x74) = 0x30 = OFF (on = bits 7:6 set, 0xc0). TWRP Linux has both enabled (different state: not our boot).

---

## 5. Decisions (do not re-argue)

- Logging: on-disk ring at the end of USERDATA, no ramoops. Kernel ring "SWEETLOG" = last 1025 blocks (written by the XNU UFS driver every `ufslogsecs`; decoder `tools/sweet-log.py`; needs root mount, so `rd=ufsroot0 ufsroot=USERDATA ufslogsecs=2`); loader "LDRLOG" = 64 blocks directly below (loader RAM 0x8f0100000, `ufs_log_write` in `shim/star2lte/ufs_probe.c`, decoder `tools/star2lte/ldrlog.py`; write path verified on hardware). Entry marker in loader RAM 0x8f013f000, outside the XNU window. Loader log/DMA at 0x8f0000000+ (`UFS_PROBE_DMA`, loader.c:27).
- XNU RAM window at **0x8c0000000** (not 0x880000000, firmware-reserved). Single source of truth: `DRAM_BASE` in `tools/mkadt_star2lte.py`; loader refuses payloads overlapping 0x880000000-0x8a1c00000. **Size 768 MiB** (`DRAM_SIZE = 0x30000000`, line 37), the max without moving `UFS_PROBE_DMA`; bank ends 0x980000000. Do not widen for now (v14 free memory at target, caches churn).
- Boot MPIDR is a runtime value from the ADT, not a kernel constant.
- Daemon fixes go in the root image (launchd disabled db), not in the kernel.
- `a5fb_noconsole` (A5XELTE name), not `sweetfb_noconsole`, mutes the console (SweetFramebuffer.cpp ~392).
- Do not write the PMIC RTC; use `s8rtc`.
- Survey level 3 stays off (reads USI+4, faults); level 12 must not be run (loop bug).
- Diagnostics S9AFF/S9PMU/S9ID/0151 still in the tree (S9ID is the only way to read M3 ID registers): remove once stable.

---

## 6. Bring-up history (chronological, one line per finding)

### 6.1 Loader and first boots (2026-11-04/05)
- Loader (fork of S8, `shim/star2lte`) cross-compiles clean with clang+lld; S8 probes (DECON 0x12860070, SPEEDY, touch, Mongoose PMU) compiled out unless `-DSTAR2LTE_S8_PROBES`. ADT from `tools/mkadt_star2lte.py` (needs `sys.path` insert for `import adt` under `python3 -I`: fixed). `tools/star2lte/make-boot.sh` needs clang lld llvm.
- First boot: loader ran to `JUMP TO XNU` at EL1, SCTLR 0x30c5183e (MMU off), DTB 0x8a000000, payload 0x89000000-0x89fbb880, entry 0xfffffff007424488 (pa 0x8c1424488), 10 segments copied. Logo stayed because the display trigger was not ported; after the 0x16030070 write the screen showed text.
- Patch 0125 (`apply-star2lte.py`, `verify-apply.py`, `export-0125.sh`) turns off S8-only touches: ramoops klog 0x92180000, S6SY761/MAX77865 I2C, Mongoose PMU CPU_ON, DECON 0x12860000 frame-done wait; entry marker -> 0x8f013f000; MPIDR from ADT; boot cluster first; keys default off. Later changes go in new patches.
- Kernel then ran to `trust caches unavailable` (our own benign patch 0015 message), stalled after AppleCLCD ("presented as 1125x2436") and before any `SWEET UFS`. Idle diagnostics (0126 v1-v4: `a5xelte_idle_diag`, framebuffer heartbeat, thread dump) showed timers/IRQs work and the kernel was just slow, not hung (heartbeat rows kept changing). The v2 print flood once hid the evidence: cap prints.

### 6.2 launchd hang = PAN fault storm (2026-11-05/06)
- launchd hung in dyld's first `mach_vm_allocate`. Rejected: low memory (free 130x the reserve), scheduler starvation (pri 37, last_run <1 ms ago), dyld loop. Sampler patches 0127 (non-blocking, `regs` line first) and 0128 (`SMP vm ...`, `kernel state`) were the tools.
- **Root cause:** `_bcopyin` took permission faults forever (ESR 0x9600000f: DFSC 0xf = permission fault L3, READ) on a valid user page, because SPSR.PAN=1 on exception entry (SCTLR_EL1.SPAN=0) and copyio did not clear PAN (`__ARM_PAN_AVAILABLE__` not defined, `user_access_enable()` no-op); `arm_fast_fault_internal` saw sufficient permissions and returned success, endless retry (`S9KAB` >40000).
- **Fix 0132** (`make-0132.py`): set SCTLR_EL1.SPAN (bit 23) in `SCTLR_EL1_DEFAULT` (osfmk/arm64/proc_reg.h); RES1 on cores without PAN, safe on M3. Result (v13): launchd runs daemons (309 `exec xpcproxy`, SpringBoard/backboardd exec'd once each). 0130's `faults`/`msgs_sent` counters are garbage; `syscalls_mach/unix` valid.
- v14: RAM 768 MiB; one crash only (`driverkitd` jetsam, `ns 1 code 7`, probably per-process memory limit, unverified).

### 6.3 SMP: A55 cores 0-3 work, M3 cores 4-7 start (2026-11-07/08)
- cpus=2 first failed: `PSCI CPU_ON rc=0` then `cpu=1 NOT alive after 10s`. **0136/0139-0141:** low trampoline at PA **0x89f00000** (a choice inside the dead S-Boot initrd tail, not measured free; writes marker 0x7701, real entry stored there) fixes the 32-bit entry; core wakes at EL1 (EL2/ICC_SRE_EL2 suspect out). Earlier "core 1 starts" claim for 0136 was wrong (stale kernel, cpus=1 run).
- Core hung in `reset_vector`: woken core MPIDR_EL1 = 0x81000100, kernel/ADT expected 0x1. **0145:** ADT uses MPIDR_EL1 numbering, PSCI target converted by `SWEET_PSCI_TARGET` (A55 0..3, M3 0x100..).
- Then "Ticket lock unexpectedly owned" (lock_ticket.c:155): XNU derived the logical cluster from MPIDR Aff1 and created extra clusters without a pset. **0149** (`machine_routines.c`: cluster-id from ADT, every core's Aff1 registered in `cluster_phys_to_logical`) and **0150** (`MAX_CPU_CLUSTER_PHY_ID 7` for A5XELTE, assertion `machine_routines.c:1058`). `tools/mkadt_star2lte.py`: M3 nodes also get `arm,cortex-a53` in `compatible` (else "cpu=4 NOT registered"), `cluster-id` 0 for ALL cores (a second pset brings the panic back: hypothesis not `__AMP__`, unproven). cpus=4: cores 0-3 "came alive; SGI1 OK".
- M3 (cpu 4-7): `CPU_ON` for cpu 4 needs six PMU fields written first (claim): `+0x1088[31:24]=0x8D`, `+0x2114/0x2180/0x21EC/0x2258/0x2384 [1:0]=2` (**0153**; measured before = 0xc7150000 and 1,1,1,1,1; all read back; firmware then powers the cluster: `+0x2000 0->f`, `+0x2004`, `+0x2040`, `+0x2044`, `+0x2380 40000->1`). PSCI target for cpu 4 = 0x100 (ADT 0x400): works. Targets for cpu 5-7 = 0x101-0x103 not individually confirmed. Core ID collision (M3 core 0 = 0x0100 vs A55 core 1) fixed via MIDR implementer 0x53 -> `0x400 + (Aff0 << 8)` in `start.s` (**0155**) and `ml_get_cpu_number_local`/`ml_get_cluster_number_local` (**0157**).
- With all 8 cores xpcproxy died with SIGILL at one shared-cache pc (0x1d473b588) and launchd exited -> panic "initproc exited". Guess: commpage advertised A55-only features; **0159** clamps ID regs (ISAR0 &= 0x11120, ISAR1/PFR1/MMFR2 = 0, PFR0 without FP16/RAS/DIT); Apple logo followed (consistent, not proven). M3 real ID registers never read (0158 `kprintf` does not reach the log ring; photos only).
- Result (v35, 0160, cpus=8, **measured**): `A5XELTE CPU: 8/8 CPUs initialized, SGI1 verified`, cpu 0-7 all "came alive; SGI1 OK". Boot-time gain unclear: 4-5 h overnight run (v34, unexplained), ~50 min with 1 core, ~20 min to "Hello" with 8 cores + other changes (not separable), ~5 min later.
- Unverified: whether 5-7 are individually correct, 4-core vs 8-core time.
- Free TWRP measurement idea (not done): diff `flexpmu-dbg/cpu_status` with cpu4-7 online vs offline.
- Overclock NOT started: CPU frequency never measured (cycle counter vs 26 MHz timer first); above stock needs voltage.

### 6.4 Display and speed
- Display path (patch 0046, `IOMobileFramebufferUserClient` swap): without `sweetfb_native=1`, backboardd presents 1125x2436 (centered, dst 157,262) and nothing writes to it (black rectangle). **With `sweetfb_native=1`** surface is 1440x2960 at 0,0 and the Apple logo + bar appear. `SWEET FBDIAG` (0133, limited by 0161: first 20 then every 1000th) shows iOS writes opaque black (`nonblack 0/64`) at the early phase.
- The swap copy `memcpy`s surface rows into `fPixels`, skipping if elementWidth/Height != 1, memory NULL, length check fails, or bpe != 4. Every swap copies the full 1440x2960 BGRA surface (~17 MB), present capped at 10 Hz (`sweetfb_hz`). **0162 FBTIME (measured):** copy 3.7-5.6 ms per swap = ~5% at 10 Hz: **copy is NOT the bottleneck, do not optimize it**; the slowness is iOS's CPU rendering. Swap rects `a`/`b` were full-screen in the first 32 swaps: the "dirty-rect" idea was wrong.
- Console text over the progress bar: boot-arg name (`a5fb_noconsole=1`, user-reported GONE); heartbeat box (patch 0126) fixed by **0160** (`hb_row` returns when `sweet_console_muted`; pe_fiq.c).
- **Black screen after swiping up "Hello" (open, workaround exists):** v36 order: assetsd crash, `display off`, PosterBoard SIGTRAP, `display on`, `backboardd sel 79`, user power press = `display off`; FBDIAG all `nonblack 0/64`. Cause (strong guess): `display off` fades `fPixels` in place to black (SweetFramebuffer.cpp 250-275 in the vsync handler: halves every channel for 6 steps then writes 0) and `display on` only sets fDirty, so the panel stays black until iOS sends a NEW swap. **Workaround `a5fb_keep_on=1`** (ignores display-off): user-reported the Setup language list appears and the screen no longer goes black. Proper fix not done: fade into a copy / redraw last swap on "on" (needs `grep -n 'fPowerOff\|fFadeStep\|fPixels' iokit/Kernel/arm/SweetFramebuffer.cpp`). Header comment (line 19): selector 12 `RequestPowerChange [state]`, 0 = display off. With keep_on the power button does nothing (expected, not a freeze).
- The language list looked "frozen" with a too-small language icon (user-reported): at the time there was no touch, so it likely just waited for a tap; the small icon is unexplained (may relate to the iPad symptom). Not re-checked since touch works. `sweethidtest=N` fakes a Home press every N s (advanced Hello -> language list on the S8; v45 key 0x40 down/up works).
- Crashes seen: `driverkitd` (jetsam, known), `assetsd` (abort, pc 0x1cf20f198), `PosterBoard` (SIGTRAP, pc 0x1ce370268; BEFORE `exec Setup`, so not the Setup-freeze cause; two execs one crash line; heap scan shows only `Poster Extension Assertions:` and `com.apple.posterboardservices.active-wallpaper-observer`/`...dataModel`; the prior agent's `_stateLock_setupSwitcherConfigurationForFirstTime` is unverified). Symbolizing needs `ipsw` (not installed on the PC; `~/ios-build` has IPSW dmgs 087-86593-047, 087-86698-044, 087-86715-047).

### 6.5 Root image and daemons
- Root image: HFS+ built by `tools/mkiosroot.sh` (runs `fsck.hfsplus -f -y` before `-n`), `/home/vsl/ios-build/ios16-root.img` (17179869184 B = 16 GiB, sha256 of the edited image 867108dcb661ce16de9af0f9c69f8b6e87bd5ed04d566acc5a447264ee46bdc7, **never read back on the phone**; the repo's `out.img` is the 17 MB BOOT image, NOT the root). Written to USERDATA sda25 (`adb exec-in` into `dd`, then read back + sha256). Backups `.bak`/`.bak2` were DELETED (no undo copy; rebuild with mkiosroot.sh). Read-only mount: `sudo mount -t hfsplus -o loop,ro <img> /mnt/s9root`; rw needs `-o loop,rw,force`. The `fsck.hfsplus -n` after `-y` always says "minor repair" (Linux quirk, guess): ignore.
- `tools/star2lte/disable-daemons.sh <img>` v2 (fsck -y first, skips labels with no plist, last line fsck -y) adds launchd `disabled.plist`: bluetoothd, fairplayd.H2, nanotimekitcompaniond, familycircled, carkitd, wcd. SKIPPED (no plist): fmflocatord, UARPUpdaterService*. Respawn loop gone (measured v36: xpcproxy 354 execs vs 4234; v38: 175 vs 232, 0 execs of the newly disabled ones). Candidates for more disabling: pick from exec counts only if SpringBoard/backboardd do not need them (earlier counts: mobiletimerd, fitnesscoachingd, liveactivitiesd, routined, remotepairingdeviced ~112 each).
- Extract dyld/launchd from the image: `sudo mount -o loop,ro -t hfsplus ~/ios-build/ios16-root.img /mnt/x; cp /mnt/x/usr/lib/dyld /tmp/dyld; sudo umount /mnt/x`.

### 6.6 Keystore (AKS) stub, patch 0038
- Handles kAKSWrapKey (10) and kAKSUnwrapKey (11) with a reversible stub (8 bytes 0xA6 + 32-byte key = 40); `default: ret = kIOReturnUnsupported` (0xe00002c7). Unsupported (minor): 2/3/6 (CreateBag/SaveBag/LoadBag), 31 (profiled), 34 (datamigrator), 93.
- **Selector 17 = kAKSGetDeviceState**: stub answers a valid-looking DER blob, 0x0. Spotlight alone makes 66,217 calls (others <800): a loop inside Spotlight, not a crash loop (one `exec Spotlight`, no errors). Guess: it waits for a state the stub never reports. The loop is the likely cause of the "slower than before" after touch let the user open Spotlight. Also pushes early S9TOUCH lines out of the log ring. The IOLog (0038 line ~271) was rate-limited (first 600, then 1 in 500).

### 6.7 CI and build infrastructure
- GitHub Actions workflow `xnu`, `runs-on: macos-15` (macos-14 retired 2026-11-02; Xcode 16 `iig` emits IORPC.kernelContent this xnu lacks if it ever fails in iig/Xcode). Only one run at a time per branch; push touching `xnu/patches/**` starts one. Public repos get free macOS minutes (private 10x), build ~9 min (first ones up to 2 h).
- BearSSL: `0020-stage-bearssl.sh` prefers a vendored `xnu/patches/bearssl-<sha>.tar.gz` (any `bearssl-*.tar.gz|xz|tgz`, any layout, warns if not the pinned commit 7bea48e5e850ab4cafbe68d3765cdaba13a86d6f); bearssl.org returned 502 for packs (`git ls-remote` works; gitweb snapshot route `https://bearssl.org/gitweb/?p=BearSSL;a=snapshot;h=<sha>;sf=tgz` works with `git get-tar-commit-id` check). `find -printf` removed (BSD find). 0019/0026 scripts have 3 retries. Fallback 0.6 release (Debian `bearssl_0.6+dfsg.1.orig.tar.xz`) unverified against patch 0098.
- KDK 13.5 (CI failure at runs from 42469127800): workflow step "Install KDK (authenticated)" = `gh release download 22G74 --repo dortania/KdkSupportPkg --pattern '*.dmg'` with retries + size/imageinfo check, before Build; `[ -f "$lib" ] || continue` in the kdk-libs loop. Generator `tools/star2lte/fix-ci-kdk.py` (idempotent).
- `.gitignore`: `star2lte-facts/`, `WORK/`, `*.img`, `out.img`, `logs/`, `shim/dreamlte/out/` (CRLF stripped).
- First-time setup (done): `gh auth login`, `git init -b main`, `gh repo create`, `bash tools/dreamlte/prep-xnu-tree.sh xnu/patches WORK` (tree=WORK/xnu commits=122; 0031 and 0041 skipped, expected), `export-0125.sh`.

---

## 7. Touch and keys (works; history for reference)

- **Chip:** Samsung S6SY761 protocol on hsi2c10 (`hsi2c@104B0000`, addr 0x48). Commands: 0x55 boot status (0x20 = app), 0x52 id, 0x21 fw check, 0x23 panel info, 0x10 sense on, 0x62 clear events, 0x60/0x61 read events (8 bytes, `left = e[7]&0x3f`). Event: kind `e[0]&3 == 0`; id `(e[0]>>2)&0xf` (1-based); state `e[0]>>6` (3 = up); x = `e[1]<<4 | e[3]>>4`; y = `e[2]<<4 | e[3]&0xf`. IRQ = AON 0x14050000 +0x24 bit0 low = events waiting (our own offset; fallback poll every 4th tick).
- **How it got working:** 0163 `sweettap=x,y,secs` tap injector (calls `sweet_hid_touch`, 0058/SweetHID.cpp). 0164 survey (`s9survey`, started from `a5xelte_touch_probe`) panicked reading USI+4 (esr 0x96000010 external abort, FAR ...43e004). 0165 level 1 = AON only (key map above). 0166 `a5keys=1` clean down/up (power=0, volup=1, voldown=2, bixby=3). 0167 nofault probe (`s9_probe_read32` + `sleh.c` ext-abort recovery) works: hsi2c@104B0000 +00..+40 readable (0), USI 0x10411000 +00=1, +04 FAULT; pin block 0x10430000 readable; 0x15a80000, 0x10400000, 0x10800000 FAULT (so 0x104xxxxx is NOT wholly dead). 0168 level 5 read-only dumps: hsi2c10 0x00-0xbf all 0, 0xc4..0xdc constants (c4=1 c8=1 cc=02070000 d0=02010001 d4=02020000 d8=02040000 dc=00400040); USI +08/10/18/20/28/30/38 = 4; gpp1-4/5 (hsi2c10) read 0 (not muxed), gpp1-6/7 read 1. 0175 USI word + pin-mux + ACK probe (controller alive, no ACK). 0177 `s9touch=1|2`: ACPM init, **LDO35/43 on** (rails were OFF), probe 0x48, S6SY761 init, polled events, HID feed (still no ACK, err 1 = our timeout). **0178** `s9t_reset` clears USI_CON (+0xC4, reset value 1 holds the block in reset) + HakiOS-style timing/sequence: **touch works** (USI_CON as the cause is likely, not directly measured: the S9TOUCH 4 line was pushed out of the ring).
- **hsi2c10 recipe that works:** USI word 0x1041101C = 4, gpp1 CON pins 4/5 = 2, PUD pins 4/5 = pull-up (0xf00), then `s9t_reset`: USI_CON=0, SW reset, timing from 200 MHz input at 400 kHz, master, TRAILING 0xffffff, TIMEOUT bit31 clear, CONF bit31. Message: FIFO_CTL 3|trig<<4|trig<<16, CTL master|rx/tx, ADDR 0x48<<10, INT_EN 0xf80, AUTO_CONF len|read<<16|stop<<17 then |RUN(1<<31) as a second write. (Source: other project; the working code is ours in `bsd/dev/a5xelte_touch.c`.)
- **Range:** this build uses the `#if ARM64_BOARD_CONFIG_A5XELTE` branch of SweetHID.cpp: touch grid **1080 x 1920** (NOT 1080x2400, that is the S8 branch and 0058's clamp; `s9touch_h=2400` clamped y at 1919). `s9touch_w=1080 s9touch_h=1920` fixed taps (user-reported); 0179 makes them default.
- **Keys:** `a5keys=1` required (A5_KEYS_DEFAULT still 0; default now in s9go). Bixby = Home works (unlocks lockscreen); power: double press locks, single does nothing (cause unknown); volume: no visible effect (unchecked).
- **Ringer remap lead** (theapplewiki Dev:IOHIDFamily, iOS 6 era, may differ): keyboard usage page 0x0B usage 0x2e = "Ringer"; the real switch is a 2-position slider, so Bixby would toggle a software state and post down/up; which value = silent unknown; usage 0x0B/0x2E is a guess. Button posting code (SweetHIDButtons / a5keys path, `keyboardEvent` in 0058) NOT yet read.

---

## 8. Open symptoms

- **iPad symptom (user-reported):** some apps look iPad-sized; Settings says "log in to your iPad". ADT is `iPhone10,3` / `D22AP` (measured, strings of `shim/star2lte/out/star2lte.adt`), so not the ADT. Guess: MobileGestalt/screen-size logic, odd reported screen size (1080x1920 logical grid, 1440x2960 fb). No repo hit for mobilegestalt/ipad. **User description (session 7, user-reported):** only in the Phone app, dialer digits smaller and centered; Settings layout also looked smaller, like a phone-sized layout on a different screen. Not investigated yet. Ideas (guesses): logical screen size/scale or device class handed to UIKit (fb is 1440x2960 but the touch grid is 1080x1920 and iOS presents 1125x2436 without `sweetfb_native`); next evidence = photos of Phone and Settings plus whatever reports the screen size.
- **One-off panic (0181 boot, pre-logo):** kernel data abort CPU 1, pc 0xfffffff007419f8c, lr 0xfffffff007419f18, far 0xfffffffffffffff8 (NULL-8 read), esr 0x96000005. Same boot line worked on retry; not symbolized. Chase only if it repeats (needs kernel Mach-O + nm).
- **Boot time variance:** 4-5 h overnight (v34) unexplained; ring wrapped (5.8 MB in 4 MiB).
- **Spotlight AKS 17 loop** (section 6.6), **fade bug** (6.4), PosterBoard/assetsd crashes (6.4), power-button single press, volume keys.
- Console text after the bar fills (iOS stops swapping): not checked.
- The v37 "freeze while drawing Hello" (log ends in exec xpcproxy / nanotimekitcompaniond, no panic, power button not tried): never explained.

---

## 9. Reference: boot args, files, other project

**Boot args (inside s9go; the `boot-args:` line of the build output is the check):**
`debug=0xc serial=3 cpus=8 keepsyms=1 -noprogress wdt=-1 wdt_test=no_user_checkin a5touchprobe=0 rd=ufsroot0 ufsroot=USERDATA ufslogsecs=2 ufsrw=1 rootrw=1 unentitled_ios_sim_launch=1 ignition_level=1 launchd_unsecure_cache=1 sweetfb_native=1 sweetfb_noconsole=1 a5fb_noconsole=1`, plus per run: `a5fb_keep_on=1` (screen stays on), `s9touch=2` (touch thread), `a5keys=1` (default in s9go), `s8rtc=(date +%s)` (date), `s9survey=N` (surveys), `sweethidtest=20`, `sweetscan=...`/`sweetsample=...` (samplers), `s9nocpuon=1` (skip PSCI CPU_ON, 0148). Removed on purpose: `-enable_kprintf_spam startup_debug=1 sweetsample=SpringBoard`. `cpus=N` is REQUIRED for SMP (default 1).

**Code map:**
- `bsd/dev/a5xelte_touch.c`: S9 ACPM helpers (`s9a_*`, `s9a_pmic_read(type,reg,&v)` returns 0 ok), hsi2c (`s9t_reset`, `s9t_msg(r,reading,buf,len,stop)`, `s9t_addr`), survey thread `s9survey_thread` (level 5 = the read-only vehicle for 0180-0182, `s9survey=5`), touch thread `s9t_thread` (`s9touch=2`), `s9bat_test`.
- `iokit/Kernel/arm/hid/SweetHID.cpp`: touch grid, edge flag, SWEET HID log. `iokit/Kernel/arm/SweetFramebuffer.cpp`: swap copy, fade, `a5fb_*` args, FBTIME/FBDIAG. `SweetCPU.cpp`: CPU startup (startCPU, trampoline).
- `xnu/patches/0038-sweet-applekeystore.patch` (AKS stub), `0046-sweet-iosurface-iomfb.patch` (display path), `0058` (SweetHID), `0065` (secondary entry: never edit), `0124-dreamlte-s8.patch` (donor S8 layer, incl. PEGetUTCTimeOfDay), `0125-star2lte.patch`, `0126` idle diagnostics, `0127/0128` samplers, `0132` SPAN, `0145-0150` cores/clusters, `0153-0159` M3, `0160/0161` heartbeat/FBDIAG, `0162` FBTIME, `0163-0168`, `0175-0182` touch/survey/battery.
- `tools/star2lte/`: `make-NNNN.py` generators, `s9.sh`, `make-boot.sh`, `collect-hw-facts.sh`, `ldrlog.py`, `disable-daemons.sh`, `findbase.py`, `aks-ratelimit.py`, `fix-ci-kdk.py`, `skip-setup.sh` (untracked, optional). `tools/mkadt_star2lte.py` (ADT: M3 `arm,cortex-a53`, cluster-id 0, DRAM_BASE/SIZE). `star2lte-facts/live.dts`. `docs/star2lte-s8-constants.txt` (S8 values to re-measure), `docs/star2lte-facts/`.

**Patch index (older):** 0151 AFFINITY_INFO probe (useless, remove) | 0152/0154 PMU snapshot diff on cpu 1 and 4 | 0153 six PMU writes before cpu 4 CPU_ON | 0155 start.s M3 MPIDR map | 0156 `a5xelte_send_ipi` non-fatal + `S9IPI` mask log | 0157 `sweet_norm_mpidr` | 0158 `S9ID` ID-register kprintf (diagnostic) | 0159 commpage ID clamp | 0141/0142/0144 secondary-entry markers (diagnostic) | 0146 ticket-lock panic detail | 0147 SCTLR/TCR/MAIR/TTBR1/ACTLR print | 0148 `s9nocpuon`.

**Other project `~/Downloads/ios-s9plus-exynos` (HakiOS, APSL 2.0: read for facts, write our own code):** `core/drivers/power/` has `hakios.s2mps18_rtc.c` (211 lines), `hakios.max77705.c` (739), `hakios.battery.c/.cpp`, `hakios.battguard.c`; `core/drivers/core/hakios.exynos_hsi2c.c`, `hakios.exynos_acpm.c`, `hakios.exynos_m3.c` (cites Samsung's exynos9810 kernel); `core/drivers/input/hakios.s6sy761.c`; `core/drivers/gpu` has exynos_dpu, backlight, mali; `metal-wip/` exists. GPU-acceleration claim UNVERIFIED (S8 README says Mali cannot run iOS Metal). `core/xnu/files/iokit/Kernel/GenericARMPE.cpp` has `findBootEpoch` (boot-arg `epoch=`, /chosen boot-epoch, then RTC driver).

---

## 10. Backlog (in order after the battery read)

1. Battery -> iOS: needs a fake/real battery service (separate from the I2C read).
2. Spotlight loop: find what it waits for (compare real iOS AKS answers, or log Spotlight's other calls; sel 17 never reports a state it waits for = guess).
3. iPad symptom (description received, section 8).
4. Bixby -> ringer (read the button code first).
5. `A5_KEYS_DEFAULT=1` for STAR2LTE; fix the fade bug (6.4); remove survey levels and diagnostics (S9AFF/S9PMU/S9ID/0151/0141-0148); trim S9TOUCH logs.
6. Confirm M3 cores 5-7, measure CPU frequency, measure 4- vs 8-core boot time.
7. Later: AKS 2/3/6, more RAM (needs `UFS_PROBE_DMA` moved), more disabled daemons, symbolize PosterBoard/assetsd (install `ipsw`), real GPU driver.

## 11. Risks and caveats

- **0182 wrote pin registers with guessed bank offsets** (gpm14 = +0x1c0, gpm15 = +0x1e0, guess; likely another bank, see section 2); CMGP USI was NOT written (code read, session 7). Anything after it that writes hardware must print its target registers first. A peripheral read can panic the kernel (0164): each survey level must say in its log what it touches; use the nofault probe.
- All new code is mock-tested only (anchors), never compiled by the assistant; CI and device are the user's. 0177/0178 were compile-checked against stubs only.
- 0177 writes the two LDO registers (on, and off/on cycle if the chip does not answer); 0178 clears USI_CON and writes hsi2c timing; no panic path seen.
- Everything marked "claim" (other project) is untested on our hardware unless also marked measured.
- Root image checksum never verified on the phone; no undo copy of the root image.
- `s9push`/`s9install` interaction (section 3), `s9pull` default version not confirmed installed.
