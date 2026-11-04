#!/bin/bash
# One-stop helper for the S9+ trials. Run from the project folder:
#   bash tools/star2lte/s9.sh build [KERNELFILE]   make out.img (newest file in xnu/out if omitted)
#   bash tools/star2lte/s9.sh flash [IMG]          write IMG (default out.img) to BOOT sda10, verify, reboot
#   bash tools/star2lte/s9.sh pull [NAME]          pull + decode logs into logs/ (NAME default: next free vN)
#   bash tools/star2lte/s9.sh restore              put the stock BOOT backup back (phone boots Android again)
# build/pull/flash/restore need the phone in TWRP (adb devices must list it) except build.
# Override boot-args:  ARGS="..." bash tools/star2lte/s9.sh build
set -euo pipefail
trap 'echo "s9.sh: FAILED at line $LINENO: $BASH_COMMAND" >&2' ERR
cd "$(dirname "$0")/../.."
STOCK=${STOCK:-star2lte-facts/boot-sda10.img}
BACKUP=${BACKUP:-$HOME/s9-backup/boot-sda10.img}
MAXSZ=57671680
MPIDR=${MPIDR:-0x0}    # your phone: MPIDR_EL1=0x81000000 -> affinity 0x0
ARGS=${ARGS:-debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam -noprogress wdt=-1 wdt_test=no_user_checkin a5touchprobe=0 rd=ufsroot0 ufsroot=USERDATA ufslogsecs=2 startup_debug=1}

need_adb() { [ "$(adb get-state 2>/dev/null)" = recovery ] || { echo "Phone must be in TWRP and listed by 'adb devices' (state 'recovery')."; exit 1; }; }

cmd=${1:-}; shift || true
case $cmd in
build)
  k=${1:-$(ls -t xnu/out/* 2>/dev/null | head -1)}
  [ -f "$k" ] || { echo "no kernel file found in xnu/out (give it as an argument)"; exit 1; }
  echo "kernel: $k"; echo "boot-args: $ARGS"
  bash tools/star2lte/make-boot.sh "$k" "$STOCK" out.img --boot-mpidr "$MPIDR" -- $ARGS
  sz=$(stat -c %s out.img); echo "out.img = $sz bytes (limit $MAXSZ)"
  [ "$sz" -le "$MAXSZ" ] || { echo "TOO BIG, do not flash"; rm -f out.img; exit 1; }
  echo "OK. Next: bash tools/star2lte/s9.sh flash"
  ;;
flash)
  img=${1:-out.img}; [ -f "$img" ] || { echo "$img not found: run build first"; exit 1; }
  sz=$(stat -c %s "$img"); [ "$sz" -le "$MAXSZ" ] || { echo "image too big"; exit 1; }
  need_adb
  echo "About to write $img ($sz bytes) to BOOT (sda10). Recovery, EFS and bootloaders are not touched."
  echo "A stock backup must exist: $BACKUP"; [ -f "$BACKUP" ] || { echo "backup missing, stop"; exit 1; }
  read -r -p "Type yes to flash: " a; [ "$a" = yes ] || { echo aborted; exit 1; }
  adb push "$img" /tmp/boot.img
  adb shell "dd if=/tmp/boot.img of=/dev/block/sda10 bs=1048576 conv=fsync; sync"
  want=$(sha256sum "$img" | cut -d' ' -f1)
  got=$(adb exec-out "dd if=/dev/block/sda10 bs=4096 count=$(( (sz + 4095) / 4096 )) 2>/dev/null" | head -c "$sz" | sha256sum | cut -d' ' -f1)
  [ "$want" = "$got" ] && echo "verified: sda10 matches $img" || { echo "VERIFY FAILED ($want vs $got): do NOT reboot, tell the assistant"; exit 1; }
  read -r -p "Reboot into it now? (yes/no): " a; [ "$a" = yes ] && adb reboot
  echo "Watch the screen. After a few minutes (or a panic) force TWRP: POWER+VOL DOWN, then POWER+BIXBY+VOL UP."
  ;;
restore)
  need_adb; [ -f "$BACKUP" ] || { echo "backup $BACKUP missing"; exit 1; }
  read -r -p "Write the stock BOOT backup back to sda10? Type yes: " a; [ "$a" = yes ] || exit 1
  adb push "$BACKUP" /tmp/b.img
  adb shell "dd if=/tmp/b.img of=/dev/block/sda10 bs=1048576 conv=fsync; sync" && echo "restored; 'adb reboot' boots Android"
  ;;
pull)
  need_adb; mkdir -p logs
  if [ -n "${1:-}" ]; then name=$1; else
    last=$(ls logs/ldrlog-v*.bin logs/sweetlog-v*.bin 2>/dev/null | sed -E 's/.*-v([0-9]+)\.bin/\1/' | sort -n | tail -1)
    name=v$(( ${last:-0} + 1 )); echo "using name $name (logs/ldrlog-$name.*)"
  fi
  # Stream straight to the PC (no /tmp on the phone, no shell-specific syntax).
  bytes=$(adb shell 'blockdev --getsize64 /dev/block/sda25' | tr -d '\r\n ')
  n=$(( bytes / 4096 )); echo "sda25: $bytes bytes = $n blocks"
  adb exec-out "dd if=/dev/block/sda25 bs=4096 skip=$(( n - 1025 - 64 )) count=64 2>/dev/null" > "logs/ldrlog-$name.bin"
  adb exec-out "dd if=/dev/block/sda25 bs=4096 skip=$(( n - 1025 )) count=1025 2>/dev/null" > "logs/sweetlog-$name.bin"
  [ "$(stat -c %s "logs/ldrlog-$name.bin")" = 262144 ] && [ "$(stat -c %s "logs/sweetlog-$name.bin")" = 4198400 ] || { echo "unexpected log sizes: check adb/TWRP"; ls -l logs/*-$name.bin; exit 1; }
  python3 -I tools/star2lte/ldrlog.py "logs/ldrlog-$name.bin" "logs/ldrlog-$name.txt" || true
  python3 -I tools/sweet-log.py "logs/sweetlog-$name.bin" "logs/sweetlog-$name.txt" || true
  echo "=== loader log (head) ==="; head -30 "logs/ldrlog-$name.txt" 2>/dev/null || true
  echo "=== kernel log (last 60 lines) ==="; tail -60 "logs/sweetlog-$name.txt" 2>/dev/null || echo "(no kernel log)"
  echo "Send me: the output above, or the files logs/*-$name.txt"
  ;;
*) sed -n 2,9p "$0"; exit 1;;
esac
