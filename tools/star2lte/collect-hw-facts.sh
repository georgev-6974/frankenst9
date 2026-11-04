#!/bin/bash
# Collect Galaxy S9+ (SM-G965F, star2lte) hardware facts from TWRP over adb.
# Read-only. Output stays local (dumps/serials must not be committed).
#   collect-hw-facts.sh [OUTDIR] [--boot-backup] [--mmio]   (default dir: ./star2lte-facts)
#   --boot-backup  also copy sda10 (BOOT) to OUTDIR/boot-sda10.img. READ-ONLY, and
#                  it is the STOCK_BOOT input of tools/star2lte/make-boot.sh: keep it safe.
#   --mmio         also read (never write) the DECON_F/DSIM/UFS register windows with
#                  devmem; a read of a clock-gated block can hang TWRP, so it is opt-in.
set -u
out=star2lte-facts; bb=0; mm=0
for a in "$@"; do case $a in --boot-backup) bb=1;; --mmio) mm=1;; *) out=$a;; esac; done
mkdir -p "$out"
adb get-state >/dev/null 2>&1 || { echo "no adb device (boot TWRP, check USB/adb devices)"; exit 1; }
sh() { adb shell "$1" 2>&1; }
sh 'getprop ro.product.device; getprop ro.boot.bootloader' > "$out/ident.txt"
sh 'cat /proc/cpuinfo'            > "$out/cpuinfo.txt"
sh 'cat /proc/iomem'              > "$out/iomem.txt"
sh 'cat /proc/cmdline'            > "$out/cmdline.txt"
sh 'ls -l /dev/block/platform/*/by-name/ 2>/dev/null || ls -l /dev/block/by-name' > "$out/partitions.txt"
sh 'ls /sys/devices/system/cpu/' > "$out/cpus.txt"
adb pull /sys/firmware/fdt "$out/live.dtb" >/dev/null 2>&1
adb pull /sys/firmware/devicetree/base "$out/dt-base" >/dev/null 2>&1
sh 'cat /sys/module/ramoops/parameters/* 2>/dev/null; ls /sys/fs/pstore' > "$out/pstore.txt"
sh 'dmesg | grep -iE "bootloaderfb|s3cfb|gic|psci|ramoops|arch_timer|decon|ufs" | head -60' > "$out/dmesg-key.txt"
sh 'for p in sda9 sda10 sda11 sda25; do echo "$p $(blockdev --getsize64 /dev/block/$p 2>&1)"; done' > "$out/part-sizes.txt"
sh 'cat /proc/device-tree/reserved-memory/*/reg 2>/dev/null | od -An -tx1 | head -40; ls /proc/device-tree/reserved-memory' > "$out/reserved-memory.txt"
sh 'cat /proc/meminfo | head -3; cat /proc/version; getprop ro.boot.em.model' > "$out/misc.txt"
sh 'dmesg | grep -iE "cc000000|fb_base|framebuffer|bootloaderfb|sec_debug|log_pstore|debug-snapshot|dss" | head -40' > "$out/dmesg-fb-debug.txt"
sh 'ls /sys/devices/platform/ | head -200' > "$out/platform-devs.txt"
if [ $bb = 1 ]; then
  adb shell 'dd if=/dev/block/sda10 2>/dev/null' > "$out/boot-sda10.img" && sha256sum "$out/boot-sda10.img" > "$out/boot-sda10.sha256"
fi
if [ $mm = 1 ]; then
  for w in 16030000:0x100 16050000:0x40 16080000:0x40 11120000:0x40 11121100:0x40; do
    a=${w%%:*}; n=$(( ${w##*:} ))
    { echo "# window 0x$a +$n"
      i=0; while [ $i -lt $n ]; do printf "%x " $((0x$a + i)); adb shell "devmem $((0x$a + i)) 32 2>&1 || busybox devmem $((0x$a + i)) 32 2>&1"; i=$((i+4)); done; } >> "$out/mmio.txt"
  done
fi
echo "done -> $out"; command -v dtc >/dev/null && dtc -I dtb -O dts "$out/live.dtb" > "$out/live.dts" 2>/dev/null
