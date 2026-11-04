# frankenstnine - Galaxy S9+ (SM-G965F, star2lte, Exynos 9810) port - progress

Project name: **frankenstnine** (Frankenstein + S9; the user's choice, turn 5). Only display names use it; directory, patch and code names (`star2lte` etc.) stay.
GitHub: user `georgev-6974`, repo created as `s9plus-ios` (renamed to `frankenstnine` in turn 5, see step C). Local folder is still `~/Downloads/ios-galaxy-s9plus`.

# HANDOFF (read this first; last updated 2026-11-04, turn 6)

**Goal**: boot an iOS 16 XNU kernel on a Galaxy S9+ (SM-G965F, Exynos 9810) via a custom loader in the BOOT partition (`sda10`), forked from the S8 port.
**Standing rules** (AGENTS.md): never reuse an S8 address without a measurement; keep build success / kernel markers / screen reports / iOS runtime as separate claims; keep dumps, serials and Apple binaries out of git; confirm every destructive step with the user; donor files (`shim/dreamlte`, `tools/dreamlte`, `DREAMLTE_PROGRESS.md`, `NOTES.md`) are not edited.
**State**: loader cross-compiled before turn 4 (never run; the turn-4 edits to it are NOT compiled, no clang in the assistant sandbox). ADT generator and make-boot.sh exist (offline only). Patch 0125 exists as a script (`apply-star2lte.py`), checked on a pseudo-tree only. **No phone measurement beyond the TWRP facts below; no kernel built; no boot attempted.**
**Blocked on the user**: see "What you do next" (user has a generated, real-tree-verified 0125 patch; next: re-unzip, send two small facts, push to GitHub and build).

## About the user (keep in mind every turn)
- Comfortable with Linux and the shell, but **new to kernels and git**: still give exact copy-pasteable commands with the expected output and what to do if it differs; explain each kernel/git term in one or two plain sentences the first time it appears (what a repo, commit, push, CI run, boot image, DT/ADT is).
- Shell is **fish** on **Arch Linux** (not bash). Run `.sh` files as `bash path/to/file.sh` (they are not executable; fish says "not an executable file"). Fish differences: no `$(...)` is fine in fish 3.4+, but avoid `&&`-chains with bash syntax, use `; and` or separate lines; `set VAR value` instead of `VAR=value`. Install packages with `sudo pacman -S NAME`.
- Working directory: `~/Downloads/ios-galaxy-s9plus` (every command below assumes `cd ~/Downloads/ios-galaxy-s9plus` first). The user's copy is the ORIGINAL zip plus what they ran; new files from the assistant must be copied in (step 0).
- No git repo exists in that folder yet (the zip has no `.git`).

## Done by the user so far (user-reported 2026-11-04)
- Fact collector ran: `bash tools/star2lte/collect-hw-facts.sh star2lte-facts --boot-backup` -> `star2lte-facts/` (incl. `boot-sda10.img`).
- Confirmed `/dev/block/by-name/BOOT -> /dev/block/sda10` (matches the notes).
- `bash tools/dreamlte/prep-xnu-tree.sh xnu/patches WORK` ran: `tree=WORK/xnu commits=122`, only 0031 and 0041 skipped (expected). The "refs/tags ... is not a commit" and whitespace warnings are harmless.
- Backup verified: `~/s9-backup/boot-sda10.img` 58M, sha256 `c71d2ba9...ed931a` equals the source.
- **`bash tools/star2lte/export-0125.sh WORK/xnu xnu/patches` succeeded on the REAL tree**: 5 files edited, `xnu/patches/0125-star2lte.patch` written (10 hunks, 5 files). So every 0125 anchor matches the real post-0124 source and the patch git-applies. (Kernel still not built.) The patch file exists only in the user's folder, not in the assistant's zip: do not delete it when unzipping.

## What you do next (fish, Arch; stop and report at any failure)
Always start with `cd ~/Downloads/ios-galaxy-s9plus`.
**A. Update your folder with the assistant's newest files** (turn 4 changed the loader, the ADT generator and these notes). Download `ios-galaxy-s9plus-progress.zip` from the chat, then:
   `cd ~/Downloads`
   `unzip -o ios-galaxy-s9plus-progress.zip`
   This does not delete your `WORK/`, `star2lte-facts/` or your generated `xnu/patches/0125-star2lte.patch`. Check: `ls ~/Downloads/ios-galaxy-s9plus/xnu/patches/0125-star2lte.patch` still exists and `grep -n 8c0000000 ~/Downloads/ios-galaxy-s9plus/tools/mkadt_star2lte.py` prints a line.
**B. Two small checks, paste the output in the chat** (neither prints the serial):
   `cd ~/Downloads/ios-galaxy-s9plus`
   `grep -o 's3cfb[^ ]*' star2lte-facts/cmdline.txt`
   `grep -i -n 'cc0\|framebuffer' star2lte-facts/iomem.txt`
   Phone in TWRP, then this names the firmware-reserved regions (tells us what the 540 MiB block at 0x880000000 is):
   `adb shell 'cd /proc/device-tree/reserved-memory; for d in */; do echo "== $d"; ls $d; od -An -tx1 -v $d/reg 2>/dev/null; done' > star2lte-facts/reserved-named.txt`
   `cat star2lte-facts/reserved-named.txt`
**C. Put the project on GitHub so its macOS machines build the kernel** (your PC cannot build XNU). Plain-language terms: a *git repository* is this folder plus its history; a *commit* is a saved snapshot; *push* uploads snapshots to GitHub; *GitHub Actions* runs the `xnu` workflow on GitHub's Mac machines, which compiles the kernel and stores it as a downloadable *artifact*.
   Public repos get free macOS minutes; private ones are billed (macOS counts 10x), and one build can take up to ~2 hours.
   `sudo pacman -S github-cli`
   `gh auth login`   (GitHub.com, HTTPS, "Login with a web browser", follow the code prompt)
   `cd ~/Downloads/ios-galaxy-s9plus`
   `git init -b main`
   `git add -A`
   `git status --short | head -20`   (must NOT list WORK/, star2lte-facts/, *.img; if it does, stop and tell the assistant)
   `git commit -m "S9+ star2lte port"`   (if git asks who you are: `git config --global user.name "YOURNAME"` and `git config --global user.email "you@example.com"`, then repeat the commit)
   `gh repo create s9plus-ios --public --source=. --push`   (use `--private` if you accept the billing)
   Observed (turn 6, corrects turn 5): the first push DID start a run (it appeared in `gh run list` about a minute later; "no runs found" was GitHub lag). A manual `gh workflow run xnu.yml -f machine_config=A5XELTE -f keep_going=true` also works but only needed if `gh run list` is still empty after 2-3 minutes. Only ONE run at a time: a new push/run on the same branch cancels the running one.
   `gh run list`  then  `gh run watch`  (arrow to the run, Enter; Ctrl+C leaves it running).
   First failure seen: run 41908009114 died after ~2 min in script `0020-stage-bearssl.sh` with `www.bearssl.org ... HTTP 502` (their server, not our code). Fixed in turn 6: the three staging scripts now retry, and BearSSL falls back to two GitHub mirrors (commit hash still verified). To retry only the failed part of a run without a new push: `gh run rerun RUN_ID --failed`.
   To send updated files from the assistant: `cd ~/Downloads; unzip -o ios-galaxy-s9plus-progress.zip; cd ios-galaxy-s9plus; git add -A; git status --short; git commit -m "describe the change"; git push` (a push touching `xnu/patches/**` starts a new run by itself).
   Done when the run shows completed/success: `gh run download -n xnu-kernel -D xnu/out` then `ls -l xnu/out` (send that listing). If it failed: `gh run view --log-failed | tail -80`, paste it.
**D. Build tools for the BOOT image** (the loader is compiled on your PC): `sudo pacman -S clang lld llvm`  (`aarch64-linux-gnu-gcc` is optional). Then, with the exact kernel file name from `ls xnu/out`:
   `bash tools/star2lte/make-boot.sh xnu/out/KERNELFILE star2lte-facts/boot-sda10.img out.img`
   If the loader fails to compile, paste the error (the turn-4 loader edit is uncompiled). The warning `d22ap.adt missing, no /product node` is expected and harmless for now.
   **Size check**: `ls -l out.img` must be <= 57671680 bytes (the BOOT partition is 55 MiB). Bigger = do NOT flash; tell the assistant.
**E. First BOOT trial** (writes `sda10` only; needs step 2 of the old list: either a TWRP backup of Data or acceptance that the last 64 blocks of USERDATA are overwritten). Phone in TWRP, `adb devices` lists it:
   `adb push out.img /tmp/boot.img`
   `adb shell "dd if=/tmp/boot.img of=/dev/block/sda10 bs=1048576 conv=fsync; sync"`
   `adb reboot`
   Expect a text screen from the loader, or blank (the S9+ display trigger is not ported; blank alone is not failure). Wait ~1 minute, then POWER+VOL DOWN, then POWER+BIXBY+VOL UP for TWRP.
**F. Pull the logs** (`pull-log.ps1` is Windows-only), phone in TWRP:
   `mkdir -p logs`
   `adb shell 'b=$(blockdev --getsize64 /dev/block/sda25); n=$((b/4096)); dd if=/dev/block/sda25 of=/tmp/ldr.bin bs=4096 skip=$((n-1025-64)) count=64 2>/dev/null'`
   `adb pull /tmp/ldr.bin logs/ldrlog-v1.bin`
   `python3 tools/star2lte/ldrlog.py logs/ldrlog-v1.bin logs/ldrlog-v1.txt`
   `cat logs/ldrlog-v1.txt`  -> paste in the chat with what the screen showed (exception level, SCTLR, MPIDR_EL1, UFS probe result, whether the XNU jump happened).
**G. Undo** (phone in TWRP): `adb push ~/s9-backup/boot-sda10.img /tmp/b.img` then `adb shell "dd if=/tmp/b.img of=/dev/block/sda10 bs=1048576 conv=fsync; sync"`.

## File map (S9+ work only)
- `STAR2LTE_PROGRESS.md` this file. `docs/star2lte-s8-constants.txt` S8 values to re-measure. `docs/star2lte-facts/` measured text facts.
- `shim/star2lte/` loader (UFS + LDRLOG + XNU jump; S8 probes compiled out). `tools/mkadt_star2lte.py` ADT. `tools/star2lte/`: `collect-hw-facts.sh`, `make-boot.sh`, `pull-log.ps1`, `ldrlog.py`, **`apply-star2lte.py`**, **`verify-apply.py`**, **`export-0125.sh`** (last three new in turn 1-2).
- `xnu/patches/0124-dreamlte-s8.patch` donor S8 layer; 0125 will be generated (step 3).

## Decisions (do not re-argue)
- Logging: on-disk ring in USERDATA (no ramoops on this TWRP). Entry marker lives in loader RAM `0x8f013f000`, outside the XNU window.
- XNU RAM window = 512 MiB at **0x8c0000000** (not 0x880000000, which is firmware-reserved). Single source of truth: `DRAM_BASE` in `tools/mkadt_star2lte.py` (mkpayload reads it from the ADT). The loader additionally refuses any payload overlapping `0x880000000-0x8a1c00000`. Loader log/DMA at `0x8f0000000+` and the marker at `0x8f013f000` stay above the window end (`0x8e0000000`).
- Boot MPIDR is a runtime value from the ADT, not a kernel constant, so a wrong guess costs a re-pack, not a rebuild.
- First trial is UFS + log + XNU jump only: SMP (`cpus=1`), touch, battery, keys, DECON frame-wait all off.

## Known risks / unverified
- Turn-4 loader edit (new constants + overlap check) and the new RAM base are **uncompiled and untested**; the 512 MiB window at `0x8c0000000` is assumed fully free (the decoded list shows no other region in the high bank; names unmatched).
- BOOT partition is only 55 MiB: kernel Mach-O size is unknown until the CI build finishes (check `ls -l out.img`).
- `make-boot.sh` needs clang+lld+llvm (or an aarch64 GCC) on the user's PC; not yet installed/tested there.
- Loader never ran. LDRLOG WRITE path could mis-target an LBA (computed from the GPT USERDATA last LBA).
- 0125 anchors verified against 0124's added text only, not the real tree. Kernel not built. Header `A5_BOOT_MPIDR` expands to a call on `ml_get_topology_info()`: expected to compile only inside SweetCPU.cpp (the sole user).
- S-Boot EL/MMU/x0 handoff and 16K-vs-4K granule assumed from the S8.
- `export-0125.sh` tested on a pseudo-tree, not a real git tree.

## Change log by turn
**Before this chat (from the zip, not re-verified)**: S9+ fork skeleton, loader fork with LDRLOG, ADT generator, make-boot.sh, TWRP fact collector, measured hardware facts, S8-probe compile-out.

**Turn 1 ("continue the progress")**
- Added: `tools/star2lte/apply-star2lte.py` (patch 0125 as an asserted-edit script), `tools/star2lte/verify-apply.py`.
- Changed in the xnu tree it edits: ramoops klog, S6SY761/MAX77865 driver, Mongoose PMU CPU_ON path and DECON frame-done wait are guarded out under `STAR2LTE`; `dreamlte_battery_read` stub added; entry marker `0x920ff000` -> `0x8f013f000`; boot MPIDR taken from the ADT; logical CPU order follows boot cluster; keys default off.
- Changed in this file: Status item for 0125 ticked; "Next" step 3 and "Needs" step 2 reworded.
- Removed: nothing.

**Turn 2 ("guide me ... handoff")**
- Added: `tools/star2lte/export-0125.sh` (turns the script into `0125-star2lte.patch`, re-checks it with `git apply --check`; tested on a pseudo-tree only), this HANDOFF section, the step list, and this log.
- Changed: the earlier note that suggested wiring the script into the workflow is replaced by the export-then-commit procedure (workflow has no hook between patching and compiling).
- Removed: nothing.

Fork of the S8 (dreamlte) port. Branch plan: `s9plus-star2lte`. Observations
and plans are kept apart. **Nothing below is measured on a phone yet.**

## Status
- [x] Fork skeleton from ios-galaxy-s8 (donor code under `shim/dreamlte`, `tools/dreamlte` untouched)
- [x] `tools/star2lte/collect-hw-facts.sh` (read-only TWRP fact collector)
- [x] `docs/star2lte-s8-constants.txt`: every S8 address/constant to re-check (auto-generated)
- [x] Hardware facts measured on the S9+ (see below); framebuffer and boot CPU still open
- [x] `shim/star2lte` loader fork with UFS-ring logging. **Cross-compiles clean** (clang + lld, `-Wall -Wextra -Werror`, no absolute relocations, 66 KB Image; `build.sh` now falls back to clang when no GCC cross toolchain exists). Never run on a phone.
- [x] Loader safety (2026-11-04): the S8-address probes (DECON trigger `0x12860070`, SPEEDY PMIC, touch, display, Mongoose PMU) are compiled out unless `EXTRA_CFLAGS=-DSTAR2LTE_S8_PROBES`; the first trial only does UFS, log flush and the XNU jump. Consequence: the screen may stay blank until the S9+ DECON trigger is derived; rely on LDRLOG. The banner now prints MPIDR_EL1.
- [x] `tools/mkadt_star2lte.py` (built and inspected offline: GICD/GICC, 8 CPUs, `--boot-mpidr` picks the boot cluster; default 0x0 is a guess) and `tools/star2lte/make-boot.sh` (syntax-checked only; needs a kernel Mach-O, a stock sda10 backup and the `dreamlte_mkboot.py` path, not exercised)
- [x] `tools/star2lte/apply-star2lte.py` (patch 0125, 2026-11-04): turns off every S8-only hardware touch in the post-0124 tree (ramoops klog 0x92180000, S6SY761/MAX77865 I2C, Mongoose PMU CPU_ON path, DECON `0x12860000` frame-done wait), moves the entry marker to loader RAM `0x8f013f000`, takes the boot MPIDR from the ADT, orders logical CPUs boot-cluster-first, defaults keys off. `tools/star2lte/verify-apply.py` runs it on a pseudo-tree rebuilt from patch 0124: all anchors match and the header macros resolve. **Not run on the real tree, not built.** The ADT keeps the names patch 0124 matches (`samsung,a5xelte*`, `/dreamlte-ufs`, `a5xelte-fbcon`)
- [x] Patch 0125 generated on the real post-0124 tree by the user (anchors verified; kernel not built)
- [x] RAM window moved off the firmware-reserved block (turn 4; uncompiled)
- [ ] First BOOT trial

## Hardware facts measured on the S9+ (2026-11-04, TWRP, bootloader G965FXXUHFVG4)
Source: `docs/star2lte-facts/` (cpuinfo, iomem, partitions, cmdline) and the live DT dump (kept local, 400 KB).
Board DT: "Samsung Star2 rev26", EXYNOS9810.

- **Interrupt controller: GICv2 (GIC-400), not GICv3** (earlier guess was wrong). `arm,cortex-a15-gic`:
  GICD `0x10101000`, GICC `0x10102000` (the `gicd/gicc` at 0x17cf1000 in iomem is the audio abox_gic).
- **Timer**: `arm,armv8-timer`, 26 MHz (0x18cba80), `use-physical-timer`, PPIs 13/14/11/10, so physical timer PPI 14 = INTID 30, same as S8.
- **CPUs**: cpu0-3 = Cortex-A55 (part 0xd05), **MPIDR 0x0-0x3**; cpu4-7 = Samsung Exynos M3 (impl 0x53, part 0x002), **MPIDR 0x100-0x103**. S8 had its boot cluster at 0x100; the S-Boot boot CPU here is **unknown** (TWRP boots on cpu0 = 0x0, but that may be Linux, not S-Boot). Needs a probe.
- **PSCI**: method `smc`, cpu_on `0xc4000003`, cpu_off `0x84000002`. Kernel 4.4 /proc/cpuinfo has no `atomics` string, so LSE on the A55 is unverified (A55 is ARMv8.2); keep the LSE scan.
- **RAM**: DT banks `80000000+0x3c800000`, `c0000000+0x20000000`, `e1900000+0x1e700000`, `0x880000000+2 GiB`, `0x900000000+2 GiB`. High bank `0x880000000-0x97fffffff` = **4 GiB contiguous** (6 GiB total, cmdline dram_info 6G). S8 bank was 2 GiB.
- **Partitions**: BOOT `sda10`, RECOVERY `sda11`, DTBO `sda9`, EFS `sda3`, CPEFS `sdd1`, PERSISTENT `sda14`, SYSTEM `sda18`, CACHE `sda21`, **USERDATA `sda25`**. (S8 was sda7 / sda24: do not reuse.)
- **UFS**: HCI `0x11120000` (the S8 loader probe uses HCI `0x11120000`, VS `0x11121100`, protector `0x11130000`: **identical map**, so the S8 UFS code is expected to carry over), UFS PHY `0x11124000`, io-coherency `0x11010700`, UFS FMP present (file-based encryption crypto engine).
- **Display**: DECON_F `0x16030000` (command mode, HW trigger, 1440x2960), DECON_T `0x16050000`, DSIM `0x16080000`, DPP `0x16021000-0x16026000` (+ `0x16071000...`), SYSMMUs `0x160a0000/160b0000/160c0000`. S8 used DECON `0x12860000`; trigger register offset and the unmask value must be re-derived. **S-Boot framebuffer: `s3cfb.bootloaderfb=0xcc000000`** (user-reported from Android cmdline; same address as the S8), 1440x2960.
- **Touch**: Samsung `sec,sec_ts` at I2C addr `0x48` on `hsi2c@104B0000`, IRQ gpio `<0x6c 0 0>`, rails `tsp_io` / `tsp_avdd`. (S8 was an S6SY761; the driver is not reusable as is.)
- **PMIC**: `s2mps18mfd` + `s2mpb03`, reached through **ACPM IPC (channel 2)**, plus `speedy@141C0000`. S8 drove the S2MPS17 directly over SPEEDY from the loader; here the PMIC is behind the ACPM firmware, so powering the touch rails is a much bigger problem (unsolved).
- **Keys** (gpio-keys, pinctrl phandles unresolved yet): power, vol up (code 0x73), vol down (0x72), Bixby (0x2bf).
- **RTC**: `samsung,exynos8-rtc` at `0x141E0000`.
- **ramoops**: **not configured in this TWRP** (`mem_address=0, mem_size=0`, `/sys/fs/pstore` empty). The S8 logging path (pmsg at 0x92180000) does not exist here. Samsung's debug-snapshot region `log_pstore` at `0xfed10000` (32 KiB) is a candidate, unverified.

## Measured 2026-11-04 (user uploads, turn 4)
- **Partition sizes**: sda9 DTBO 8 MiB; **sda10 BOOT 57,671,680 B (55 MiB)**; sda11 RECOVERY 65 MiB; **sda25 USERDATA 50,925,645,824 B (~47.4 GiB)**. The BOOT image (kernel + ADT + loader) must fit 55 MiB.
- **ramoops**: module params `mem_address=0, mem_size=0` (the 4096s are defaults), `/sys/fs/pstore` empty -> not configured; confirms the on-disk-ring decision.
- **`dmesg-fb-debug.txt` was empty**: the framebuffer address `0xcc000000` is still only user-reported (see turn-4 step B for a cmdline/iomem cross-check).
- **Firmware-reserved regions** (decoded from `/proc/device-tree/reserved-memory/*/reg`, 12 entries, cells = hi, lo, size; names NOT matched yet, step B fixes that):
  `0x0fb200000+40MiB`, **`0x880000000+540MiB` (to 0x8a1c00000)**, `0x0f9200000+32MiB`, `0x0fda00000+~28MiB`, `0x0ff800000+8MiB`, `0x0f0000000+146MiB`, `0x0af800000+32MiB` (rkp_region), `0x080000000+4KiB`, `0x0c0000000+512KiB`, `0x0e1900000+30MiB`, `0x0b8000000+2MiB` (tima_region), `0x091300000+4KiB`.
  **Consequence**: the old XNU window `0x880000000+512 MiB` lay entirely inside the 540 MiB firmware block; the loader zeroes the window, which could fault or break firmware. Moved to **`0x8c0000000`** (see decisions). Low-bank reserved blocks also matter later for the ramdisk position (`0x080000000-0x0bc800000` contains rkp/tima/others).

## Assumptions still to verify
- S-Boot hands over at EL1 with MMU off and x0 = DTB (S8 behaviour; unchecked).
- 16 KiB granule: ID_AA64MMFR0 not readable from here; M3 and A55 both likely 4 KiB only.
- GPIO/alive pinctrl base for the keys, the S-Boot framebuffer address, whether ACPM can be driven from the loader.

## Logging decision (2026-11-04): on-disk ring, no ramoops
Two areas at the end of USERDATA (`sda25`), both clear of the 16 GB iOS root image:
- **Kernel ring**: last 1025 blocks, "SWEETLOG", written by the XNU UFS driver (patch 0047 path, flushed every `ufslogsecs`). Decoder `tools/sweet-log.py`. Needs the XNU UFS driver running on the S9+ (not yet ported/tested).
- **Loader log** (new): 64 blocks directly below it, "LDRLOG". The loader keeps text in RAM at `0x8f0100000` and writes it with a new UFS WRITE(10) path (`ufs_log_write` in `shim/star2lte/ufs_probe.c`) after the UFS probe and just before the XNU jump. Decoder `tools/star2lte/ldrlog.py` (tested on synthetic data only).
- Pull both from TWRP with `tools\star2lte\pull-log.ps1 NAME`.
- Limits: the loader log is flushed at two points, so a hang between them leaves only the earlier flush (the screen still shows live text). A bug in the new WRITE path could fail silently or, worst case, write to the wrong LBA; the target is computed from the GPT USERDATA last LBA (`ud_last + 1 - 1025 - 64`). Check the first flash on a spare/backed-up userdata.
- Dropped for now: the XNU entry marker (needed pstore) and patch 0124's `A5_KLOG_PHYS`/`A5_ENTRY_MARKER_PHYS` (0x92xxxxxx), which must be replaced in patch 0125.

## Next
1. ~~Build the loader~~ done (see Status).
2. First BOOT trial to `sda10` (backup `sda10` first): expect the screen text, then LDRLOG in USERDATA. Report the loader's EL, MPIDR and probe output.
3. Port the display trigger (`DECON_F 0x16030000`; the S8's `0x12860070` offset is not valid) and the DECON frame-done wait; then touch/PMIC (ACPM), SMP and keys later (all left off by 0125).

## Needs the user's phone / GitHub (2026-11-04)
1. In TWRP, with adb working: `bash tools/star2lte/collect-hw-facts.sh star2lte-facts --boot-backup` (read-only; also copies `sda10` = STOCK_BOOT for make-boot.sh). Optional second pass with `--mmio` (reads DECON_F/DSIM/UFS windows; opt-in because a read of a gated block could hang TWRP). `docs/star2lte-facts/` was empty in the handoff zip.
2. Patch 0125 must exist as a real `xnu/patches/0125-star2lte.patch` for CI, because `build.sh` applies `git apply` patches itself and the workflow has no step between patching and compiling. Produce it where an XNU tree exists: prep the tree (`tools/dreamlte/prep-xnu-tree.sh`, which applies 0001-0124), run `python3 tools/star2lte/apply-star2lte.py XNU_TREE`, then export the diff the way `tools/dreamlte/export-patches.sh` does and commit it. Any anchor miss aborts with the file and text. The kernel Mach-O then comes from the normal `xnu` CI run (`MACHINE_CONFIG=A5XELTE`).
3. First BOOT trial only after (1), with the stock `sda10` backup stored safely: `tools/star2lte/make-boot.sh KERNEL boot-sda10.img out.img`, flash to `sda10` from TWRP, then `tools\star2lte\pull-log.ps1 v1` and send the loader log (EL, SCTLR, MPIDR, UFS probe).

**Turn 3 (user ran steps 1 and prep; hit "export-0125.sh: No such file")**
- Cause: the user's folder is the original zip, so turn 1-2 files were missing. Fixed by new step 0 (unzip over the folder).
- Added: "About the user" (beginner, fish on Arch, `~/Downloads/ios-galaxy-s9plus`), "Done by the user so far", `.gitignore` entries (`star2lte-facts/`, `WORK/`, `*.img`, `out.img`).
- Changed: the step list is rewritten for fish/Arch with full commands and expected output; step 7 now uses adb + `ldrlog.py` directly (the PowerShell script is Windows-only); step 4 spells out GitHub setup and that a push to `main` auto-starts the build (no manual run).
- Removed: the `pull-log.ps1` instruction and the "commit" wording that assumed an existing git repo.
- Not verified: the fish-specific commands were not run in fish; `gh`/GitHub steps not run; no check yet that the workflow succeeds in a fresh repo.

**Turn 4 (user ran export-0125 successfully and uploaded part-sizes / reserved-memory / dmesg-fb-debug / pstore)**
- Found: a 540 MiB firmware-reserved block at `0x880000000` contains the whole planned XNU window (decoded the DT cells; see "Measured ... turn 4"). Also: BOOT is 55 MiB, ramoops confirmed absent, the dmesg grep for the framebuffer was empty.
- Changed: `tools/mkadt_star2lte.py` (`DRAM_BASE` 0x880000000 -> 0x8c0000000, docstring); `shim/star2lte/loader.c` (comment, `FW_RSVD_BASE/END`, refuse payloads overlapping the reserved block); `.gitignore` (CRLF line endings stripped so `logs/` and `shim/dreamlte/out/` rules work).
- Added: the facts subsection, the decision and risk entries, status lines, and new steps A-G (re-unzip, facts checks, GitHub build explained for a git newcomer, build tools `clang lld llvm`, BOOT size check).
- Removed: the old numbered step list (replaced by A-G) and the "Done: step 3 pending" wording.
- Verified: ADT still generates with the new base. NOT verified: loader compile (no clang in the assistant sandbox), the kernel build, any phone behaviour. Region names unknown until step B output.

**Turn 5 (user pushed to GitHub; "no runs found"; asked to rename the project "frankenstnine")**
- Observed: repo `georgev-6974/s9plus-ios` created and pushed OK (266 objects, 646 KiB, branch `main`). No workflow run started automatically, so my earlier "the push starts it by itself" was wrong for this first push.
- Changed: step C now starts the workflow manually (`gh workflow run xnu.yml ...`) after checking `gh workflow list`; README and notes titles use the name frankenstnine (code/file/dir names unchanged); project-name and GitHub info added at the top of these notes.
- Added: repo rename instructions (given in chat; user runs them).
- Removed: the "do not start it by hand" advice.
- Not verified: that the manual run succeeds; the repo rename.

**Turn 6 (first CI run failed; user pasted the log)**
- Observed: both runs (push 41908009114, manual 41908635689) go through checkout, Xcode/KDK setup, libpthread staging, then `0020-stage-bearssl.sh` fails: `fatal: unable to access https://www.bearssl.org/git/BearSSL/ ... 502`. The "Package build tree" step errors afterwards are only follow-ups (no build tree exists). No XNU source of ours was compiled yet, so 0125 is still not build-tested.
- Changed: `xnu/patches/0020-stage-bearssl.sh` (3 attempts with 15/30/45 s waits; sources: bearssl.org, github.com/nickray/bearssl, github.com/tarigo/BearSSL; exact-commit check unchanged), `0019-stage-libpthread.sh` and `0026-stage-hfs.sh` (3 attempts each, same URL).
- Corrected: turn 5's claim that the push did not start a run; step C text updated; added the `git add/commit/push` update procedure and `gh run rerun --failed`.
- Added: nothing else. Removed: the "start it by hand" advice as the default.
- Verified: bash syntax of all three scripts; retry/fallback loop simulated with a fake `git` (falls through the three URLs). NOT verified: that either GitHub mirror actually contains commit 7bea48e5 (if neither does and bearssl.org stays down the run fails with "could not fetch BearSSL"); the real CI run.

