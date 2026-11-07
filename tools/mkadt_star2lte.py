#!/usr/bin/env python3
"""Build the Galaxy S9+ (SM-G965F, star2lte, Exynos 9810) ADT.

Forked from tools/mkadt_dreamlte.py. Every value below is either measured
(docs/STAR2LTE_PROGRESS.md "Hardware facts", TWRP live DT, 2026-11-04) or
marked ASSUMED; nothing here has run on a phone.

Measured:
  - GIC-400 (GICv2): GICD 0x10101000, GICC 0x10102000 (S8: 0x10201000/2000)
  - physical timer PPI 14 = INTID 30, 26 MHz
  - CPUs: cpu0-3 Cortex-A55 MPIDR 0x0-0x3; cpu4-7 Exynos M3 MPIDR 0x100-0x103
  - RAM: 4 GiB contiguous bank 0x880000000-0x97fffffff, BUT firmware reserves
    0x880000000-0x8a1c00000 (540 MiB, live DT /reserved-memory). XNU gets
    512 MiB at 0x8c0000000 (the size the S8 and A5 ports proved; the 39-bit VA
    layout panicked with more); 0x8f0000000+ stays the loader's log/DMA area.
  - UFS HCI 0x11120000, vendor block 0x11121100 (identical to the S8)
  - S-Boot framebuffer 0xcc000000 1440x2960 (user-reported, unverified)
ASSUMED / open:
  - Which cluster S-Boot boots on. --boot-mpidr picks it (default 0x0 = A55
    cluster); the loader banner prints MPIDR_EL1, rerun with the real value.
    Logical cpu0 must be the CPU XNU starts on.
  - Nominal clocks (A55 1.8 GHz, M3 2.7 GHz) are informational only.
Kernel-side names stay the ones patch 0124 matches ('samsung,a5xelte*',
node '/dreamlte-ufs', 'a5xelte-fbcon') until patch 0125 adds star2lte.
"""
import argparse
import os
import sys
from pathlib import Path

# make-boot.sh runs python3 -I (no script dir on sys.path): add it explicitly.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adt  # noqa: E402
import mkadt  # noqa: E402

DRAM_BASE = 0x8c0000000   # NOT 0x880000000: firmware-reserved there
DRAM_SIZE = 0x30000000
FB_PHYS, FB_W, FB_H = 0xcc000000, 1440, 2960
TIMEBASE = 26000000
IO_BASE = 0x10000000        # /arm-io ranges parent; reg values are offsets
GICD, GICC = 0x10101000, 0x10102000
UFS_HCI, UFS_VS = 0x11120000, 0x11121100

A55 = dict(name='arm,cortex-a55', cluster=0, base=0x0, mhz=1794000000)
M3 = dict(name='samsung,exynos-m3', cluster=1, base=0x400, mhz=2704000000)


def set_prop(node, name, value):
    for i, (key, flags, _) in enumerate(node.props):
        if key == name:
            node.props[i] = (key, flags, value)
            return
    node.props.append((name, 0, value))


def child(node, name):
    for candidate in node.children:
        if candidate.prop('name') == mkadt.cstr(name):
            return candidate
    raise ValueError(f'missing donor ADT node {name}')


def cpu_order(boot_mpidr):
    """Logical order: boot cluster first (cpu0 = the boot CPU)."""
    clusters = [A55, M3]
    if boot_mpidr >= 0x400:
        clusters.reverse()
    order = []
    for c in clusters:
        for core in range(4):
            order.append((c, c['base'] + (core << 8), core))  # SWEET_CORE_AFF1
    # put the exact boot CPU first, keep the rest in order
    order.sort(key=lambda e: e[1] != boot_mpidr)
    return order


def cpu_node(logical, cluster_info, mpidr, core):
    return [
        ('device_type', mkadt.cstr('cpu')),
        ('compatible', mkadt.cstr(cluster_info['name']) +
         (mkadt.cstr('arm,cortex-a53') if cluster_info is A55 else b'') +  # SweetCPU matches a53 (patch 0086)
         mkadt.cstr('ARM,v8')),
        ('reg', mkadt.u32(mpidr)),
        ('cpu-id', mkadt.u32(logical)),
        ('cluster-id', mkadt.u32(cluster_info['cluster'])),
        ('cluster-type', mkadt.u32(0)),
        ('die-cluster-id', mkadt.u32(cluster_info['cluster'])),
        ('cluster-core-id', mkadt.u32(core)),
        ('l2-cache-id', mkadt.u32(cluster_info['cluster'])),
        ('l3-cache-id', mkadt.u32(0)),
        ('state', mkadt.cstr('running' if logical == 0 else 'stopped')),
        ('timebase-frequency', mkadt.u32(TIMEBASE)),
        ('clock-frequency', mkadt.u32(cluster_info['mhz'])),
        ('bus-frequency', mkadt.u32(100000000)),
        ('memory-frequency', mkadt.u32(1794000000)),
        ('peripheral-frequency', mkadt.u32(TIMEBASE)),
        ('fixed-frequency', mkadt.u32(TIMEBASE)),
    ]


def build(canvas=(FB_W, FB_H), boot_mpidr=0x0):
    root = mkadt.build(seed=os.urandom(64), qemu=True)
    set_prop(root, 'compatible', mkadt.cstr('samsung,star2lte') +
             mkadt.cstr('samsung,a5xelte') + mkadt.cstr('samsung,exynos9810') +
             mkadt.cstr('AppleARM'))
    chosen = child(root, 'chosen')
    set_prop(chosen, 'dram-base', mkadt.u64(DRAM_BASE))
    set_prop(chosen, 'dram-size', mkadt.u64(DRAM_SIZE))
    set_prop(chosen, 'firmware-version', mkadt.cstr('star2lte-entry'))
    set_prop(chosen, 'system-firmware-version', mkadt.cstr('star2lte-entry'))

    cpus = child(root, 'cpus')
    order = cpu_order(boot_mpidr)
    cpu0 = child(cpus, 'cpu0')
    c, mpidr, core = order[0]
    for key, value in cpu_node(0, c, mpidr, core):
        if key != 'cpu-id':
            set_prop(cpu0, key, value)
    for logical, (c, mpidr, core) in enumerate(order[1:], start=1):
        cpus.children.append(mkadt.node(f'cpu{logical}', cpu_node(logical, c, mpidr, core)))

    arm_io = child(root, 'arm-io')
    set_prop(arm_io, 'device_type', mkadt.cstr('star2lte-io'))
    set_prop(arm_io, 'compatible', mkadt.cstr('samsung,exynos9810-io') + mkadt.cstr('arm-io'))
    set_prop(arm_io, 'ranges', mkadt.u64(0, IO_BASE, 0xf0000000))
    arm_io.children = [n for n in arm_io.children if n.prop('name') == mkadt.cstr('wdt')]
    arm_io.children.append(mkadt.node('gic', [
        ('compatible', mkadt.cstr('arm,cortex-a15-gic')),
        ('interrupt-controller', mkadt.cstr('master')),
        # Non-secure physical timer PPI 14 = INTID 30 (DT: use-physical-timer).
        ('virtual-timer-intid', mkadt.u32(30)),
        ('reg', mkadt.u64(GICD - IO_BASE, 0x1000, GICC - IO_BASE, 0x1000)),
    ]))
    arm_io.children.append(mkadt.node('disp0', [
        ('device_type', mkadt.cstr('display-subsystem')),
        ('compatible', mkadt.cstr('samsung,star2lte-display') +
         mkadt.cstr('samsung,a5xelte-display')),
        ('canvas-width', mkadt.u32(canvas[0])),
        ('canvas-height', mkadt.u32(canvas[1])),
    ]))
    root.children = [n for n in root.children if n.prop('name') not in
                     (mkadt.cstr('sweet-fbcon'), mkadt.cstr('sweet-ufs'))]
    root.children.append(mkadt.node('a5xelte-fbcon', [
        ('reg', mkadt.u64(FB_PHYS, FB_W * FB_H * 4)),
        ('width', mkadt.u32(FB_W)),
        ('height', mkadt.u32(FB_H)),
        ('stride', mkadt.u32(FB_W * 4)),
    ]))
    root.children.append(mkadt.node('dreamlte-ufs', [
        ('reg', mkadt.u64(UFS_HCI, 0x200, UFS_VS, 0x200)),
    ]))
    return root


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--canvas', default=f'{FB_W}x{FB_H}',
                        help='display size presented to iOS, WxH')
    parser.add_argument('--boot-mpidr', type=lambda v: int(v, 0), default=0x0,
                        help='MPIDR of the CPU S-Boot enters on (loader banner); '
                             'default 0x0 is a guess')
    args = parser.parse_args()
    blob = adt.serialize(build(tuple(int(v) for v in args.canvas.split('x')),
                               args.boot_mpidr))
    args.output.write_bytes(blob)
    print(f'{args.output}: {len(blob)} bytes (boot MPIDR {args.boot_mpidr:#x})')
