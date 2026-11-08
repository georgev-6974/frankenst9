# frankenstnine - Galaxy S9+ (SM-G965F, star2lte, Exynos 9810) port - progress


# LATEST 3 (2026-11-08 night, session 4; read this first, it supersedes LATEST 2 where they differ)

**Source:** session 3 left no handoff; this section is rebuilt from the user's chat with that agent. I re-measured nothing. Labels: measured = log/grep output the user pasted; user-reported; guess. Build / kernel marker / screen / iOS runtime stay separate claims.

**Boots in the chat (two different logs, do not mix them):**
- Boot A: `s9go out-0162 8 a5fb_keep_on=1 sweetscan=backboardd,SpringBoard,PosterBoard` (version number not stated; an older paste was v41). Line numbers: `exec backboardd` n/a, `display-off request ignored (a5fb_keep_on)` 1698 and 2288, `exec PosterBoard` 1735 and 2558, `exec Setup` 1855, `SMP SpringBoard t0` samples 2222/2398/2672. CRASH line: `PosterBoard[204] sig 5 code 0x600000001 sub 0x1e1e30268 slide 0x206b8000`.
- Boot B (probably v43, the user's example for the variable): `exec backboardd` 634, `CRASH PosterBoard[204] ... sub 0x1fabec268 slide 0x39474000` 1735, `exec Setup` 1843. Extra args NOT stated (the agent asked; unanswered). This is the boot of the "freeze" screenshot.
- Whether these ran the 0162 kernel is implied by `s9go out-0162` for A only. **FBTIME numbers were never reported**: run `grep -a FBTIME $L` on the stored log first.

**Findings**
1. a5fb_keep_on test (was NEXT item 2): the user reached the Setup language list (screenshot, user-reported), so the screen did NOT go black after the swipe. Guess (supports hypothesis (a) of LATEST 2): the black screen came from the display-off fade destroying fPixels with no new swap after display-on. Args of the screenshot boot unconfirmed.
2. Then "frozen" on the language list (user-reported): the language icon looked too small, as if an animation stopped midway; power button did nothing. NOT proven frozen (no wait time reported). Guess: the power button does nothing BECAUSE keep_on ignores display-off, so it is no freeze evidence.
3. PosterBoard (measured): SIGTRAP in both boots, BEFORE `exec Setup` (B: 1735 < 1843), so it is not the cause of any Setup freeze. Heap scan (STR, boot A) has no assert text, only `Poster Extension Assertions:` and listener names `com.apple.posterboardservices.active-wallpaper-observer` / `...dataModel`. The prior agent named the crash site `_stateLock_setupSwitcherConfigurationForFirstTime` (source of that name not in the chat; treat as unverified). Cause still open; `ipsw` still missing for symbolizing (pcs in LATEST 2).
4. Boot A order (measured): first ignored display-off (1698) is BEFORE `exec Setup` (1855), so the first display-off is part of startup, not an idle timeout after Hello (idle-timer theory weakened for the first off; the second, 2288, is ambiguous). `exec PosterBoard` appears twice with one CRASH line (guess: launchd restarted it).
5. Prior agent said Setup was already idle at its first sample (~125 s after boot); this conflicts with the user reaching the language list, so treat it as unreliable.
6. SpringBoard t0 samples (boot A, raw): pri 47, mode 2, `last_run_ago` 77987 / 30168569 / 30277764 at now 3236713778 / 6356835852 / 9476950910 (units unverified, no conclusion drawn).

**v45 (2026-11-08 night; boot args as in boot A plus `sweethidtest=20`, no sweetscan; kernel 0162; measured from the pasted log):**
- FBTIME: copy 3.7-5.6 ms per full swap (n 1-250, 1440x2960, ~two values 3.8 / 5.4 ms). At the default 10 Hz cap (100 ms) the copy is ~5%: **the copy is NOT the speed bottleneck; do not optimize it.** The slowness is iOS's CPU rendering.
- Fake Home presses work: `SWEET HID: key 0x40 down/up` every 20 s, each followed by 4x `SWEET AKS: SpringBoard sel 17`. Last SMP dump: SpringBoard threads waiting normally (t3/t4/t6 same pc 0x1fba85030), no crash. What the screen showed in v45 was NOT reported.
- `sweethidtest` exists (donor NOTES.md line 31: fake Home press every N s; on the S8 it advanced Hello to the language list).
- **Likely explanation of the "freeze" (guess, strong):** the language list is static and waits for a TAP. The S9+ has NO touch driver (`a5touchprobe=0`; touch is Samsung sec_ts at I2C 0x48 on hsi2c@104B0000, rails behind ACPM; S8 driver not reusable). Fake Home cannot choose a language. So the language list is probably not a freeze. The small icon the user saw is unexplained.
- Fade code seen (SweetFramebuffer.cpp 250-275, vsync handler): `fPowerOff` set -> each vsync halves every channel of `fPixels` in place for 6 steps, then writes 0 (step 6); keeps going idle. Nothing restores fPixels. Fix needs the display on/off handler and the `fPowerOff/fFadeStep` set/clear sites: run `grep -n 'fPowerOff\|fFadeStep\|fPixels' iokit/Kernel/arm/SweetFramebuffer.cpp` in WORK3/xnu. Not urgent: keep_on already works.
- **Plan:** skip Setup so the boot ends at SpringBoard: `tools/star2lte/skip-setup.sh` (UNTESTED; sets SetupDone + SetupFinishedAllSteps in `/private/var/mobile/Library/Preferences/com.apple.purplebuddy.plist` of the image file, fsck -y before/after). Needs a root write to sda25 = destructive, ask for yes. Then fake Home (sweethidtest) should unlock to the home screen; real interaction needs a touch driver (big: sec_ts + ACPM rails).

**s9delta v2 (2026-11-08, reviewed, not run):** `s9delta -n` = dry run (list differing chunks, no write); after the write `sync; echo 3 > /proc/sys/vm/drop_caches; sleep 3` before the re-check (otherwise the read-back can come from the page cache). Safe for updating the phone to the image (rewrites differing 64 MiB chunks from the image; log ring at the end of sda25 is outside the image range). Still not a verifier after a boot. Plan: `s9delta -n` first, then `s9delta` after skip-setup.sh instead of the full s9root.

**s9delta v3 (2026-11-08):** progress screen (clears the terminal): 0-50% compare, 50-100% write (first half) + re-check (second half), live count and % of checked chunks differing; helper `__s9delta_draw` lives in the same file. UNTESTED (no fish in sandbox). First dry run after skip-setup.sh (user-reported): 39 of 256 differ: 0 11 13 69 107 186-190 192-208 even 210-226 even 248 250 252 254 255.

**Gotcha (2026-11-08, hit again):** after `mv`-ing a new fish function file, the shell still runs the OLD definition in memory; `funcsave NAME` then OVERWRITES the new file with the old one. After a mv always `source ~/.config/fish/functions/NAME.fish`, never funcsave. User did this to s9delta v3 (lost; re-copy from outputs). Also (user-reported, v2 run): a compare after the write showed chunks 0-15 all matching (no DIFFERS for 0, 11, 13), so the earlier chunk write appears to have worked; the final VERIFIED line was not shown to me.

**s9delta write bug (2026-11-08, measured by the user with cmp on chunk 186):** image stable (3 identical hashes, nothing mounted, fsck changed nothing), phone reads stable, but chunk 186 differs from the image in 1,769,728 bytes starting at byte offset 65273856 (62.25 MiB, 4 KiB aligned) = the last ~1.75 MiB of the 64 MiB chunk; phone holds text ("tivit..."), image zeros. Guess (strong): `adb exec-in` drops the tail of each chunk stream; chunk 255 (alternate volume header at the image end) fits. Chunks 0/11/13/69 were fixed because their differences sit earlier in the chunk. Fix = s9delta v4: `adb push` to phone /tmp, sha256 check there, then local dd + conv=fsync. UNTESTED. Same flaw may affect s9root (its read-back hash matched on the one test, so unclear).

**s9delta v4 result (user-reported 2026-11-08):** with the adb push staging, the 13 stubborn chunks (186-188 197-202 204-206 255) were written and re-checked: "Done: written and verified". Root on sda25 now equals the image (after skip-setup.sh + fsck). **s9delta v5** (UNTESTED): PC hashes all chunks in parallel first (`xargs -P nproc`, /tmp/s9local.txt), phone hashes `S9DELTA_JOBS` (default 4) chunks at a time via background jobs in one adb call; re-check uses the same path; prints "compare took N s".

**Why every root write makes the next boot slow (2026-11-08, user-reported + guess):** after s9root/s9delta the first boot takes 15+ min (progress bar), later boots ~1 min. Guess (strong): iOS first-boot work (caches, databases, migrations) is stored in /var inside the root image (rootrw=1); writing the image back resets it. s9delta only rewrites chunks that differ, but those are exactly the chunks iOS changed, so phone == image again = caches lost. Fix = never overwrite iOS-written chunks: **s9delta v6 `-p` (pull mode, UNTESTED)** copies the differing chunks phone -> image file (via dd to phone /tmp, adb pull, hash check, dd conv=notrunc into the image, re-hash), so the image mirrors the live state. Workflow: boot once (slow), TWRP, `s9delta -p` (yes), `sudo fsck.hfsplus -f -y IMAGE`, run the edit script (skip-setup.sh, disable-daemons.sh ...), then `s9delta` pushes only the edit's chunks. Risks: the image is no longer pristine (rebuild with tools/mkiosroot.sh if needed); HFS+ may be dirty after a forced power-off (fsck -y fixes); an edit that conflicts with cached state is untested.

**Boot after skip-setup.sh + s9delta v4 write (user-reported + measured, 2026-11-08; args `a5fb_keep_on=1 sweethidtest=20`, kernel 0162):** screen showed ~5 languages in the "Hello" animation, then stopped (user-reported). Log (measured): exec SpringBoard 763, driverkitd crash 921, assetsd crash 3502, PosterBoard crash 4111 (pc 0x1f0b74268, SIGTRAP), **exec Setup 4174**, last FBTIME n 16250 (copy 3.6-5.3 ms). So Setup STILL launched: the SetupDone/SetupFinishedAllSteps keys written by skip-setup.sh did not stop it (cause unknown: keys insufficient, file reset, or wrong path; not checked on the phone). Unknown: was it the slow first boot after the write, how long was waited. Next checks: (1) count swaps after exec Setup (`grep -a -n 'FBTIME\|exec Setup' $L`): many swaps = iOS still presenting, so probably slow, not hung; (2) `s9delta -p`, then read com.apple.purplebuddy.plist from the image (command in chat).

**purplebuddy.plist read back after the boot (user-reported via s9delta -p + mount, 2026-11-08):** `SetupDone` True, `SetupFinishedAllSteps` True (our keys survived), plus keys iOS added itself: `PaymentMiniBuddy4Ran` True, `HSA2UpgradeMiniBuddy3Ran` True, `setupMigratorVersion` 12, `chronicle`, `lastPrepareLaunchSentinel` = 1970-01-01 00:17:46 (system clock is 1970: RTC not set on the S9+; the stamp is ~17.8 min of uptime). Conclusion: iOS READS the file, yet Setup still launches and shows Hello. So the keys are NOT sufficient (or Setup is started for another reason, e.g. a mini-buddy flow; unproven). Next experiment: boot with `sweetscan=Setup,SpringBoard` added and grep the STR lines for buddy/flow class names. Do not delete Setup.app blindly (SpringBoard may loop on the failed launch); reversible via s9delta if tried.

**MILESTONE v47 (user-reported photo + log, 2026-11-08; args `a5fb_keep_on=1 sweethidtest=20 sweetscan=Setup,SpringBoard`, kernel 0162):** the screen now shows the post-update mini-buddy **"Software Update Complete - Your iPhone has been updated to iOS 16.7.16 ... [Continue] [Only Download Automatically]"** (status bar: clock 4:02, charging icon). This is beyond the language "Hello" flow, so SetupDone worked and Setup now runs a mini-buddy pane. It needs a TAP; the fake Home presses (sweethidtest, key 0x40) cannot press Continue; the S9+ has no touch driver. Earlier "Hello stops animating" was probably just slowness (guess; wait times were never recorded). Continue is at about (50%, 86%) of the screen width/height in the photo, "Only Download Automatically" about (50%, 92%) (estimated from a tilted photo). `sweetscan=Setup,SpringBoard` gave NO matching STR lines for buddy/setupdone/welcome/flow/hello (the grep printed nothing). Options: (a) find the plist key that marks this mini-buddy done by `strings` on Setup.app (and the dyld shared cache if needed), write it with skip-setup.sh; (b) tap injector: a boot-arg that calls the existing C hook `sweet_hid_touch(finger, down, x, y)` (donor NOTES.md line 31) at given coordinates; need the SweetHID.cpp touch code and the coordinate range first (do not write blind); (c) real sec_ts touch driver (big, ACPM rails).

**Setup.app strings (user-reported 2026-11-08):** only two "...Ran" keys exist: `PaymentMiniBuddy4Ran`, `HSA2UpgradeMiniBuddy3Ran` (both already True in the plist). Functions: `_BYBuddyRun{Diagnostics,HSA2,KeychainSync,Mesa,Payment,Standard}MiniBuddy`, `_inMiniBuddyFromBreadcrumb`, `checkMiniBuddyBreadcrumbs`. So the "Software Update Complete" pane has no obvious Ran key (guess: Standard mini-buddy gated by a version compare or breadcrumb). Donor lead (NOTES.md line 28, S8 Codex report `codex/setup/report.md`, unverified here): skip Setup = `SetupDone`, `SetupFinishedAllSteps`, **`SetupVersion`=11** in com.apple.purplebuddy.plist + activation check. skip-setup.sh now also sets `SetupVersion`=11 (int). Donor image v13 also removed CommCenter jobs from launchd.plist and set `BKNoWatchdogs`=true + `FBLaunchWatchdogExceptions{com.apple.purplebuddy:100}` in com.apple.springboard.plist because Setup was killed by the scene-create watchdog while blocked in CoreTelephony -> CommCenter: possible cause of Setup stalls here too (untested on S9+). Touch plumbing seen by git grep: `sweet_hid_touch(int finger, int down, int x, int y)` defined in xnu/patches/0058-sweet-hid-event-services.patch (~line 21130), `sweethidtest` parsed there (~20973); S8 touch driver `tools/dreamlte/dreamlte_touch.c`, A5 version in A5XELTE_PROGRESS.md (patch 0123): donor only. ORDER RULE: after any boot run `s9delta -p` BEFORE editing the image, otherwise `s9delta` pushes stale chunks over iOS's new writes (mixed old/new HFS+ metadata = corruption risk).

**MILESTONE: iOS HOME SCREEN (user-reported photo IMG_20261108_153448, 2026-11-08):** after `s9delta -p`, skip-setup.sh with `SetupVersion`=11 added, `s9delta`, boot (args presumably unchanged: `a5fb_keep_on=1 sweethidtest=20`): home screen with two "Waiting..." widgets, Photos / App Store / Settings, dock Phone / Safari / Messages (red badge), clock 4:01 changing (phone alive), charging icon. Likely cause of skipping the mini-buddy: SetupVersion=11 (guess; keys not tested one by one). NOW: touch is the blocker. No tap works; sweethidtest only presses Home.

**TOUCH TASK (next):** S9+ touch = Samsung `sec_ts` at I2C 0x48 on `hsi2c@104B0000`, IRQ gpio `<0x6c 0 0>`, rails `tsp_io`/`tsp_avdd` behind the PMIC (`s2mps18mfd` + `s2mpb03`) reached through ACPM IPC channel 2 / `speedy@141C0000` (hardware facts section, ~lines 350-351 of the old part of this file). Donor code (not reusable as is): `tools/dreamlte/dreamlte_touch.c` (S6SY761 polled, calls `sweet_hid_touch`), patches 0060/0062 (other devices), 0123 (A5XELTE ZT7538, see A5XELTE_PROGRESS.md). HID entry: `sweet_hid_touch(int finger, int down, int x, int y)` in 0058 (SweetHIDTouch); coordinate range NOT checked. Plan: (1) tap injector boot-arg (`sweettap=x,y,secs`) to prove HID -> iOS on the S9+ and to pass screens; (2) survey: are the tsp rails already on after S-Boot (probe I2C 0x48 first); (3) power rails via ACPM if needed; (4) polled sec_ts driver.

**Open request, now done:** `s9pull.fish` (repo copy: `tools/star2lte/s9pull.fish`; install: `mv ~/Downloads/s9pull.fish ~/.config/fish/functions/`). `s9pull` runs `bash tools/star2lte/s9.sh pull`, then sets global `$N` (number) and `$L` (log path of the newest `logs/sweetlog-*.txt`). Use `grep -a FBTIME $L` etc. UNTESTED (no fish in the sandbox, not run on the phone); must run from the project folder; `s9.sh` itself was not changed.

**NEXT (in order)**
0. (v45 done: s9pull works, FBTIME read, sweethidtest run; see v45 block above; items 1-2 below are superseded by the v45 Plan.)
1. Install `s9pull`; `s9pull`; `grep -a FBTIME $L | head` (FBTIME from boot with 0162, never read).
2. Discriminator boot: `s9go out-0162 8 a5fb_keep_on=1 sweethidtest=20` (no sweetscan). `sweethidtest` is the prior agent's name, NOT checked in the code: `git grep -n sweethidtest` first. Watch Hello/language list ~3 min, photo. Lettering animates or Setup moves on = input/idle related (check auto-lock in the image). Same freeze = missing wake-up of Setup's runloop (vsync/frame callbacks): read how vsync notifications are delivered.
3. Fade fix (patch 0163): `display off` fades into a copy, `display on` redraws the last swap, not just fDirty. Do NOT write it blind: need `sed -n 250,275p` and the keep_on code (~line 648) of SweetFramebuffer.cpp (paste output). Then remove keep_on from normal args.
4. PosterBoard/assetsd symbolization (install ipsw), CPU frequency measurement, remove diagnostics, more daemons: as in LATEST 2.

**User rules:** unchanged (tiny copy-paste answers, fish, `mv` from ~/Downloads, confirm destructive steps).


# LATEST 2 (2026-11-08 evening, session 3; read this first, it supersedes the LATEST below where they differ)

**Labels:** measured = seen in a log/output; user-reported; guess. Build / kernel marker / screen / iOS runtime stay separate claims.

**State (user-reported unless noted):** kernel 0161, cpus=8, root with disabled.plist boots to the Setup Assistant "Hello" screen in ~5 min (first boot after the root write was ~20 min). Once it froze while drawing "Hello" (v37: log ends in exec xpcproxy / nanotimekitcompaniond, no panic; touch did not react; power button NOT tried). Still slow (CPU-only rendering).

**Black screen after swipe (open):** Hello stayed visible until the swipe (user). v36 order (measured): assetsd crash (line 3147), `display off` 3685 (iOS), PosterBoard SIGTRAP 3715, `display on` 3795, `backboardd sel 79` 3796, user power press = `display off` 4216. All FBDIAG samples `nonblack 0/64`. Code (SweetFramebuffer.cpp ~257-270): `display off` fades `fPixels` in place to black; `display on` only sets fDirty, so the panel stays black until iOS sends a NEW swap. Hypotheses (unproven): (a) auto-lock fade destroyed fPixels and no new swap came; (b) PosterBoard dead. Untested cheap test: add boot-arg `a5fb_keep_on=1` (ignores display-off, code exists at ~line 648). If screen stays visible -> fix fade to not destroy fPixels (fade into a copy / redraw last swap on "on").

**Speed findings:** every swap copies the full 1440x2960 BGRA surface (~17 MB) row by row (SweetFramebuffer.cpp ~503); present is capped at 10 Hz by default (sweetfb_hz). CORRECTION: swap rects `a`/`b` were full-screen (0,0 1440x2960) in the first 32 swaps, so they are not shown to be damage rects; an earlier "dirty-rect" idea was wrong. Patch 0162 (`tools/star2lte/make-0162.py`, log `SWEET FBTIME: n N copy X us ...` first 5 then every 50th) is BUILT by CI (success, user-reported) but NOT booted. Next: `gh run download -n xnu-kernel -D xnu/out-0162`, `s9go out-0162 8`, pull log, `grep -a FBTIME`. Ideas only after that number: skip unchanged rows, higher hz. GPU (Mali-G72) stays unrealistic (no Metal/AGX path). Overclock NOT started: current CPU freq never measured; do measure (cycle counter vs 26 MHz timer) before touching PLL/PMIC; going above stock needs voltage and may cause crashes that mask other tests.

**Root image:** `tools/star2lte/disable-daemons.sh` v2 (fsck -y first, skips labels with no plist, last line fsck -y): disabled bluetoothd, fairplayd.H2, nanotimekitcompaniond, familycircled, carkitd, wcd. SKIPPED (no plist of that name): fmflocatord, UARPUpdaterService*. v38 log (measured): 0 execs of nanotimekitcompaniond/familycircled/carkitd/wcd, xpcproxy 175 (was 232) => the new image was active. `fsck.hfsplus -n` after `-y` always says "minor repair" (Linux fsck quirk, guess): ignore, use `-y` as the last check. Backups: `.bak`/`.bak2` were DELETED by the user (space); there is no undo copy; rebuild with tools/mkiosroot.sh if needed.

**Writing the root:** `s9root.fish` pipe test fixed (exec-in dd to /tmp/pipe.bin + `sync; sleep 3`, then hash; hash matched). The 2026-11-08 write was interrupted by an accidental reboot (VERIFIED never printed). `s9delta.fish` (NEW, UNTESTED write path; fish function, `s9delta [IMG]`) compares sda25 vs image in 64 MiB chunks (hash on phone) and rewrites only differing chunks after "yes". Ran after a boot: 28/256 differ: 0 11 107 186-218(even, 186-190 contiguous) 248-255 = iOS rw changes (rootrw=1). Do NOT write them back (would roll back HFS+ metadata). s9delta is only a valid verifier right after a write and BEFORE the first boot.

**CI:** runs from 42469127800 (0162) failed: KDK 13.5 "download" took 0.07 s, `hdiutil: image not recognized` (build.sh curls the Dortania manifest URL without --fail; guess: anonymous download got an HTTP error page). Fix (user-reported build success afterwards): workflow step "Install KDK (authenticated)" = `gh release download 22G74 --repo dortania/KdkSupportPkg --pattern '*.dmg'` with retries and size/imageinfo check, before Build (build.sh skips its download if KDK_13.5_22G74.kdk exists); also `[ -f "$lib" ] || continue` in the kdk-libs loop (the literal `lib*.members.txt` broke the artifact upload). Generator: `tools/star2lte/fix-ci-kdk.py` (idempotent).

**Not verified:** the 0162 compile result on the phone, a5fb_keep_on test, PosterBoard/assetsd crash cause (`ipsw` not installed; pcs PosterBoard 0x1ce370268, assetsd 0x1cf20f198), whether nanotimekit removal changed boot time, freeze cause of v37.

**NEXT (in order; superseded by LATEST 3):** 1) boot out-0162, collect FBTIME; 2) boot with `a5fb_keep_on=1`, swipe on Hello, photos at 5 and 15 min (separate boot so results stay readable); 3) if time allows: install ipsw, symbolize PosterBoard/assetsd; 4) measure CPU frequency; 5) remove diagnostics (S9AFF/S9PMU/S9ID/0151) once stable; 6) consider more daemons from the exec counts (only picks that SpringBoard/backboardd do not need).

**User rules (unchanged):** very small copy-paste answers, fish shell (no heredocs, quote globs), new files arrive from ~/Downloads via mv, confirm every destructive step (USERDATA write) first.

# LATEST (2026-11-08; merged from HANDOFF_M3; read this first, everything below is history and is partly superseded)

## START HERE: handoff to the next agent (end of session 2026-11-08)

**Goal:** a usable iOS 16.7 on the S9+ (star2lte): all 8 cores, lock screen, speed; later a real GPU driver (Mali, large project, hardware survey first). **User rules:** very small, exact copy-paste answers; shell is **fish** (no heredocs, quote globs, `ls` = eza); patches arrive as `tools/star2lte/make-NNNN.py` moved from `~/Downloads`; confirm every destructive step (USERDATA write) first; keep build / kernel marker / screen / iOS runtime as separate claims; say what is untested.

**State (user-reported unless "measured"):** kernel 0161, `cpus=8` boots to the Setup Assistant "Hello" screen in ~20 min (was ~50 min to a full bar). 8/8 cores alive (measured, v35). Console text and heartbeat no longer drawn (fixed by boot-arg `a5fb_noconsole=1`, the A5XELTE name, plus patch 0160). Respawn loop gone via `disabled.plist` in the root (measured in v36 log). Very slow and stuttering: expected, CPU-only rendering.

**OPEN PROBLEM (first thing to do):** after swiping up on "Hello" the screen is black; phone is alive (recovery combo did nothing until forced off), no panic, swaps keep counting (60000), log ends `SWEET FB: display off` after off/on/off and `backboardd sel 79`. Only crashes in v36: driverkitd (known), assetsd (abort), PosterBoard (SIGTRAP), none for SpringBoard/backboardd. Guess, unproven: display power state (our driver doesn't undo "display off") or just slow drawing. I had asked the user for: `git -C WORK3/xnu show HEAD:iokit/Kernel/arm/SweetFramebuffer.cpp | sed -n 8,34p`; `git -C WORK3/xnu grep -n 'RequestPowerChange\|display %s\|"display\|fDisplayOn\|fPowerState' -- iokit osfmk pexpert bsd`; `git -C WORK3/xnu grep -n 'sel 79\|case 79' -- iokit`. Not yet answered: did the user press power between swipe and log pull. Header comment (line 19): selector 12 `RequestPowerChange [state]`, 0 = display off. Do not write a patch before reading the handler. Phone tests: press power once, wait 30 s, photo (flashlight at the glass); swipe and wait 10-15 min, photos at 5 and 15 min.

**File map:** `xnu/patches/0160-star2lte-hb-mute.patch` (heartbeat stops once console muted, pexpert/arm/pe_fiq.c) | `0161-star2lte-fbdiag-limit.patch` (FBDIAG first 20 swaps then every 1000th) | `tools/star2lte/make-0160.py`, `make-0161.py` (generators; need a clean tree) | `tools/star2lte/disable-daemons.sh <img>` (adds `disabled.plist` for com.apple.bluetoothd and com.apple.fairplayd.H2 to the root image FILE on the PC) | `~/.config/fish/functions/s9go.fish` (kernel + BOOT image + flash; boot-args live here) | `s9root.fish` (fish function, `s9root [IMG]`: writes the root to sda25 via `adb exec-in` and verifies by read-back; written but NEVER RUN, check with `fish -n` first; install into `~/.config/fish/functions/`) | root image `/home/vsl/ios-build/ios16-root.img` (+ `.bak` = copy before the daemon edit) | `tools/mkiosroot.sh` (builds the root; runs `fsck.hfsplus -f -y` before `-n`).

**Decisions:** a5fb_noconsole, not sweetfb_noconsole, in the A5XELTE build (SweetFramebuffer.cpp ~392). Removed boot-args `-enable_kprintf_spam startup_debug=1 sweetsample=SpringBoard` (not separated from the other speedups). Did NOT remove diagnostics S9AFF/S9PMU/S9ID/0151 yet: S9ID is the only way to read the M3 ID registers. Daemon fix done in the image (launchd disabled db), not in the kernel.

**Known issues / risks:** the edited root write was never read back (checksum 867108dcb661ce16de9af0f9c69f8b6e87bd5ed04d566acc5a447264ee46bdc7 unverified on the phone). `disable-daemons.sh` should run `fsck.hfsplus -f -y` before its check (the first check said "Volume header needs minor repair"; user repaired by hand, reported healthy). `nanotimekitcompaniond` respawns (35 execs). M3 ID-register clamp (0159) is a guess. A 4-5 h overnight boot (v34) is unexplained. `ipsw` is not installed on the user's PC (needed to symbolize userland crash pcs: PosterBoard 0x1ce370268, assetsd 0x1cf20f198). Stale fish functions: after editing a function file run `source` on it and check the `boot-args:` line of the build output.

**Commands:** new patch: `git -C WORK3/xnu commit -am "0161"` (0161's edit is still uncommitted there), `python3 tools/star2lte/make-NNNN.py WORK3/xnu (pwd)/xnu/patches/NNNN-name.patch`, `cat` it, `git add ...; git commit; git push; sleep 2 && gh run watch` (CI artifact upload timeouts: `gh run rerun --failed`). Boot test: TWRP, `s9go out-NNNN 8` (add `fresh` to re-download), `yes` to flash. Logs: force TWRP (POWER+VOL DOWN, then POWER+BIXBY+VOL UP), `bash tools/star2lte/s9.sh pull`, then `grep -a ... logs/sweetlog-vNN.txt`. Last log: v36.


Labels: **measured** = seen on this phone; **user-reported** = user said so, no log; **claim** = from danstronics/ios-s9plus-exynos (`core/drivers/core/hakios.exynos_m3.c`, cites Samsung's exynos9810 kernel), not verified here; **guess** = hypothesis.

**Goal:** bring up all 8 cores (A55 cpu 0-3 done; Exynos M3 cpu 4-7 in progress), then lock screen and speed. **Current task: hide on-screen kernel logs and the heartbeat once the first display is shown (in progress, nothing written yet that is known).**

**User rules:** very small, precise answers: exactly what to copy-paste, back and forth. Shell is **fish** (no heredocs, quote or avoid `--include=*.c`, `ls` is an `eza` alias). New patch generators arrive as `tools/star2lte/make-NNNN.py`, moved from `~/Downloads` with one `mv` line. AGENTS.md rules apply (build / kernel marker / screen / iOS runtime are separate claims; no S8 address without a measurement; never edit shim/dreamlte, tools/dreamlte, DREAMLTE_PROGRESS.md, NOTES.md).

**Status**
- user-reported: kernel 0159 with 8 cpus requested reaches the Apple logo. NOT checked: per-core "came alive" lines for cpu 5-7, boot time vs cpus=4, lock screen.
- measured, cpu 4: `CPU_ON rc=0`, "came alive; SGI1 OK" after 0153 + 0155 (0156 was in the kernel).
- This supersedes the 2026-11-07 night note "`cpus=5` panics, use cpus=4": with 0153-0159 the M3 start works at least for cpu 4.

**Findings (M3)**
- PSCI AFFINITY_INFO (0xC4000004) answers -1 for every target (measured): core state cannot be polled.
- A55 MPIDR = 0x8100_0n00 (MT set, core in Aff1). **M3 core 0 = 0x80000100** (measured, third `D=` value; this also resolves the earlier "0x81000300 maybe stale" doubt: M3 is 0x80000100). Cores 1-3 = 0x101-0x103 (claim).
- PSCI target for cpu 4 is 0x100 (ADT 0x400 mapped by `SWEET_PSCI_TARGET`): works. Targets for cpu 5-7 = 0x101-0x103: not individually confirmed.
- M3 `CPU_ON` needs six PMU fields (PMU 0x14060000) written first (claim): `+0x1088[31:24]=0x8D`, `+0x2114/0x2180/0x21EC/0x2258/0x2384 [1:0]=2`. Measured: before = 0xc7150000 and 1,1,1,1,1; all six read back as written; afterwards firmware powers the cluster (`+0x2000 0->f`, `+0x2004`, `+0x2040`, `+0x2044`, `+0x2380 40000->1`).
- Reading the whole first 16 KiB of the PMU aborts (sync external abort, likely +0x1030). Only known offsets are read (0154).
- Core identification by raw MPIDR collides (M3 core 0 = 0x0100 vs A55 core 1). Fixed in `start.s` (0155) and `ml_get_cpu_number_local`/`ml_get_cluster_number_local` (0157) via MIDR implementer 0x53 -> `0x400 + (Aff0 << 8)`.
- With all cores up, xpcproxy died with SIGILL at one fixed shared-cache pc (0x1d473b588), launchd exited -> panic "initproc exited, namespace 2 subcode 0x4". **Guess:** commpage advertised A55-only features (LSE etc.). 0159 clamps ID regs; the Apple logo followed (consistent, not proven). The M3's real ID registers were never read: 0158 prints them with `kprintf`, which does NOT reach the log ring (photos only).

**Patches (xnu/patches, generator tools/star2lte/make-NNNN.py)**
0151 AFFINITY_INFO probe (useless, remove) | 0152/0154 PMU snapshot diff on cpu 1 and 4, safe-offset list (diagnostic) | 0153 six PMU writes before cpu 4 CPU_ON | 0155 start.s M3 MPIDR map | 0156 `a5xelte_send_ipi` non-fatal + `S9IPI` mask log | 0157 `sweet_norm_mpidr` | 0158 `S9ID` ID-register kprintf (diagnostic) | 0159 commpage ID clamp (ISAR0 &= 0x11120, ISAR1/PFR1/MMFR2 = 0, PFR0 without FP16/RAS/DIT). Earlier: 0149/0150 cluster/pset fixes (A55 cpus=4 works).

**Workflow / gotchas**
- Each make script needs a clean tree: `git -C WORK3/xnu commit -am "<previous number>"` first. WORK3/xnu is a detached HEAD; 0159's edit is still uncommitted there.
- Push -> `gh run watch` -> in TWRP `s9go out-NNNN CPUS fresh`. `s9go` reuses `xnu/out-NNNN` unless `fresh` (stale-kernel trap hit twice). Check: `grep -a -c '<marker string>' xnu/out-NNNN/xnu-kernel/kernel.development.a5xelte`.
- Logs: `bash tools/star2lte/s9.sh pull`. A panic screen needs an upright, sharp photo.
- Check `git status` for uncommitted local edits in `tools/mkadt_star2lte.py` (M3 `arm,cortex-a53` compatible, `cluster-id` 0 for all cores).

**RESULT 2026-11-08 (user-reported, kernel out-0159, no new patch):** console text over the progress bar was caused by the boot-arg name. In the A5XELTE build `AppleCLCD::present` reads `a5fb_noconsole`, not `sweetfb_noconsole` (SweetFramebuffer.cpp ~line 392), so `sweet_console_muted` (patch 0067) was never set. With `a5fb_noconsole=1` added to `s9go`, the flashing log lines under the bar are GONE. NOT yet checked: text after the bar fills (iOS stops swapping), the blue heartbeat box (patch 0126 draws straight into the framebuffer, ignores the mute; `make-0160.py` written to fix it, never built), boot time. Gotcha: an already-loaded fish function keeps the old text after the file is edited: run `source ~/.config/fish/functions/s9go.fish` and check the `boot-args:` line of the build output. Boot time with 8 cpus was ~50 min, same as 1 core (unexplained, cpu 5-7 alive unchecked).

**FINDINGS 2026-11-08 (later, user-reported unless "measured")**
- iOS root image (HFS+, built by `tools/mkiosroot.sh`, written to USERDATA sda25): `/home/vsl/ios-build/ios16-root.img` (path on the user's PC). `out.img` in the repo is the 17 MB BOOT image (sda10), NOT the root. Read-only mount: `sudo mount -t hfsplus -o loop,ro <img> /mnt/s9root`; rw needs `-o loop,rw,force`.
- measured, boot v35 (0160, cpus=8): `A5XELTE CPU: 8/8 CPUs initialized, SGI1 verified`, cpu 0-7 all "came alive; SGI1 OK" (cpu 4-7 mpidr 0x400-0x700 in ADT numbering). Bar appears 1m20s after boot, ~75% at ~10 min (same as before the log cuts). Heartbeat box gone after 0160 (user-reported).
- An overnight run (v34, 0160, same args) took 4-5 hours to reach a full bar; cause UNEXPLAINED (earlier runs ~50 min). Log ring wrapped (5.8 MB in 4 MiB). Process launches seen in v34: xpcproxy 4234, fairplayd.H2 1687, bluetoothd 1682, ~112 each for mobiletimerd, fitnesscoachingd, liveactivitiesd, routined, remotepairingdeviced.
- `SWEET FBDIAG` (SweetFramebuffer.cpp ~475/496) logs on EVERY swap (~1000/min, all frames black, `nonblack 0/64`): rate-limited by patch 0161 (`make-0161.py`: first 20, then every 1000th). Status: script written, not yet built or run.
- Boot args now (s9go, after removing -enable_kprintf_spam, startup_debug=1, sweetsample=SpringBoard and adding a5fb_noconsole=1): `debug=0xc serial=3 cpus=8 keepsyms=1 -noprogress wdt=-1 wdt_test=no_user_checkin a5touchprobe=0 rd=ufsroot0 ufsroot=USERDATA ufslogsecs=2 ufsrw=1 rootrw=1 unentitled_ios_sim_launch=1 ignition_level=1 launchd_unsecure_cache=1 sweetfb_native=1 sweetfb_noconsole=1 a5fb_noconsole=1`.
- Respawn loop daemons: `/System/Library/LaunchDaemons/com.apple.bluetoothd.plist` (KeepAlive SuccessfulExit=false, RunAtLoad) and `com.apple.fairplayd.H2.plist` (KeepAlive=true). The image has `/private/var/db/com.apple.xpc.launchd/config` only, no disabled.plist. `tools/star2lte/disable-daemons.sh <img>` writes a disabled.plist for both labels (untested; whether launchd honors it here is NOT verified; fallback: set `Disabled` true in the two plists). Flashing the edited root to USERDATA is destructive: needs the user's explicit yes (AGENTS.md).
- GPU: the user wants an attempt at a real GPU driver later (Mali, no AGX/Metal path). Start with a hardware survey; very large project.

**ROOT IMAGE WRITE (2026-11-08)**
- Image edit: `bash tools/star2lte/disable-daemons.sh /home/vsl/ios-build/ios16-root.img` (adds launchd `disabled.plist` for bluetoothd and fairplayd.H2). The first fsck right after the edit reported "Volume header needs minor repair"; the user then ran `fsck.hfsplus -f -y` and reported the image AND its backup `ios16-root.img.bak` healthy (user-reported, output not seen). Next time the script should run `fsck.hfsplus -f -y` before the check, as `mkiosroot.sh` does (not fixed yet).
- Image facts (measured by the user): size 17179869184 bytes (16 GiB, multiple of 4096), sha256 867108dcb661ce16de9af0f9c69f8b6e87bd5ed04d566acc5a447264ee46bdc7 (the edited image, before the first write). `sda25` = 50925645824 bytes, `by-name userdata` is sda25, TWRP has `dd`, `sha256sum`, `blockdev`.
- Write method: `adb exec-in` stream into `dd of=/dev/block/sda25`, then read back the same byte count and compare sha256. Packaged as the fish function `s9root` (`s9root.fish`, install to `~/.config/fish/functions/`; `s9root [IMAGE]`). UNTESTED as a function: the user approved the write on 2026-11-08 and ran the manual steps; the read-back result has NOT been reported yet.
- Patches since the handoff: 0160 (`hb_row` returns when `sweet_console_muted`; heartbeat box gone, user-reported), 0161 (FBDIAG logs first 20 swaps then every 1000th; CI build succeeded, boot result not yet reported). Generators `tools/star2lte/make-0160.py`, `make-0161.py`.

**MILESTONE 2026-11-08: iOS reaches the Setup Assistant "Hello" screen** (user-reported; kernel 0161 build, cpus=8, edited root with disabled.plist). Very slow and stuttering (CPU-only rendering). After swiping up the screen is BLACK; the phone is not off (recovery combo did nothing until the user forced it off) and no panic. Boot v36 log (measured): only three crashes in the whole log, each once: `driverkitd` (ns 1 code 7, known), `assetsd` (ns 2 code 6, abort, pc 0x1cf20f198), `PosterBoard` pid 341 (SIGTRAP, pc 0x1ce370268). No crash lines for SpringBoard or backboardd. The bluetoothd/fairplayd.H2 loop is GONE (xpcproxy 354 execs vs 4234 before; neither daemon in the top 10), so `disabled.plist` works on this build. Remaining small loop: `nanotimekitcompaniond` (35 execs). GUESS, unproven: the black screen is drawing/slowness or a not-yet-launched app, not a dead SpringBoard. Check next: `grep -a 'FBDIAG\|SWEET FB:' logs/sweetlog-vNN.txt | tail` (are swaps still happening, nonblack count). `ipsw` is not installed on the user's PC; `~/ios-build` has the IPSW dmgs (087-86593-047, 087-86698-044, 087-86715-047), `ios16-root.img(.bak)` and `ios16-root.sha256`.

**TIMING + BLACK-SCREEN EVIDENCE (2026-11-08, user-reported + v36 log):** boot to the Hello screen takes ~20 min (from power-on; earlier runs took ~50 min just to fill the bar). Changes since then, not separable: log args removed, a5fb_noconsole mute, heartbeat off, FBDIAG limited (0161), bluetoothd/fairplayd disabled. The root write was NOT read back (user skipped it, "it booted anyway"); treat the 867108dc... checksum as unverified on the phone. v36 tail (measured): swap counter reached 60000 and kept growing; the last events are `SWEET FB: display off`, `display on`, `backboardd sel 79 in 2/0 out 0/40 -> 0x0`, `display off`, i.e. iOS toggled the display state and the log ENDS on "display off". GUESS: the black screen after the swipe is the panel/backlight state (sleep or auto-lock) that our driver does not undo, not a dead SpringBoard. Unknown: whether the user pressed power in between (that also toggles display off/on). Next: read what `display off`/`display on` do in the framebuffer/DECON code and test a power-button press.

**NEXT (in order)**
1. (Console part DONE for the bar phase, see RESULT above; heartbeat still open.) Hide on-screen logs and the heartbeat (patch 0126, top-left blue rows) after the first display. Known leads (from older notes, unverified): `sweetfb_noconsole=1` did not stop console text overlaying iOS after the progress bar; suspects a5xelte patches 0109/0110 (override), 0046/0067; console text also came from `kprintf`/video console.
2. Remove diagnostics once stable: S9AFF loop (~0.8 s per M3), S9PMU, S9ID, 0151.
3. Confirm cpu 5-7 alive; time the boot against cpus=4 (old 1-core baseline ~50 min to the bar).
4. Read the M3's ID registers properly (photo of `S9ID` lines) instead of guessing the clamp.
5. Still open from earlier: iOS draws opaque black (FBDIAG nonblack 0/64), AKS selectors 2/3/6/31/34/93 unsupported, fairplayd/bluetoothd respawn loop fills the 4 MiB ring, RAM window 768 MiB (max without moving `UFS_PROBE_DMA`).


# HISTORY: older LATEST (2026-11-06 evening, boot v14; superseded by the 2026-11-08 section above)

**Milestone chain:** PAN fix (0132) -> launchd runs daemons (v13) -> RAM window widened to 768 MiB (v14) -> SpringBoard and backboardd exec'd once each, backboardd presents frames. NO lock screen/Apple logo yet after 28+ min; screen = text console with black rectangles in the middle (user photo).

**Done this session (claims separated):**
- v13 (0132, 512 MiB): `S9KAB` 0, launchd 6 threads, 309 `exec xpcproxy`, SpringBoard (line 685) and backboardd (776) exec'd. Only CRASH: `driverkitd` jetsam (`ns 1 code 0x7`; code 7 = per-process memory limit is from memory, NOT verified).
- v14 (user ran, same kernel, BOOT image rebuilt): `DRAM_SIZE = 0x30000000` in `tools/mkadt_star2lte.py` line 37 (sed). Boots, no panic, no reset; the line-15 comment ("layout panicked with more") did NOT bite at 768 MiB. Loader log/DMA area stays at 0x8f0000000 (`UFS_PROBE_DMA`, loader.c:27), so 768 MiB is the max without moving it; bank ends 0x980000000. Longer than 28 min: more daemons exec'd (softwareupdated, contacts/cloud, itunesstored, filecoordinationd, healthd, healthappd...). Then only fairplayd.H2/bluetoothd/xpcproxy loops (known donor noise).
- Memory (v14): `SMP vm free 3209 reserved 897 target 3208 active 62405 inactive 62467 wired 47088` (pages), free at target, active/inactive shrinking = cache churn, NOT a hard limit. Do not widen further for now.
- v14 log: still ONE CRASH (driverkitd). SpringBoard line 471, backboardd 569 (one exec each, no restart loop).
- Display path (patch 0046, `IOMobileFramebufferUserClient` swap): `SWEET FB: swap N layer 0 surface 3 1125x2436 fmt 0x42475241 (BGRA) bpr 4608`. CORRECTION: the log line is capped at 16 swaps (`sweet_fb_swaps_logged < 16`), N = IOMFB swap id (up to 55630 seen), so it does NOT prove frames are still arriving at the end. The copy `memcpy`s surface rows into `fPixels` and silently skips it (src=0) if: elementWidth/Height != 1, memory NULL, length check fails, or bpe != 4.
- Keystore stub (patch 0038): `default: ret = kIOReturnUnsupported` (0xe00002c7). `securityd sel 10 in 2/32 out 1/40` hits it 62 times (all other AKS calls -> 0x0). What selector 10 is: UNKNOWN (cases are named kAKS*, enum not seen yet). Whether it blocks SpringBoard: UNKNOWN.

**Written but NOT built/tested:** `tools/star2lte/make-0133.py` edits `xnu/patches/0046-sweet-iosurface-iomfb.patch` IN PLACE (revert: `git checkout xnu/patches/0046-sweet-iosurface-iomfb.patch`): logs `SWEET FBDIAG:` for the first 8 swaps then every 256th: `SKIP` + reason fields, or `ok nonblack N/64 px0 px32`. Tested only on a stand-in patch (hunk count correct, 2nd run refused). Unknown: whether a later patch touches those lines (CI apply would fail), compile errors. User had started the CI build before the limit; result unknown.

**Why a rebuild is needed (user asked):** the script edits patch text on the PC; the phone runs the compiled kernel, so CI build -> `gh run download` -> `s9.sh build` -> `flash` is required.

**NEXT (in order):**
1. Check CI result for the 0046 edit. If apply/compile fails, read the error, fix `make-0133.py`.
2. Boot with the new kernel + `sweetsample=SpringBoard,backboardd` (default per patch 0054 line 137; 0127 rework assumed to keep it, unverified). Wait ~30 min, `s9.sh pull`, then:
   `grep -a 'SWEET FBDIAG' logs/sweetlog-vN.txt | head -30`
   `grep -a 'SMP SpringBoard\|SMP backboardd' logs/sweetlog-vN.txt | tail -20`
   - FBDIAG `SKIP` -> fix the failing check in 0046. FBDIAG `ok nonblack 0/64` -> iOS draws black (look at SpringBoard/backboardd samples, selector 10). `nonblack >0` -> content exists, scanout/display problem (fPixels -> S-Boot framebuffer 0xcc000000, 1125x2436 vs native 1440x2960 path, `sweetfb_native`).
3. Keystore selector 10: `grep -rn 'kAKSOpen' xnu/patches/` for the enum; match in 2 scalars + 32 B struct, out 1 scalar + 40 B struct; add a case only once the meaning is known (do not guess a return shape).
4. Only if free memory drops far below target again or SpringBoard/backboardd get jetsam-killed: widen RAM (needs `UFS_PROBE_DMA` moved off 0x8f0000000; read donor NOTES.md "HIGHMEM": donor used dram-base/size in ADT + patch 0034 UFS DMA >4G, not needed here since our window is already >4 GiB).
5. Record every finding here right away; keep `AGENTS.md` rules (separate build/boot/screen/runtime claims).

**Commands (fish, no heredocs):** `mv` new files; push: `git add ...; git commit -m "..."; git push; gh run list --limit 1`; kernel: `gh run download -n xnu-kernel -D xnu/out-NNNN`; build: `env ARGS="<boot args in CURRENT STATE> sweetsample=SpringBoard,backboardd" bash tools/star2lte/s9.sh build xnu/out-NNNN/kernel.development.a5xelte`; `bash tools/star2lte/s9.sh flash`; after boot -> TWRP (Power+Vol Down, then Power+Bixby+Vol Up) -> `bash tools/star2lte/s9.sh pull`.

**User preferences (unchanged):** short replies, copy-paste commands, `mv` for new files, ask for exact log lines/greps rather than typed hex.


# HISTORY: CURRENT STATE (updated 2026-11-05 late; old)

**Where we are:** the kernel boots, mounts the iOS 16 HFS+ root from UFS (`hfs: mounted iOSRoot`), and execs Apple's `/sbin/launchd`. launchd then **hangs inside dyld's very first memory allocation**. No daemon ever starts (SMP samples for SpringBoard/backboardd are empty). The screen keeps updating (user checked), so the kernel is alive; only that one thread is stuck.

**Verified facts (from logs/photos, not guesses):**
- Boot args that work to this point: `debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam -noprogress wdt=-1 wdt_test=no_user_checkin a5touchprobe=0 rd=ufsroot0 ufsroot=USERDATA ufslogsecs=2 startup_debug=1 ufsrw=1 rootrw=1 unentitled_ios_sim_launch=1 ignition_level=1 launchd_unsecure_cache=1` (+ `sweetsample=launchd` for diagnostics). `ufsrw=1` works, so `s9.sh pull` returns the kernel SWEETLOG.
- ADT (`tools/mkadt_star2lte.py`, via donor `mkadt.build`) already contains `/chosen/asmb` (`lp-sip0`, `lp-sip1`). The image on userdata has `/System/Library/Caches/com.apple.dyld/` with the 44 cache files, `/System/Cryptexes/{App,OS}` symlinks. So the donor's SIP/cache-dir fixes are NOT the missing piece.
- XNU RAM window is only **512 MiB** (`mem=0x20000000` at `0x8c0000000`). The donor ran 1.2 GiB, then ~3.95 GiB ("highmem", donor notes) before userland was stable.
- Sampler (`sweetsample=launchd`, patch 0127) gives 10+ identical samples over ~18 min: pc `0x1007a9990`, lr `0x10079ff2c`, sp `0x16f7775b0`, bt `0x1007cb778 0x1007cded0 0x1007ac238`, launchd mh `0x100688000`. launchd `__TEXT` is only 0x68000, so these are NOT launchd code: they are in **dyld**, loaded at about `0x100798000` (4/4 return addresses match `bl` sites with slide 0x100798000, `tools/star2lte/findbase.py` on `llvm-objdump --macho --arch=arm64 -d /tmp/dyld`).
- Decoded stack: `lsl::Allocator::persistentAllocator` -> `lsl::MemoryManager::vm_allocate_bytes` -> `vm_allocate` -> `_kernelrpc_mach_vm_allocate_trap`; pc is the `ret` right after `svc #0x80` (x16 = -10 = mach_vm_allocate_trap).
- Inference (strong, not proven): the 17 ms timer IRQ would overwrite the saved user pc if the thread ran user code, so the thread is **blocked or looping in the kernel inside mach_vm_allocate**.

**REJECTED hypothesis: low memory.** Boot v8 (kernel 0128): `SMP vm free 118006 reserved 897 target 2405 active 54 inactive 2 wired 12910` (pages; free is ~130x the reserve), identical in samples 0-2 (free creeps +1 per sample). So 512 MiB is NOT what blocks dyld's vm_allocate (it may still be too small later; do not widen it for this reason).

**Finding (boot v8, 0128):** `SMP launchd t0 kernel state 0x4 wait_event 0x0 cont 0 kstack 0xfffffffb01ed0000`. State 0x4 = TH_RUN (TH_WAIT is 0x1): the thread is runnable, NOT sleeping, no wait event, no continuation. With cpus=1 the sampler thread is what is on the CPU while sampling, so launchd was preempted/queued. User regs are identical in every sample (mh moved to 0x100e58000 this boot because of ASLR; pc-mh = 0x1c9990 both boots, dyld base = mh + 0x...: same code location `ret` after the mach_vm_allocate_trap svc). Remaining explanations: (a) launchd spins inside the kernel in mach_vm_allocate (vm_map_enter/zone/retry loop), (b) it is runnable but never gets the CPU (priority/scheduler), (c) it retries the same syscall endlessly from user mode with identical saved state (unlikely: pc would still be refreshed by the 17 ms IRQ... unverified).
**Finding (boot v9, 0129, 2026-11-06):** 3 samples (now = 3144485283, 6264640609, 9385051288 ticks = 121 s, 241 s, 361 s) all show `sched pri 37 base 37 flags 0x0 mode 3`, `last_run_ago` 22899 / 24122 / 22770 ticks (26 MHz = about 0.9 ms) and `nentries 14 map_size 0x614416c000` (constant, so no allocation leak). So launchd is NOT starved: it was on the CPU less than 1 ms before every sample, i.e. it is really running, in the kernel (the saved user regs never change because an IRQ taken in the kernel does not touch them). Scheduler/priority hypothesis (b) REJECTED. Remaining: a kernel loop in the mach_vm_allocate path, or a user-mode retry loop of the same failing syscall. Kernel stack scan (low 32 bits, prefix 0xfffffff0; sample 0, top of stack first): 0742db80 074215a4 0742157c 072cf74c 072a1d88 07422228 07412ed8 0728f21c 0742b488 0728f21c 0716d400 0728f1e0 0728f21c 074217ec 07295688 072d8898 0716d400 072dad50 072da150 0742db50 07401460 07174000 072d9b64 07401560 072e0d1c 072cce04. NOT yet symbolized (next step).
**ROOT CAUSE FOUND (boots v10-v12, 0129+0131, 2026-11-06): PAN fault storm in copyin.** launchd's first `mach_vm_allocate` trap faults forever in `_bcopyin` (pc 0xfffffff00742b488, symbolized) reading its user stack: `S9KAB esr 0x9600000f far 0x16f22b5b0 fc 0xf ft 0x1 cpsr 0x20400204 tcr 0x22a5192519 sctlr 0x3454593d`, same fault repeated >40000 times, plus `S9FF va 0x16f22b5b0 ft 1 spte 0x600008c43b2e43 now == spte` (no PTE change). Decode: ESR EC 0x25 (data abort, current EL), DFSC 0x0f = permission fault level 3, WnR 0 = READ. PTE 0x...e43 = valid page, AF=1, AP[2:1]=01 (RW for EL1 and EL0), UXN+PXN, PA 0x8c43b2000: the mapping is fine. SPSR bit 22 (PAN) is 1 in cpsr 0x20400204, and SCTLR_EL1 0x3454593d has bit 23 (SPAN) = 0, so the A55 (FEAT_PAN) sets PAN=1 on every exception entry; the kernel's copyio code does not clear PAN (`__ARM_PAN_AVAILABLE__` is almost certainly not defined in this armv8-a build, so `user_access_enable()` is a no-op). Privileged load of a user page with PAN=1 = permission fault; `handle_kernel_abort` -> `arm_fast_fault_internal` sees a sufficiently permissive PTE ("already has sufficient permissions" path), returns KERN_SUCCESS without changing anything -> access retried -> same fault, forever. Everything before (scheduler, low memory, stack scans) was a symptom. PLANNED FIX (patch 0132, not written): set SCTLR_EL1.SPAN (bit 23) in `SCTLR_EL1_DEFAULT` (osfmk/arm64/proc_reg.h): PAN then stays 0 on exception entry; the bit is RES1 on cores without PAN (M3), so it is safe on both clusters. Alternative (not chosen): define `__ARM_PAN_AVAILABLE__` (would execute `msr PAN` on cores without PAN). 0130's `task counters` line prints garbage (those `task_t` field names/types are wrong): ignore it.
**MILESTONE (boot v13, 0132, 2026-11-06 15:00): launchd runs daemons.** Patch 0132 (`xnu/patches/0132-star2lte-sctlr-span.patch`, generated by `tools/star2lte/make-0132.py` from the real tree: SCTLR_EL1.SPAN set via `SCTLR_EL1_DEFAULT`) FIXED the dyld hang: `S9KAB` count 0. launchd now has 6 threads, 14053 mach and 33076 unix syscalls at 361 s, shared cache mapped (slide 0x1fcf4000), 309 `exec xpcproxy`, many daemons exec'd (syncdefaultsd, healthd, keybagd 3x, watchdogd 2x, usermanagerd 2x, analyticsd, mount_hfs 2x, mount 2x, DumpPanic, ...), fairplayd.H2 and bluetoothd relaunch ~30x each (known donor noise, no hardware). Only crash seen: `CRASH driverkitd sig 9 ... reason ns 1 code 0x7` (ns 1 = jetsam, code 7 probably per-process memory limit; unverified). NOT YET CHECKED: whether backboardd/SpringBoard were exec'd (not in the top 30 by count). MEMORY: `SMP vm free 2208 reserved 897 target 2405 active 38168 inactive 38216 wired 42015` (pages) at 361 s = ~470 of 512 MiB used, free below target. Memory widening is now the next topic: `DRAM_SIZE = 0x20000000` in `tools/mkadt_star2lte.py`; loader log/DMA area starts at 0x8f0000000 (`UFS_PROBE_DMA` in `shim/star2lte/loader.c`), so the window can only grow to 0x30000000 (768 MiB) without moving it; the contiguous bank ends at 0x980000000. A comment in mkadt (line ~15) says a layout "panicked with more": read it before changing. 0130's `faults`/`msgs_sent` counters are garbage, `syscalls_mach/unix` are valid.
**Pending evidence:** the framebuffer heartbeat (patch 0126, top-left blue hex rows: row0 = PC of the interrupted context at the last timer IRQ, row1 = LR, row2 = IRQ count) tells whether the CPU is busy in the kernel or idle in cpu_idle (idle PC seen earlier: 0x07428730). Ask the user for 2 close-up photos of the top-left rows, a few seconds apart, on a boot that is stuck (>5 min). Symbolize PC/LR with `~/swift/usr/bin/llvm-symbolizer --obj=KERNEL 0xfffffff0XXXXXXXX` (heartbeat prints the low 32 bits; kernel text is 0xfffffff007...).

**Work state:**
- Patch **0127** `xnu/patches/0127-sweet-sampler-nonblocking.patch`: sampler prints `regs` line first and reads frames only from resident pages (old 0054 code wedged in `vm_map_read_user`). Built by CI and tested on the phone: works.
- Patch **0128** `xnu/patches/0128-sweet-sampler-kstate.patch` (built by CI and run on the phone as boot v8: compiles, works): adds per sample `SMP vm free/reserved/target/active/inactive/wired` and `SMP launchd t0 kernel state 0x.. wait_event 0x.. cont .. kstack ..`. Uses `thread->state/wait_event/continuation/kernel_stack` and `vm_page_*` externs; if CI fails to compile, fix those names.
- CI: GitHub retired `macos-14` (2026-11-02). Workflow now uses `runs-on: macos-15`; build succeeded (0127). If the build ever fails in iig/Xcode, note the workflow comment: Xcode 16 `iig` emits IORPC.kernelContent that this xnu lacks.

**NEXT (decision tree):**
1. Get the heartbeat photos (see Pending evidence) and symbolize PC/LR: kernel loop (-> read that function, likely in vm_map_enter/vm_fault/zalloc paths) vs idle (-> scheduler/priority issue; then print thread->sched_pri/runq and processor state).
2. Next sampler patch (0129, if needed): print kernel backtrace of the launchd thread from its saved kernel context (thread->machine kstackptr / saved fp chain, symbolizable) plus sched_pri, runq, last_run_time.
3. Memory widening (donor highmem, NOTES.md search "HIGHMEM") is NOT needed for this blocker; revisit once launchd runs daemons.
4. After launchd passes dyld: expect the donor sequence (SHA1/in6_nigroup crash needs donor 0032/0033, already below 0124; `_PanicOnCrash` plist patch v5 and `-wdt_no_pmu`; watchdogd/IOWatchdog; AMFI/platform-binary patches 0035/0036). Check which donor image-side fixes (v3 keybag, v5 plist) are in the S9+ image (`ios16-root.img`, 17 GB, built 2026-11-05 21:32 in `~/ios-build`; only one image file there).

**Exact commands (user's shell is fish: no heredocs, no `$(( ))`):**
- Push patch (use `mv`, not `cp`, for new files): `cd ~/Downloads/ios-galaxy-s9plus; mv ~/Downloads/NNNN-*.patch xnu/patches/; git add xnu/patches/NNNN-*.patch; git commit -m "..."; git push; gh run list --limit 1`
- Download kernel into a FRESH dir (SHA256SUMS exists in xnu/out): `gh run download -n xnu-kernel -D xnu/out-NNNN`
- Build + flash (TWRP, confirms `yes`): `env ARGS="<boot args above>" bash tools/star2lte/s9.sh build xnu/out-NNNN/kernel.development.a5xelte` then `bash tools/star2lte/s9.sh flash`; look for `BUILD OK`.
- After boot (~4 min; first sample at 90 s, then every 120 s): TWRP (Power+Vol Down, then Power+Bixby+Vol Up), `bash tools/star2lte/s9.sh pull` (next free vN; v7 = 0127 run). Use `tail -n 80 logs/ldrlog-vN.*` (not `tail -80`).
- Disassemble without flooding the terminal: redirect to a file, then `grep -n` / `sed -n 'A,Bp'`. dyld/launchd are extracted from the image: `sudo mount -o loop,ro -t hfsplus ~/ios-build/ios16-root.img /mnt/x; cp /mnt/x/usr/lib/dyld /tmp/dyld; sudo umount /mnt/x`.

**User preferences:** short replies (token cost); copy-paste commands; use `mv` (not `cp`) when moving new files (patches, tools, progress file) into the repo; record EVERY new finding in this section right away; new to git; ask for exact files/log lines rather than typed hex (use `s9.sh pull`, photo only as backup).

Project name: **frankenstnine** (Frankenstein + S9; the user's choice, turn 5). Only display names use it; directory, patch and code names (`star2lte` etc.) stay.
GitHub: user `georgev-6974`, repo created as `s9plus-ios` (renamed to `frankenstnine` in turn 5, see step C). Local folder is still `~/Downloads/ios-galaxy-s9plus`.

# HANDOFF (read this first; last updated 2026-11-05)

**Goal**: boot an iOS 16 XNU kernel on a Galaxy S9+ (SM-G965F, Exynos 9810) via a custom loader in the BOOT partition (`sda10`), forked from the S8 port.
**Standing rules** (AGENTS.md): never reuse an S8 address without a measurement; keep build success / kernel markers / screen reports / iOS runtime as separate claims; keep dumps, serials and Apple binaries out of git; confirm every destructive step with the user; donor files (`shim/dreamlte`, `tools/dreamlte`, `DREAMLTE_PROGRESS.md`, `NOTES.md`) are not edited.
**State (SUPERSEDED by "Helper script and latest hardware results" below: the loader and kernel have now run on the phone)**: loader cross-compiled before turn 4 (was never run then; the turn-4 edits to it are NOT compiled, no clang in the assistant sandbox). ADT generator and make-boot.sh exist (offline only). Patch 0125 exists as a script (`apply-star2lte.py`), checked on a pseudo-tree only. **No phone measurement beyond the TWRP facts below; no kernel built; no boot attempted.**
**Blocked on the user**: see "What you do next" (user has a generated, real-tree-verified 0125 patch; next: re-unzip, send two small facts, push to GitHub and build).

## Helper script and latest hardware results (added 2026-11-05)
**`tools/star2lte/s9.sh` exists: use it instead of hand-typing commands, and keep the user on it.** Run from the project folder:
- `bash tools/star2lte/s9.sh build [KERNEL]`: runs `make-boot.sh` (newest file in `xnu/out` if none given; MPIDR 0x0; boot-args default include `rd=ufsroot0 ufsroot=USERDATA ufslogsecs=2`, override with `ARGS="..."`), checks the 57,671,680-byte BOOT limit, writes `out.img`.
- `... flash [IMG]`: TWRP only; asks `yes`, writes `sda10`, reads it back and compares SHA-256, optional reboot. Refuses without `~/s9-backup/boot-sda10.img`.
- `... pull [NAME]`: pulls and decodes LDRLOG + SWEETLOG into `logs/`; **NAME defaults to the next free `vN`** (v1, v2 exist as of now), prints loader head and kernel tail.
- `... restore`: writes the stock BOOT backup back to `sda10`.
Edit the script (not ad-hoc commands) when a step changes, and ship it in the zip.

**Observed on the phone (user-reported, 2026-11-04/05; kernel built by CI, run IDs not in this zip):**
- Loader ran: `EL=0x1 SCTLR=0x30c5183e DTB=0x8a000000 MPIDR=0x81000000` (affinity 0x0 = A55 cluster, so `--boot-mpidr 0x0` is right), initrd `0x89000000-0x89fbb880`, XNU window `0x8c0000000` 512 MiB, entry `0xfffffff007424488`, 10 segments copied.
- **DECON trigger fixed**: `DECON_TRIG` at `0x16030070` read `0x3070`, written `0x1281`, reads back `0x1001`. The screen shows the loader and kernel text.
- **XNU boots and prints on screen** (photo): VM/zone init, IOKit, platform expert, AppleKeyStore, WDT, HID, static battery, AppleCLCD 1440x2960 at 0xcc000000, AMFI, vnguard; last visible line `trust caches unavailable (Image4/AMFI not installed)`. The user waited only ~3 min then went to TWRP, so it is NOT known whether it stalls there or is just slow (CPU-drawn console, 1 core; S8 needed ~15 min to the lock screen).
- `SWEETLOG` empty after that boot: expected, because the kernel UFS driver (and its log thread) only starts at root mount (`rd=ufsroot0`), which the first boot-args did not request. Next trial uses `rd=ufsroot0 ufsroot=USERDATA ufslogsecs=2`; this writes ~4 MiB at the end of `sda25` (Android data tail; the user accepted losing Android in AGENTS.md, but confirm before flashing).
- Open: whether the kernel progresses past `trust caches` (wait >=10 min, photograph), then whether the UFS driver works on the S9+ (`SWEET UFS:` lines).

**Trial v3 (user-reported + log, 2026-11-05):** boot-args had `rd=ufsroot0 ufsroot=USERDATA ufslogsecs=2`. After 24 min the screen was still frozen on the `trust caches unavailable` line; no new text. LDRLOG v3 is complete and clean: the loader's UFS probe works on the S9+ (VER 0x210, GPT parse OK; BOOT 0x4c02-0x8301, SYSTEM 0x10c80-0x26287f, USERDATA 0x309180-0xee47fa; the first TUR "not ready" is cured by SSU wlun ACTIVE) and it printed `JUMP TO XNU`. SWEETLOG empty = the kernel never reached the root-device/UFS init (patch 0028 `sweet_ufs_rootdev`, called from bsd_init -> vfs_mountroot). **So the hang is in `kernel_bootstrap_thread` after `trust_cache_runtime_init`/`load_static_trust_cache`, or early in `bsd_init`.** From xnu-8796 source (`osfmk/kern/startup.c`), the order after the trust-cache line is: `kernel_startup_initialize_upto(STARTUP_SUB_LOCKDOWN)` -> `OSKextRemoveKextBootstrap` -> `machine_lockdown` -> `PE_lockdown_iokit` -> `bsd_init` (-> IOKitInitializeTime, vfsinit, bsd_autoconf, setconf, vfs_mountroot). Suspects: a timer/GIC tick that never arrives with `cpus=1` (a sleeping thread never wakes), `machine_lockdown`, or something in `PE_lockdown_iokit`/IOKit matching. **No rebuild needed to narrow it:** the boot-arg `startup_debug=1` makes XNU kprintf every startup step ("kernel_bootstrap_thread: <step>"); `s9.sh build` now includes it by default. Next trial = photograph the LAST lines on screen after ~2-3 min.

**Trial v4 (`startup_debug=1`, photo, 2026-11-05):** every bootstrap step printed. The kernel passes `trust_cache_init`, `OSKextRemoveKextBootstrap` (keepsyms), `machine_lockdown`, `kernel_do_post - done`, `PE_lockdown_iokit`, then IOKit prints `A5XELTE: starting device-tree platform expert`, AKS, WDT, SURF, HID buttons+touch, static BATTERY and **`SWEET FB: AppleCLCD 1440x2960 ... presented as 1125x2436` = the LAST line printed**. The long `kernel_startup_initialize_upto[15, rank 2147483647]: 0x..addff0(0x..)` block below the blank gap on screen is OLD text (sysctl registrations, phase 15 = STARTUP_SUB_SYSCTL) not yet overwritten: the framebuffer console wraps around and the blank gap marks the cursor. So the kernel stalls AFTER AppleCLCD registers and BEFORE any `SWEET UFS:` line (SWEETLOG stays empty), i.e. in IOKit matching or early `bsd_init` (IOKitInitializeTime, vfsinit, bsd_autoconf, IOFindBSDRoot wait). `bsd_init` kprintfs are compiled out (DEBUG_BSDINIT 0). Leading hypothesis: timers/interrupts do not reach the CPU (cpus=1; first thread with a timed wait never wakes; the CPU sits in WFI). Alternatives: a spin/deadlock in a SWEET IOKit driver, or the AppleCLCD vsync timer path.
**Patch 0126 (`xnu/patches/0126-star2lte-idle-diagnostics.patch`, written 2026-11-05, generated and `git apply --check`ed on a tree rebuilt with `prep-xnu-tree.sh` + `apply-star2lte.py`; function syntax-checked with clang, NOT built by CI yet):** `a5xelte_idle_diag()` (pexpert/arm/pe_fiq.c) is called from `cpu_idle()` just before WFI and kprintfs `S9DIAG idle#N ct ctl(CNTP_CTL) cval-ct due daif | gicd grp en pend act | gicc pmr hpp | irqs=<count> last_iar=` when state changed or every 64th idle (cap 400 change-prints); `sleh_irq` counts IRQs (`a5xelte_irq_count`, `a5xelte_last_iar`); `startup.c` arms it just before `PE_lockdown_iokit` and prints `S9DIAG: armed`. **How to read the next photo:** `irqs=0` while `ctl=1` (timer enabled, unmasked) and `due=1` or `pend` bit 30 set = the timer fires but the interrupt never reaches the CPU (GIC group/priority/enable/routing, DAIF.I set); `ctl=0` or `cval` far in the future = timer never armed (software); `irqs` rising and `last_iar=1e` = interrupts work and the stall is elsewhere (a spin in a driver).

**Trial v5 (kernel with 0126 v1, photo/report 2026-11-05):** the first attempt booted an OLD image: `s9.sh build` had picked `kernel.development.a5xelte.lse.txt` (30-byte text) and the failed build left a stale `out.img` that `flash` wrote. Fixed in `s9.sh` (Mach-O magic check, `rm -f out.img` first, `BUILD OK` line). Real v5: `S9DIAG: armed before PE_lockdown_iokit` appeared between the `kernel_do_post` and `PE_lockdown_iokit` lines, but NO `S9DIAG idle#` lines after 3 min. So after arming the CPU never reached the WFI in `cpu_idle` (hook was just before WFI). Either it spins/deadlocks outside the idle path (driver/IOKit/bsd_init), or `cpu_idle` exits early without WFI (`cpu_proximate_timer()` -> `Idle_load_context()` loop = a due timer whose IRQ never arrives). **0126 v2** (same file name, replaces v1): idle diag moved to the TOP of `cpu_idle` (before every early exit); `S9DIAG: PE_lockdown_iokit returned` after that call; `DEBUG_BSDINIT 1` so `bsd_init: calling <step>` kprintfs show. Reading the next photo: no `bsd_init:` lines and no `returned` = stuck inside `PE_lockdown_iokit`/IOKit matching; `bsd_init:` lines stopping at step X = stuck in X; `S9DIAG idle#` lines with irqs=0 = timer interrupt not delivered.

**Trial v6 (0126 v2 kernel, photo 2026-11-05):** screen full of `S9DIAG idle#N ...` lines. Findings: (1) **timers and interrupts WORK on the S9+**: `ctl=1`, GICD en=0x40007fff (INTID 30 enabled), GICC ctl=1 pmr=0xf0 hpp=0x3ff, `irqs` increments (20->21...), `last_iar=0x1e` = INTID 30, the deadline `cval-ct` counts down and fires about every 17.65 ms (459023 ticks at 26 MHz); the old "timer IRQ never arrives" hypothesis is REJECTED. (2) The CPU re-enters `cpu_idle` every ~12.8 us (~1340 times per tick; WFI returns at once / idle loop is hot): harmless. (3) **BUG in 0126 v2 (my fault): after the first 400 change-prints the `n%64` branch printed forever and the flood overwrote the screen, so the `bsd_init:` and `PE_lockdown_iokit returned` lines were lost.** (4) The newest printed line has `ct=0x9ac0e38` (6.24 s) at `idle#25344` with `cval-ct=12332`; nothing later appears, even though idle prints should continue every 0.8 ms. So the machine most likely STOPPED right after that line, within ~0.5 ms, i.e. at the next timer deadline: a thread/callout woke and then spun forever or hung with IRQs masked (candidate: an unbounded hardware poll, e.g. in `sweet_ufs_init`/rootdev, or a driver start; not confirmed). Caveat: the photo time after boot was not recorded; a stale screen cannot be fully excluded.
**0126 v3** (same file name, replaces v2): idle kprintf capped at 6 lines (no flood); a **framebuffer heartbeat drawn directly from the IRQ handler** (white hex digits on blue at the top-left, 4 rows, 8 digits each, scale 4: row0 = PC of the interrupted context (low 32 bits; kernel text is 0xfffffff007xxxxxx, so prefix 0xfffffff0), row1 = its LR, row2 = IRQ count, row3 = idle-entry count; PC/LR/count refreshed every 4th IRQ, idle count every 4096 idles). Reading: row2 counting + row3 frozen = a thread spins with IRQs ON and row0 is where (symbolicate: `bash tools/dreamlte/sym.sh xnu/out/<kernel> 0xfffffff0<row0>`); row2 AND row3 frozen = hung with IRQs masked (row0 = last sample before the hang); both counting = the CPU is alive and the console is what stalled. Also kept: `DEBUG_BSDINIT 1` (`bsd_init:` lines) and `S9DIAG: PE_lockdown_iokit returned`. Verified: applies to the real tree, function syntax-checked, glyph rendering tested on the host; NOT built by CI. Possible follow-up if the CPU is idle-blocked: dump all thread wait states (`threads` queue, `thread->machine.kstackptr` saved fp/lr).

**Trial v7 (0126 v3 kernel, photos 2026-11-05 14:12):** heartbeat rows visible (left edge clipped by the rounded screen corner): row0 (PC) ?428730 = 0x07428730 (leading 07 inferred), row1 (LR) 0742872C, row2 (IRQ count) 000070F0 = 28912 (~8.5 min at 17.65 ms), row3 (idle count) 4998?000. The user reports the rows KEEP CHANGING (still running after 30+ min): the kernel is ALIVE, IRQs keep arriving, and the sampled PC varies, so it is not a hard hang or a single spin loop; it may just be very slow (S8 needed ~15 min to the lock screen). The earlier "stopped at 6.24 s" conclusion is withdrawn (the v2 flood probably stalled the console, not the CPU). Idle kprintf lines (6 max) show the timer firing every 17.65 ms (irqs 4..7, ctl=5/due=1 just before a fire). Console text after `SWEET FB:` never appeared: NO `Copyright (c) 1982...` (the `printf(copyright)` at the start of `bsd_init`), and NO `bsd_init:` lines even with DEBUG_BSDINIT=1, so either the main kernel thread is stuck/slow before that printf (between `PE_lockdown_iokit returned` and the first bsd_init lines: vm_set_restrictions, kperf_init_early, platform_stall_panic_or_spin, throttle_init) or the console output is stalled. PC 0x07428730 is only ~17 KB above `_start` (0x07424488): symbolicate with `bash tools/dreamlte/sym.sh xnu/out/kernel.development.a5xelte.lse 0xfffffff007428730 0xfffffff00742872c`.
**0126 v4** (same file; replaces v3): heartbeat moved to x=120,y=70 (clear of the rounded corner); markers `S9DIAG: calling bsd_init`, `S9DIAG: bsd_init entered`, `S9DIAG: throttle_init done`; one-shot **thread dump 45 s after arming** (`a5xelte_thread_dump()` in osfmk/arm64/cpu.c, trigger `a5xelte_dump_due()` in pe_fiq.c): lines `T<tid> s<state> e<wait_event> c<continuation> | <saved lr> <4 callers>` (low 32 bits; prefix 0xfffffff0), symbolicate with sym.sh. Verified: git apply --check on the real tree; field names checked against thread.h/thread_kernel_state.h; NOT built by CI.

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
   First failure seen: run 41908009114 died after ~2 min in script `0020-stage-bearssl.sh` with `www.bearssl.org ... HTTP 502` (their server, not our code). Turn 6 added retries + two GitHub mirrors; turn 7 log showed that was not enough (bearssl.org 502 for >2 min on all 3 attempts; both mirrors answer "not our ref 7bea48e5", i.e. they lack that commit). Turn 7: vendor the commit into the repo (step C2). To retry only the failed part of a run without a new push: `gh run rerun RUN_ID --failed`.
   **C2 (needed while bearssl.org is down): vendor BearSSL into the repo.** The script `xnu/patches/0020-stage-bearssl.sh` now uses `xnu/patches/bearssl-7bea48e5e850ab4cafbe68d3765cdaba13a86d6f.tar.gz` if it exists (found through `$GITHUB_WORKSPACE`), and only then the network. Make that file ON YOUR PC, once:
   `git ls-remote https://www.bearssl.org/git/BearSSL | head -3`   (prints lines of hashes = site reachable; error/502/hang = not reachable now, wait 30-60 min and retry, or tell the assistant)
   `rm -rf /tmp/bearssl-src; git init -q /tmp/bearssl-src`
   `git -C /tmp/bearssl-src fetch --depth 1 https://www.bearssl.org/git/BearSSL 7bea48e5e850ab4cafbe68d3765cdaba13a86d6f`
   `git -C /tmp/bearssl-src checkout -q FETCH_HEAD`
   `git -C /tmp/bearssl-src rev-parse HEAD`   (must print exactly 7bea48e5e850ab4cafbe68d3765cdaba13a86d6f; if not, STOP)
   `git -C /tmp/bearssl-src archive --format=tar.gz -o ~/Downloads/ios-galaxy-s9plus/xnu/patches/bearssl-7bea48e5e850ab4cafbe68d3765cdaba13a86d6f.tar.gz HEAD inc src LICENSE.txt`
   `ls -l ~/Downloads/ios-galaxy-s9plus/xnu/patches/bearssl-*.tar.gz; tar -tzf ~/Downloads/ios-galaxy-s9plus/xnu/patches/bearssl-*.tar.gz | head -5`   (several hundred KB; list starts with inc/ or src/)
   then `git add -A; git status --short; git commit -m "vendor BearSSL 7bea48e5 for CI"; git push`.
   **C2-alt (turn 8): if the `git fetch` above gives HTTP 502** (observed: `git ls-remote` works and shows 7bea48e5 = master HEAD, but pack downloads 502), use the site's gitweb snapshot route instead (the URL form Gentoo/Alpine packages use):
   `curl -fL --retry 8 --retry-all-errors --retry-delay 15 -o /tmp/bearssl-snap.tgz 'https://bearssl.org/gitweb/?p=BearSSL;a=snapshot;h=7bea48e5e850ab4cafbe68d3765cdaba13a86d6f;sf=tgz'`
   `gzip -dc /tmp/bearssl-snap.tgz | git get-tar-commit-id`   (must print exactly 7bea48e5e850ab4cafbe68d3765cdaba13a86d6f; if it prints NOTHING, tell the assistant; if it prints a different hash, STOP)
   `rm -rf /tmp/bearssl-snap; mkdir /tmp/bearssl-snap`
   `tar -xzf /tmp/bearssl-snap.tgz -C /tmp/bearssl-snap --strip-components=1`
   `ls /tmp/bearssl-snap`   (must include inc, src, LICENSE.txt)
   `tar -czf ~/Downloads/ios-galaxy-s9plus/xnu/patches/bearssl-7bea48e5e850ab4cafbe68d3765cdaba13a86d6f.tar.gz -C /tmp/bearssl-snap inc src LICENSE.txt`
   then the same `ls -l` / `tar -tzf ... | head -5` checks and the `git add/commit/push` line above. (Or retry the fetch in fish: `for i in 1 2 3 4 5 6; git -C /tmp/bearssl-src fetch --depth 1 https://www.bearssl.org/git/BearSSL 7bea48e5e850ab4cafbe68d3765cdaba13a86d6f; and break; sleep 20; end`.)
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

**Turn 7 (user pasted the failed log of the run with the turn-6 retries)**
- Observed: the retry loop ran 3 rounds x 3 sources (~2 min): bearssl.org HTTP 502 every time; github.com/nickray/bearssl and github.com/tarigo/BearSSL: "not our ref 7bea48e5..." (commit absent). Ends `could not fetch BearSSL`, exit 1. libpthread staging passed again. Still nothing of ours compiled.
- Changed: `xnu/patches/0020-stage-bearssl.sh` prefers a vendored `xnu/patches/bearssl-<sha>.tar.gz` (extracted into the temp dir, network skipped); network loop and the commit check are unchanged and only run without it. The two mirrors stay in the loop but are known not to have the commit.
- Added: step C2 (user creates the tarball locally from bearssl.org and commits it).
- Corrected: my turn-6 assumption that a GitHub mirror would carry the commit.
- Verified: syntax; vendored path tested with stand-in files (18 files staged, `limits.h` rewrite applied, exit 0). NOT verified: the real tarball (does not exist yet), anything in the real CI. Trust note: the vendored tarball has no hash pin; its integrity rests on the user's local `rev-parse` check.

**Turn 8 (user ran C2 on their PC)**
- Observed: `git ls-remote https://www.bearssl.org/git/BearSSL` works: HEAD and refs/heads/master = 7bea48e5e850ab4cafbe68d3765cdaba13a86d6f (so our pin is the current master head). `git fetch --depth 1 <url> <sha>` fails with HTTP 502 for the user too; the empty /tmp/bearssl-src repo then made checkout/rev-parse fail (harmless follow-ups).
- Found (web search): bearssl.org also serves `https://bearssl.org/gitweb/?p=BearSSL;a=snapshot;h=<commit>;sf=tgz` (used by Gentoo and Alpine packages), a different server path; top directory in the tarball is `BearSSL-<first 7 of sha>/`.
- Added: step C2-alt (curl with retries, commit check with `git get-tar-commit-id`, re-pack into the layout the script expects).
- Changed/removed: nothing in code. NOT verified: that the gitweb route works right now, or that its tarball carries the commit-id header (the check will tell).


**Turn 9 (CI still fails on bearssl.org 502; user has no tarball yet)**
- Observed: no `xnu/patches/bearssl-*.tar.*` exists in the repo/zip, so the script still falls into the network loop (bearssl.org 502; the two GitHub mirrors lack the pinned commit).
- Changed: `xnu/patches/0020-stage-bearssl.sh` now takes ANY `xnu/patches/bearssl-*.tar.gz|.xz|.tgz` (pinned-sha name preferred), in any layout (`git archive`, gitweb snapshot, release/Debian tarball with one top dir), and warns when it is not the pinned commit.
- Verified: syntax; staging with stand-in trees in all three layouts (files staged, `machine/limits.h` rewrite applied). NOT verified: a real BearSSL tarball, the real CI.
- Fallback (not the pinned commit, 0.6 release of 2018): Debian `bearssl_0.6+dfsg.1.orig.tar.xz` (e.g. mirror.its.umich.edu/ubuntu/pool/universe/b/bearssl/). Unverified that patch 0098 builds against 0.6.

**Turn 10 (CI got past the BearSSL download; new failure in my script)**
- Observed: run on macOS runner: `0019-stage-libpthread` OK, then `0020-stage-bearssl.sh` died with `find: -printf: unknown primary or operator` (BSD find). So the vendored tarball WAS found and extracted; only my layout-detection line failed. The "Package build tree" errors that follow are consequences (no build tree).
- Changed: `0020-stage-bearssl.sh` detects the top directory with a portable bash loop instead of `find -printf`. My Turn 9 test ran on Linux, whose find has -printf, so it could not catch this.
- Verified: syntax, no `printf` left in the find line, three tarball layouts on Linux. NOT verified: on macOS (the real CI).

**Turn 11 (user ran step D; `ModuleNotFoundError: No module named 'adt'`)**
- Observed: `tools/star2lte/make-boot.sh` runs `python3 -I tools/mkadt_star2lte.py`; `-I` (isolated mode) does not put the script's directory on `sys.path`, so `import adt` (tools/adt.py) failed. `out.img` missing was only the follow-up `ls`.
- Changed: `tools/mkadt_star2lte.py` inserts its own directory into `sys.path` before `import adt, mkadt` (as `mkadt.py` and `mkpayload.py` already do).
- Verified: `python3 -I tools/mkadt_star2lte.py ... --boot-mpidr 0x0` now writes a 9576-byte ADT here (only the expected `d22ap.adt missing` warning). NOT verified: the later steps (`mkpayload.py` with the real kernel, `build.sh` loader compile with `-Werror`, bootimg packing): I have neither the kernel, the stock boot image nor clang in my sandbox.

**Turn 12 (FIRST S9+ BOOT TRIAL, user-reported 2026-11-05)**
- Observed: phone stayed on the Samsung "Galaxy S9+" logo (no loader text, not blank). Log pulled from sda25 (`docs/star2lte-facts/ldrlog-v1.txt`): the loader RAN TO THE END and printed `JUMP TO XNU`.
- Measured: loader entered at EL1, SCTLR 0x30c5183e (M=0, MMU off), boot CPU MPIDR_EL1 0x81000000 = Aff 0x0 (A55 cluster, cpu0; matches `--boot-mpidr 0x0`; bit 24 is MT). S-Boot DTB 0x8a000000, initrd (our payload) 0x89000000-0x89fbb880. XNU RAM at 0x8c0000000 (512 MiB) zeroed and written without a fault; 10 segments copied; entry_pa 0x8c1424488.
- Measured UFS: VER 0x210 (UFS 2.1); first TUR "not ready" (key 2 asc 4 ascq 2) -> SSU wlun ACTIVE fixes it, same as S8; READ and GPT parse work. GPT: BOOT 0x4c02-0x8301, SYSTEM 0x10c80-0x26287f, USERDATA 0x309180-0xee47fa.
- Verified on hardware: the new UFS WRITE(10) path wrote the LDRLOG area (flush #2) at the computed LBA; TWRP read it back at `n-1025-64` of sda25, so the block arithmetic is right.
- NOT known: whether XNU started. The logo stays because the S9+ display trigger is not ported (the loader's text was drawn into 0xcc000000 but is not shown) OR XNU hung/crashed after the jump; the screen cannot tell them apart, and XNU has no log channel yet (patch 0124's 0x92xxxxxx klog is not a reserved region here; the kernel UFS ring needs the XNU UFS driver).
- Next: measure DECON_F (0x16030000) in TWRP with devmem to port the display trigger; then add an XNU-side log channel.

**Turn 13 (display trigger; TWRP has no /dev/mem access)**
- Observed (TWRP): `/dev/mem` node can be created but the kernel has no devmem (ENXIO), so no register reads from TWRP. debugfs `decon/` has `dump0`/`dump2` (empty) and `event0`: driver event log only (60 Hz TE interrupts, DSIM init commands, hibernation on); no register offsets. Live DT `decon_f`: `exynos9-decon`, psr_mode 2 (command), trig_mode 0 (HW trigger).
- Found (web, barebox mailing list patch for samsung-exynos): HW_SW_TRIG_CONTROL = DECON0 + 0x70 on the 8895 (0x12860000) and the 990 (0x19050000); bits 12 (auto mask), 8 (SW trig), 0 (HW trig); the patch says post-S7 phones leave framebuffer refresh disabled at handoff. The 9810 is between them, so 0x16030070 is the likely register. NOT verified on a 9810.
- Changed: `shim/star2lte/loader.c` writes 0x1281 (the value that worked on the S8) to `0x16030070` at entry and logs `DECON_TRIG old` / `DECON_TRIG now`; `-DSTAR2LTE_NO_DECON_TRIG` turns it off. Host syntax check only; not compiled with clang/aarch64 here.
- Expected: if the hypothesis is right the loader text appears on screen; the log's `old` value tells us what S-Boot left in the register. Risk: a wrong register layout could leave the logo/blank; restore sda10 from backup.

**Turn 14 (display trigger build flashed; user-reported 2026-11-05)**
- Observed: the screen now shows text (the `0x16030070 = 0x1281` trigger write works, so the S8 unmask value and the DECON_F + 0x70 offset hold on the 9810 at least for display). XNU is RUNNING: the last visible line was `SWEET: trust caches unavailable (Image4/AMFI not installed)`.
- Meaning: that line is our own patch 0015 (`kern_trustcache.c`, `trust_cache_init`), an intentional benign message because the lab build has no AppleImage4/AMFI. Reaching it means: loader handoff, MMU/pmap/VM bring-up and early kernel threads all worked on the S9+.
- NOT known: where it stops after that line (hang vs panic), whether timers/GIC interrupts work (`cpus=1`), whether the XNU UFS driver (patch 0028 path) works on the 9810 so the root device can mount.
- Next: pull the kernel SWEETLOG ring (needs the XNU UFS driver flushing) plus the LDRLOG; if the ring is empty, photograph the last screen.


## Handoff 2026-11-07: display works with sweetfb_native=1; second core fails (user-reported + logs v15-v21)

**Observed (measured from logs unless marked user-reported):**
- AKS: patch 0038 now handles kAKSWrapKey (10) and kAKSUnwrapKey (11) with a reversible stub (8 bytes 0xA6 + 32-byte key = 40). Log v16: `AKS wrap: in=32 out=40`, `unwrap in=40 out=32`, both -> 0x0. Still unsupported (minor daemons): sel 93, 34 (datamigrator), 31 (profiled). CreateBag/SaveBag/LoadBag (2/3/6) not added.
- Black rectangle cause: without `sweetfb_native=1` backboardd presents a 1125x2436 surface (centered, dst 157,262) and nothing ever wrote into it (FBDIAG px = 0x0). Patch 0046 FBDIAG now logs every swap (`sed` edit, committed). SpringBoard and backboardd were exec'd once each (no crash loop).
- **With `sweetfb_native=1` (v20, user-reported):** Apple logo + progress bar appeared. Bar took ~50 min on one core (S8 took ~15 min to the lock screen). Surface is 1440x2960 at dst 0,0, px = 0xff000000 (opaque black written by iOS), 0 non-black samples in every valid line. Screen was later buried by kernel console text. No lock screen seen yet (user waited ~2 h in the earlier run).
- Log ring (4 MiB) fills with the `fairplayd.H2` / `bluetoothd` respawn loop (55 execs each in v19); early lines get overwritten in long runs. Use short runs (about 20 min after the bar disappears) or `sweetfb_noconsole=1`.
- Memory is tight: `SMP vm free` 2200-5400 pages (~10-20 MB) of 512 MiB. `driverkitd` killed `sig 9 reason ns 1 code 0x7` (probably jetsam, unverified).

**Second core (cpus=2), user-reported photo of the panic screen, 2026-11-07 00:55:**
- Screen: `CPU_ON target=0x1 entry_pa=0x8c142a000 context=1`, then `PSCI CPU_ON rc=0`, then `A5XELTE CPU: cpu=1 mpidr=0x1 NOT alive after 10s` and `panic(cpu 0 ...): cpu=1 startup timeout (reset/MMU/GIC/SGI) @SweetCPU.cpp:203`.
- So firmware accepted CPU_ON (rc=0) but core 1 never reported alive. The panic erased the log ring: sweetlog-v21 is from the previous cpus=1 boot, not from this panic.
- Hypotheses (NOT verified): (1) the entry PA 0x8c142a000 is above 4 GiB and S-Boot's PSCI keeps only 32 bits; donor patch 0124 (S8) needed a low-memory/PMU INFORM workaround for exactly this, and 0125 turned it off for STAR2LTE. (2) If the core enters at EL2, `ICC_SRE_EL2` access in `sweet_secondary_entry` (patch 0065) is undefined on a GICv2/GIC-400 part. (3) Fault inside LowResetVectorBase (reset/MMU).
- Code seen: `sweet_secondary_entry` in patch 0065 (EL1/EL2 check, then `b LowResetVectorBase`), `SWEET_SMP_MAX_CPUS 6`. Cores 0-3 = A55 (MPIDR 0-3), cores 4-7 = Exynos M3 (MPIDR 0x100+), untouched.

**Working boot (use this until the core is fixed):** kernel from CI run 0134 (`xnu/out-0134` or `out-0135`, same code besides FBDIAG), boot-args `debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam -noprogress wdt=-1 wdt_test=no_user_checkin a5touchprobe=0 rd=ufsroot0 ufsroot=USERDATA ufslogsecs=2 startup_debug=1 ufsrw=1 rootrw=1 unentitled_ios_sim_launch=1 ignition_level=1 launchd_unsecure_cache=1 sweetsample=SpringBoard sweetfb_native=1` (+ `sweetfb_noconsole=1` is the next untested step; not yet timed). The default ARGS in `s9.sh` lacks most of these: always pass `env ARGS="..."`.

**Next:** (a) time the progress bar with `sweetfb_noconsole=1`; (b) debug core 1: read patch 0124 lines ~798-870 (S8 CPU_ON workaround) and decide if the entry must move below 4 GiB; add a stage marker written by the secondary at entry; (c) later: more RAM, stop the fairplayd/bluetoothd respawn loop, AKS 2/3/6.

**Rules kept:** nothing in `shim/dreamlte`, `tools/dreamlte`, `DREAMLTE_PROGRESS.md` or `NOTES.md` was edited. All results above are from the S9+ device; the 0124 code is donor reference only. Nothing from the core fix has been compiled or run.

## Build 0136 (2026-11-07): low-RAM trampoline for core 1 (UNTESTED on device)
- Why: PSCI CPU_ON got entry 0x8c142a000 (>4 GiB); S9+ firmware may keep only 32 bits (S8 donor 0124 did). Result was rc=0 then silence.
- What: `tools/star2lte/make-0136.py` inserted a `#if defined(STAR2LTE)` block into the 0125 patch hunk (SweetCPU::startCPU). It writes a 4-instruction trampoline plus the real entry to PA 0x89f00000 and passes that as the CPU_ON entry.
- Trampoline writes marker 0x7701 at +0x18 then jumps to the real entry. The kernel does NOT read the marker yet (no panic hunk to attach it to in 0125).
- 0x89f00000 is a CHOICE, not a measurement: inside the dead S-Boot payload tail (initrd 0x89000000-0x89fbb880). If the core still never starts, doubt this page first.
- Not done: dc cvac/ivac cache maintenance (secondary starts with caches off; the kernel only does dsb sy). PMU 0x16480000 steps stay off on purpose.
- CI build succeeded; flashing and result: pending.

- RESULT build 0136 (2026-11-07): no panic, Apple progress bar starts normally. Core 1 starts via the 0x89f00000 trampoline, so the S9+ PSCI CPU_ON entry is 32-bit (supported by this result, not directly read: no marker readback yet). Not yet checked: that cores 2-3 are alive, boot time vs the earlier cpus=1 baseline, whether it reaches the lock screen.

- CORRECTION (2026-11-07): the "core 1 starts" result above is WRONG. Log v22 shows "1/1 CPUs initialized": that run used default ARGS with cpus=1, and plain `s9.sh build` picks the newest kernel in xnu/out, not xnu/out-0136. The trampoline is still untested. Run with ARGS without cpus=1 and pass the xnu/out-0136 kernel explicitly.

- RESULT builds 0139/0140 (2026-11-07): panic "cpu=1 NOT alive after 10s ... S9FLAG=0x7701 EL=0x4". Core 1 reaches the low trampoline at 0x89f00000 (so the 32-bit CPU_ON entry theory holds) and wakes at EL1 (the EL2/ICC_SRE_EL2 suspect is out). It dies after the jump to 0x8c142a000: sweet_secondary_entry or LowResetVectorBase (MPIDR lookup for mpidr 0x1, or cache-coherency of kernel data read with MMU/caches off). WARNING: do not add lines to xnu/patches/0065 (build 0138 did, and broke 0112+ context). Put diagnostics in 0125.

- RESULT build 0141 (2026-11-07): S9FLAG=0x7703. Core 1 passes the whole sweet_secondary_entry EL1 path (markers 0x7702/0x7703, patch 0141) and dies at/after `b LowResetVectorBase`. Untested suspect: the reset code reads ResetHandlerData / cpu data entries with MMU+caches off, and the boot CPU never cleaned that data to the point of coherency, so core 1 reads zeros and hangs at `cbz x19`/`b .`.

## HANDOFF 2026-11-07 (core 1 bring-up, S9+)
**Goal**: start secondary cores so iOS boots faster (all rendering is on the CPU). User runs fish, is new to git/kernels, wants copy-paste commands only, short answers. Heredocs (<<) do not work in fish: type `bash`, paste, `exit`.
**Workflow**: edit patches via small python scripts in tools/star2lte/make-01NN.py, git push (CI builds the kernel), then fish function `s9go out-01NN [cpus]` (saved with funcsave; waits for the newest CI run, downloads into xnu/out-01NN, builds with s9.sh, flashes). Phone in TWRP. Boot-arg `cpus=N` is REQUIRED for SMP (default is 1 core). Kernel code needs CI; only boot-args/ADT/loader repack locally.
**Findings (measured)**:
- cpu=1 PSCI CPU_ON rc=0 but entry 0x8c142a000 is above 4 GiB; fix = low trampoline at PA 0x89f00000 (inside dead S-Boot initrd tail; a choice, not measured free). In patch 0125 (SweetCPU::startCPU, STAR2LTE block). It works: core 1 reaches it (marker 0x7701), wakes at EL1 (EL=0x4), passes sweet_secondary_entry (0x7703) and reaches reset_vector (bit 0x10).
- Core 1 then HANGS in reset_vector: it never finds its CPU data entry. Panic tail: S9FLAG=0x7f13 EL=0x4 D=c1bc5bd8,c2b19730,81000100 = (cpu_data_entries ptr, cpu1 entry paddr, MPIDR_EL1 of the woken core). Table is readable (cache theory ruled out).
- ROOT CAUSE (strong, one fix not yet tried): woken core has MPIDR_EL1=0x81000100, so low 16 bits = 0x0100. Kernel/ADT expect cpu1 phys_id=0x1. reset_vector compares MPIDR&0xFFFF with cpu_phys_id from the ADT. So core 1 is really MPIDR 0x100 (Aff1=core); cores 2,3 probably 0x200,0x300 (UNMEASURED). Boot CPU is 0x81000000 (0x0).
**NEXT STEP**: make the A55 cores use MPIDR 0x0,0x100,0x200,0x300: (a) tools/mkadt_star2lte.py: in `cpu_order`/A55 base use core<<8 for the A55 cluster (cpu_node reg=mpidr); (b) patch 0125 expected_mpidr line (~lines 56-61: boot_cluster + cpu->cpu_id must become boot_cluster + (cpu->cpu_id<<8) for the A55 cluster); (c) PSCI CPU_ON target (cpu->phys_id) then becomes 0x100, which firmware may or may not accept (Linux DTB for this phone is the reference; check). (d) SGI/IPI target in patch 0101 already uses full Aff1 (fine). Then `s9go out-01NN` with cpus=2.
**Diagnostics in tree (remove when done)**: 0125 S9FLAG panic (late startup-timeout panic in 0101/0115), 0141 (entry markers, may be superseded) and 0142-s9-reset-markers.patch (bit markers in reset_vector, writes PA 0x89f00020, data at 0x89f00030), make-0144.py. NEVER add lines to patch 0065 (build 0138 broke the context of 0112+). Put new start.s edits in a NEW patch generated with git against /tmp/xnu-orig (clone of xnu-8796.141.3; `git apply --check` it).
**Not verified**: cores 2-3 and M3 cores 4-7, whether firmware accepts CPU_ON target 0x100, lock screen, performance gain.

## HANDOFF 2026-11-07 (evening) - core 1 bring-up, S9+

### Done
- 0145 (core MPIDR): ADT uses MPIDR_EL1 numbering (A55 core n = n<<8, Aff1); PSCI target converted with
  SWEET_PSCI_TARGET (A55 0..3, M3 0x100..). Result: cpu 1 wakes via low trampoline 0x89f00000, passes
  reset_vector, prints "cpu 1 online", GIC lines, "cpu=1 entered initCPU mpidr=0x100".
- 0146 v2 (diag): "Ticket lock unexpectedly owned" panic prints thread, ctid, owner and 6 return addresses.
- 0147 (diag): every cpu kprintf's SCTLR/TCR/MAIR/TTBR1/ACTLR in initCPU.
- 0148 (diag): boot-arg s9nocpuon=1 makes startCPU skip PSCI CPU_ON. make-0148.py written and syntax-checked;
  NOT yet run by the user, so patch 0148 may not exist in the repo yet.

### Open problem
With cpus=2, panic "Ticket lock ... unexpectedly owned" (lock_ticket.c:155), ctid == lock owner.
- Seen on cpu 0 (lock = _pset0 at 0xfffffff007b74880) and on cpu 1 (lock 0xfffffff03ba48100, probably a
  dynamic pset for cluster 1; pset_find(cluster_id=1) returned -1 in the log).
- Stack is always lck_ticket_contended <- thread_select <- thread_block_reason <- Call_continuation.
- On cpu 1 the owner equals cpu 1's own thread (0x7b6bc) on a freshly created lock: unexplained.
- No Sweet patch calls pset_lock/pset_unlock (grep empty); processor_startup balances lock/unlock.
- Hypotheses, both UNPROVEN: (a) cache coherency / memory attributes / SMPEN on cpu 1;
  (b) scheduler/pset bookkeeping with a second registered CPU in a cluster with no pset.

### Last state (what went wrong at the end)
The last test photos came from a STALE kernel: no s9nocpuon line, no 0147 SCTLR line, CPU_ON still called,
bt present => it is the 0146 v2 build. Cause not found; earlier the same thing happened with out-0146 (old kernel
left in the folder). The 0148 test has therefore NOT been done.

### NEXT STEP
1. User runs: python3 tools/star2lte/make-0148.py WORK2 ; commit; push; sleep 2 && gh run watch.
2. gh run download RUNID -n xnu-kernel -D xnu/out-0149 (fresh folder).
3. VERIFY before flashing: grep -a -c 's9nocpuon' and grep -a -c 'SCTLR=%llx' on the kernel; both must be >= 1.
4. Boot cpus=2 with s9nocpuon=1 added to ARGS. Flash only the verified file; check the photo shows the
   "s9nocpuon: NOT calling PSCI CPU_ON" line.
5. Interpret: ticket-lock panic gone (probably a processor-start timeout instead) => needs cpu 1 hardware
   activity, investigate coherency (compare cpu 0/1 SCTLR/TCR/MAIR/ACTLR/CPUECTLR). Panic still present =>
   bookkeeping: look at the missing cluster-1 pset / processor registration, pset init for cluster 1.
6. If cpu 1 ever prints its register line, compare with cpu 0 (cpu 0: TCR=22a5192519 MAIR=c08044f080bb44ff
   TTBR1=8c28b1000; SCTLR read from a blurry photo).

### Other open items
- sweetfb_noconsole=1 does not stop console text overlaying the iOS screen after the progress bar; look at
  a5xelte patches 0109/0110 (suspected override), 0046/0067. Unknown whether the 1-core run reached iOS.
- Cores 2-3 and M3 MPIDRs unmeasured (M3 0x400.. is a placeholder). Test cpus=4 only after cpus=2 works.

### User notes
Uses fish. Wants copy-paste commands. Use "sleep 2 && gh run watch" after pushes. Downloads with -n xnu-kernel
land directly in the folder; sym.sh: bash tools/dreamlte/sym.sh KERNEL ADDR... Keep replies short.

## 2026-11-07 night: cores 0-3 (A55) start on the S9+ (user-reported + log v27)
- Cause of the "Ticket lock unexpectedly owned" panic: with core MPIDRs 0x0/0x100/0x200/0x300 XNU derived the logical cluster from MPIDR Aff1 and created extra clusters without a pset. Patch 0149 (make-0149.py): cluster-id from the ADT (A55 = 0), every core's physical Aff1 registered in cluster_phys_to_logical. Patch 0150: MAX_CPU_CLUSTER_PHY_ID = 7 for A5XELTE (default 1, assertion failed for cpus=4).
- RESULT: cpus=2 log v27: cpu 0/1 "came alive; SGI1 OK", "2/2 CPUs initialized". cpus=4 (build out-0151): user reported cpu 0-3 start. Boot-time gain not measured yet.
- NOT done: M3 cores 4-7 (MPIDR 0x400.. and PSCI targets are placeholders), lock screen, performance.
- Workflow notes: WORK2 is stale (patches up to 0142); WORK3 = WORK2 + 0145-0148 and is the tree to diff against. fish `ls` is aliased (no -t), use explicit file names.

## HANDOFF 2026-11-07 (night) - A55 cores 0-3 run; M3 cores 4-7 do not start yet

**Goal / user rules:** boot iOS faster on the S9+ by starting more CPU cores (all rendering is on the CPU). User runs fish on Arch, is new to git/kernels: give copy-paste commands with expected output; short replies; `mv` for new files; heredocs (`<<`) do not work in fish (type `bash`, paste, `exit`, or give a file and use `cat file >> target`). Fish `ls` is aliased: `-t`/`--time=mtime` fail, use explicit names. Keep `AGENTS.md` rules: build / kernel marker / screen / iOS runtime are separate claims; no S8 address without a measurement; never edit shim/dreamlte, tools/dreamlte, DREAMLTE_PROGRESS.md, NOTES.md.

### Done (user-reported photos/logs, S9+ device)
- **cpus=4 works**: cores 0-3 (Cortex-A55, ADT MPIDR 0x0/0x100/0x200/0x300) "came alive; SGI1 OK", reaches the Apple logo (kernel `xnu/out-0151`, args from `s9go ... 4`). Boot time vs the ~50 min 1-core baseline NOT measured yet. Lock screen not reached in any run so far; frames from iOS are still opaque black (FBDIAG nonblack 0/64).
- **Root cause of the "Ticket lock unexpectedly owned" panic (0145 era):** XNU `ml_parse_cpu_topology` derives the logical cluster from MPIDR Aff1, so 4 cores with Aff1 0..3 became 4 clusters. Fixed by **0149** (`tools/star2lte/make-0149.py`, machine_routines.c: cluster-id from ADT, every core's Aff1 registered in `cluster_phys_to_logical`) and **0150** (`make-0150.py`, board_config.h: `MAX_CPU_CLUSTER_PHY_ID 7` for A5XELTE; default was MAX_CPU_CLUSTERS-1 = 1, assertion `machine_routines.c:1058` failed for cpus=4).
- **Local ADT edits in `tools/mkadt_star2lte.py`** (no CI needed; check `git status`, commit was requested): M3 nodes now also get `arm,cortex-a53` in `compatible` (else SweetCPU never registers them: "cpu=4 NOT registered"), and `cluster-id` is 0 for ALL cores (one pset).
- `s9go` (fish function, funcsave'd) now reuses `xnu/NAME` if it holds a kernel; third arg `fresh` forces a CI re-download.

### M3 (cpu 4-7) findings
- With cluster-id 1 for the M3 node: `pset_find(cluster_id=1) returned -1` is normal (pset gets created), but the `_pset0` ticket-lock panic returns as soon as a cluster-1 processor registers. Hypothesis (unproven): this build is not `__AMP__`, two psets under pset_node0 break the scheduler. Workaround in use: all 8 cores in logical cluster 0.
- With one pset, `cpus=5`: cpu 4 registers (pset 0), `CPU_ON target=0x400` (ADT MPIDR, placeholder) -> `SWEET_PSCI_TARGET` converts to PSCI target 0x100 -> firmware `rc=0` -> `cpu=4 NOT alive after 10s`, `S9FLAG=0x0 EL=0x0`: the core never reached the low trampoline (marker word cleared before CPU_ON, written by trampoline). The 3rd D value 0x81000300 is probably stale from core 3 (unverified). Real M3 MPIDR_EL1 still UNKNOWN (placeholder 0x400+).
- Device facts (star2lte-facts/live.dts, measured on the phone running Linux): A55 cpu@0..3 (implementer 0x41 part 0xd05), Meerkat/M3 cpu@0x100..0x103 (`arm,meerkat`, implementer 0x53 part 0x002), PSCI via smc, cpu_on 0xc4000003. PMU syscon `samsung,exynos9810-pmu` at **0x14060000** size 0x10000 (the S8 value 0x16480000 in donor code is wrong for the S9+; PMU steps stay disabled for STAR2LTE). DT has no CPU power offsets.
- TWRP limits: no busybox, no /dev/mem (CONFIG_DEVMEM unset), PMU not in regmap debugfs. `mount -t debugfs none /sys/kernel/debug` works. Debugfs has `acpm_framework`, `flexpmu-dbg/{cpu_status,cur_sequence,lpm_count,mif_always_on,seq_count,seq_status,sw_flag}`, `exynos-pd` (only peripheral domains: aud, dpu, dspm, dsps, embedded_g3d, g2d, isphq, isplp, isppre, iva, mfc, vts: no CPU cluster), `exynos-pm`. Suggests CPU/cluster power is sequenced by FlexPMU/ACPM firmware (inference from names).

### NEXT (in order; SUPERSEDED by the 2026-11-08 section at the top, kept for the TWRP measurement ideas)
1. Free measurement in TWRP: `adb shell 'mount -t debugfs none /sys/kernel/debug; cat /sys/kernel/debug/flexpmu-dbg/cpu_status'` with all 8 online, then offline cpu4-7 (`echo 0 > /sys/devices/system/cpu/cpuN/online`), cat again, diff; also read seq_status/sw_flag. Save under star2lte-facts/pmu/.
2. Diagnostic kernel patch (new patch 0151, generated with git against WORK3/xnu, NOT in 0065): after CPU_ON for cpu >= 4 log PSCI AFFINITY_INFO (0xc4000004, target 0x100) a few times over the 10 s: 0 ON (dies before trampoline: entry/EL/cache), 2 ON_PENDING (firmware waiting: cluster power), 1 OFF (never started). Also try other PSCI targets for cpu 4.
3. Only then think about M3 power-up; do not reuse S8 PMU offsets. Real M3 MPIDR comes from the panic tail `D=` once a core runs.
4. Measure the 4-core boot time (progress bar vs ~50 min on 1 core) before spending more on M3.
5. Other open items: console text still overlays iOS despite `sweetfb_noconsole=1` (see a5xelte patches 0109/0110, 0046/0067); iOS draws black; AKS selectors 2/3/6/31/34/93 unsupported; fairplayd/bluetoothd respawn loop fills the 4 MiB log ring; RAM window 768 MiB.

### Workflow / commands
- Tree to diff patches against: `WORK3/xnu` (= WORK2 + patches 0145-0148 committed; WORK2 alone is stale at 0142). Generate: `python3 tools/star2lte/make-01NN.py WORK3/xnu (pwd)/xnu/patches/01NN-name.patch`, `cat` it, then `git add ...; git commit -m ...; git push; sleep 2 && gh run watch`. CI kernel build ~9 min.
- Test: phone in TWRP, `s9go out-0151 N` (N = cpus; boot-args are inside s9go; `cpus=` is required for SMP). `cpus=5` currently panics (cpu 4 timeout): use `cpus=4` as the working setup. After boot: TWRP (Power+Vol Down, then Power+Bixby+Vol Up), `bash tools/star2lte/s9.sh pull` (writes logs/sweetlog-vNN.txt; read the version it prints), `grep -a 'came alive\|CPUs initialized\|NOT alive' logs/sweetlog-vNN.txt`.
- Verify a kernel before flashing when in doubt: `grep -a -c 'STRING' xnu/out-NNNN/kernel.development.a5xelte`. Stale-kernel mix-ups caused earlier false results.
- Never add lines to xnu/patches/0065 (broke 0112+ context in build 0138).
## HANDOFF: star2lte touch (written from the chat; STAR2LTE_PROGRESS.md and NOTES.md not re-read)

### Goal
Working touch on the S9+ (star2lte). Kernel 0162+, 8 cores, iOS 16.7.16 reaches the home screen. No real touch yet.

### Standing user rules
- Very small copy-paste answers. Fish shell: no heredocs, quote globs.
- New files arrive in ~/Downloads, user moves them with mv. Always `source` a fish function after mv, never funcsave.
- Confirm every destructive step (USERDATA write).
- Keep build / kernel marker / screen / iOS runtime as separate claims; say what is untested.
- Boot test: `s9go out-NNNN 8 a5fb_keep_on=1 sweethidtest=20 <new args>`, then `s9pull; grep -a ... $L`.
- Image workflow: `s9delta -p` BEFORE editing the image, edit, then `s9delta`.
- Generators: tools/star2lte/make-NNNN.py on a clean tree. Donor files (shim/dreamlte, tools/dreamlte, DREAMLTE_PROGRESS.md, NOTES.md, S8 addresses) are not to be reused without a measurement.

### Done
- 0163 tap injector: boot-arg `sweettap=x,y,secs` calls sweet_hid_touch (xnu/patches/0058, SweetHID.cpp). In tree and tracked. Reported working on device (observed by the previous agent, not re-verified). Coordinate range is not checked in 0058.
- Commit labels: top two commits in WORK3 are both named "0162"; one is really 0163. Content right, CI ignores labels, only patch files matter.
- 0164 s9survey: tools/star2lte/make-0164.py + xnu/patches/0164-star2lte-survey.patch, pushed. Survey thread starts from a5xelte_touch_probe. Levels: 1 = always-on (AON) dump + button diffs (~150 s watch loop), 2 = I2C probe of 0x48 (touch chip), planned 3 = more. The previous agent said "S9SURVEY count 15", stub build + fake-tree test passed; CI result of 0164 not seen by me.
- Untracked, optional to commit separately: s9delta.fish, s9pull.fish, skip-setup.sh. Do NOT git add WORK2/ or WORK3/ (huge).

### Result of the 0164 boot (observed from a photo, 20261108_164208.jpg)
- Kernel panic right after `S9SURVEY: start level 1`; the next line (USI modes) never appeared.
- esr 0x96000010 = synchronous external abort on a data access. FAR ends ...43e004, x22 = ...43e000 (virtual, pages mapped AON, pin, USI in that order).
- Guess (fairly strong): the first read was USI base+4 (0x10411004); the whole 0x104xxxxx peripheral block (USI, gpp1 pins, hsi2c@104B0000) is not powered/clocked when S-Boot hands over. Not confirmed by a symbol lookup.
- Consequence: the level 1 and 2 reads must not touch 0x104xxxxx. The AON block (0x14050000) is not known to fault.

### Next
1. 0165 (the previous agent said it was writing it, make-0165.py, output not seen; check ~/Downloads and the tree first): level 1 reads ONLY AON (0x14050000) for the button survey. All 0x104xxxxx reads (USI modes, gpp1 pins, hsi2c, I2C 0x48 probe) go to a later level 3, off by default.
2. Boot `s9go out-0165 8 fresh a5fb_keep_on=1 s9survey=1`. Start pressing at the first Apple logo, one key at a time, ~3 s each, 5 s apart: vol up, vol down, Bixby, power (release power before 7 s). User states the order. Then `s9pull; grep -a 'S9SURVEY' $L | cut -c1-150 | head -80`. Check `grep -a 'S9SURVEY AON' $L | wc -l` (0 or few = window closed; stretch loop and add uptime stamps).
3. Touch plan: the peripheral block must be clocked/powered first (ACPM IPC channel 2 / speedy@141C0000, PMIC s2mps18mfd + s2mpb03, rails tsp_io / tsp_avdd). Do not touch 0x104xxxxx again without a fault-safe read or a measured gate. Then probe 0x48 (sec_ts, IRQ gpio <0x6c 0 0>), then a polled sec_ts driver feeding sweet_hid_touch.

### Risks
- A peripheral read can panic the kernel (just happened). Each survey level must say in its log what it touches.
- Everything about touch hardware reachability is untested.
