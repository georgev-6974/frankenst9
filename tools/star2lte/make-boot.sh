#!/bin/bash
# Kernel Mach-O -> Galaxy S9+ BOOT image (sda10). UNTESTED on hardware.
#   make-boot.sh KERNEL STOCK_BOOT.img OUT.img [--boot-mpidr 0x..] [-- boot-args...]
# STOCK_BOOT = a backup of the phone's own sda10 (header + DTB source).
# Never writes to a device; flashing is a separate, user-confirmed step.
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
kernel=$(realpath "$1"); stock=$(realpath "$2"); out=$(realpath -m "$3")
shift 3
mpidr=0x0
if [ "${1:-}" = --boot-mpidr ]; then mpidr=$2; shift 2; fi
[ "${1:-}" = -- ] && shift
# One CPU, verbose, no watchdog. No a5touchprobe/touch yet: the S9+ touch and
# PMIC (ACPM) paths are unported, so the first trials end in a root-mount panic.
args=${*:-debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam -noprogress wdt=-1 wdt_test=no_user_checkin a5touchprobe=0}
work=$repo/shim/star2lte/out
mkdir -p "$work"
python3 -I "$repo/tools/mkadt_star2lte.py" "$work/star2lte.adt" --canvas 1440x2960 --boot-mpidr "$mpidr"
python3 -I "$repo/tools/mkpayload.py" "$kernel" "$work/star2lte.adt" "$work/payload.bin" --cmdline "$args"
bash "$repo/shim/star2lte/build.sh" "$stock" "$work/payload.bin" "$out"
python3 -I "$repo/tools/dreamlte_bootimg_info.py" "$out" | head -4
