#!/bin/bash
# Build the Galaxy S8 XNU loader (Samsung S-Boot "kernel" Image).
# Optionally pack a BOOT image: build.sh STOCK_BOOT.img PAYLOAD.bin OUT.img
# (PAYLOAD from tools/mkpayload.py; STOCK_BOOT supplies header and DTBH).
set -euo pipefail
cd "$(dirname "$0")"
# GCC cross toolchain if present, else clang + lld (verified to build clean).
# EXTRA_CFLAGS e.g. -DSTAR2LTE_S8_PROBES (off by default: S8 addresses).
if command -v aarch64-linux-gnu-gcc >/dev/null; then
	CC=aarch64-linux-gnu-gcc; P=aarch64-linux-gnu-
	LDX="-static -Wl,--build-id=none -Wl,--no-warn-rwx-segments -Wl,-N"
	EXTRA="-fno-tree-loop-distribute-patterns"
else
	CC="clang --target=aarch64-linux-gnu"; P=llvm-
	LDX="-fuse-ld=lld -static -Wl,--build-id=none -Wl,-N"
	EXTRA="-fno-builtin"
fi
OBJCOPY=${P}objcopy; READELF=${P}readelf; NM=${P}nm
CFLAGS="-O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector $EXTRA -march=armv8-a -Wall -Wextra -Werror ${EXTRA_CFLAGS:-}"
mkdir -p out
$CC $CFLAGS -c start.S -o out/start.o
$CC $CFLAGS -c loader.c -o out/loader.o
$CC $CFLAGS -c ../fdt.c -o out/fdt.o
$CC $CFLAGS -c ufs_probe.c -o out/ufs_probe.o
$CC $CFLAGS -c smp_probe.c -o out/smp_probe.o
$CC $CFLAGS -c touch_probe.c -o out/touch_probe.o
$CC $CFLAGS -c pmic.c -o out/pmic.o
$CC $CFLAGS -c display_probe.c -o out/display_probe.o
objs="out/loader.o out/fdt.o out/ufs_probe.o out/smp_probe.o out/touch_probe.o out/pmic.o out/display_probe.o"
# Runs wherever S-Boot puts it with no relocation pass.
abs=$($READELF -r $objs | grep -c ABS64 || true)
[ "$abs" = 0 ] || { echo "error: $abs absolute relocations" >&2; exit 1; }
$CC $CFLAGS $LDX -T loader.ld \
	out/start.o $objs -o out/loader.elf
$OBJCOPY -O binary out/loader.elf out/Image
size=$((16#$($NM out/loader.elf | awk '$3=="_end"{print $1}')))
truncate -s "$size" out/Image
echo "out/Image: $(stat -c %s out/Image) bytes"
if [ $# = 3 ]; then
	python3 ../../tools/dreamlte_mkboot.py "$1" out/Image "$2" "$3"
	sha256sum "$3"
fi
