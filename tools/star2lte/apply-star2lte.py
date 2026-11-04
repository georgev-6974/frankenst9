#!/usr/bin/env python3
"""Adapt a post-0124 (dreamlte/S8) xnu tree to the Galaxy S9+ (star2lte).

Run after patch 0124 has been applied to the A5XELTE-configured tree:

    apply-star2lte.py XNU_TREE

Scope of this first revision (matches the loader's first-trial safety rule in
STAR2LTE_PROGRESS.md): the kernel must not touch any S8-only address on the
S9+, and the S9+ facts that ARE measured are applied. Nothing here has been
built or run; the replacement anchors were checked only against the text that
patch 0124 adds (tools/star2lte/verify-apply.py).

Applied:
  * A5XELTE.h: STAR2LTE=1 (DREAMLTE stays 1 for the shared fb/timer/VA
    changes). Entry marker moves from the S8 pstore slot 0x920ff000 to loader
    RAM just above the LDRLOG buffer (0x8f013f000, outside XNU's window).
    A5_BOOT_MPIDR is read from the ADT (--boot-mpidr of mkadt_star2lte.py), so
    a different S-Boot boot cluster needs no kernel rebuild. Keys default off.
  * Logical CPU order follows the boot cluster (A55 0x0-0x3 first for boot
    MPIDR 0x0, M3 0x100-0x103 first for 0x100).
  * Off on STAR2LTE (S8 addresses, would hit unrelated or unmapped hardware):
    ramoops klog (0x92180000 is Linux RAM here, not a reserved zone), the
    S6SY761 touch + MAX77865 battery driver (USI/HSI2C/ALIVE), the Mongoose
    PMU/trampoline CPU_ON path (0x16480000), the DECON frame-done wait
    (0x12860000). dreamlte_battery_read() becomes a stub returning -1, so
    SweetBattery publishes its static fallback.
  * Unchanged on purpose: 'samsung,a5xelte*' / '/dreamlte-ufs' / 'a5xelte-fbcon'
    names (the ADT still uses them), physical-timer PPI 30, 0xcc000000 FB.

Not done (needs measurements, see STAR2LTE_PROGRESS.md): DECON_F trigger and
frame-done on 0x16030000, touch (sec_ts) and PMIC (ACPM), SMP on the S9+
(CPU_ON entry placement, PMU), keys GPIO bases.

Every replacement asserts its expected match count.
"""
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit(__doc__)
tree = Path(sys.argv[1])


def edit(rel, pairs):
    path = tree / rel
    text = path.read_text()
    for old, new, count in pairs:
        found = text.count(old)
        if found != count:
            raise SystemExit(f'{rel}: expected {count}x {old!r}, found {found}')
        text = text.replace(old, new)
    path.write_text(text)
    print(f'edited {rel}')


# ---------------------------------------------------------------- header
edit('pexpert/pexpert/arm64/A5XELTE.h', [(
    '#define A5_TOUCH_DEFAULT              1\n#endif\n',
    '#define A5_TOUCH_DEFAULT              1\n#endif\n'
    '\n'
    '/*\n'
    ' * Samsung Galaxy S9+ (SM-G965F, star2lte, Exynos 9810) build, layered on\n'
    ' * the DREAMLTE settings above (same 0xcc000000 1440x2960 framebuffer,\n'
    ' * GIC-400, 26 MHz physical timer PPI 14). Measured S9+ facts:\n'
    ' * docs/star2lte-facts, STAR2LTE_PROGRESS.md. Nothing here ran on a phone.\n'
    ' */\n'
    '#define STAR2LTE                      1\n'
    '#if defined(STAR2LTE)\n'
    '/* No ramoops on this TWRP: the entry marker lives in loader RAM just above\n'
    ' * the 63-block LDRLOG buffer (shim/star2lte/loader.c LDR_LOG_PHYS +\n'
    ' * 63 * 4096), in the high bank outside the XNU window. */\n'
    '#undef A5_ENTRY_MARKER_PHYS\n'
    '#define A5_ENTRY_MARKER_PHYS          0x8f013f000\n'
    '/* The boot CPU is whatever the ADT calls logical CPU 0 (the loader banner\n'
    ' * prints the real MPIDR_EL1; rerun make-boot.sh --boot-mpidr if it differs). */\n'
    '#undef A5_BOOT_MPIDR\n'
    '#define A5_BOOT_MPIDR                 (ml_get_topology_info()->boot_cpu->phys_id)\n'
    '#undef A5_KEYS_DEFAULT\n'
    '#define A5_KEYS_DEFAULT               0           /* S8 GPIO bases do not apply */\n'
    '#endif\n', 1)])

# ------------------------------------------------- touch / battery (S8 I2C)
edit('bsd/dev/a5xelte_touch.c', [
    ('#if defined(DREAMLTE)\n/*\n * Galaxy S8 I2C devices, polled',
     '#if defined(DREAMLTE) && !defined(STAR2LTE)\n/*\n * Galaxy S8 I2C devices, polled', 1),
    ('#endif /* DREAMLTE */\n',
     '#endif /* DREAMLTE */\n'
     '\n'
     '#if defined(STAR2LTE)\n'
     '/*\n'
     ' * S9+: the S6SY761/MAX77865 drivers above use S8 USI/HSI2C/ALIVE addresses\n'
     ' * and are compiled out. The S9+ touch is a sec_ts behind ACPM-managed\n'
     ' * rails and the fuel gauge is unported: no reading, so SweetBattery\n'
     ' * publishes its static fallback.\n'
     ' */\n'
     'int dreamlte_battery_read(unsigned *percent, unsigned *mv, int *ma,\n'
     '    int *external, int *charging, int *full);\n'
     'int\n'
     'dreamlte_battery_read(unsigned *percent, unsigned *mv, int *ma,\n'
     '    int *external, int *charging, int *full)\n'
     '{\n'
     '\t(void)percent; (void)mv; (void)ma; (void)external; (void)charging; (void)full;\n'
     '\treturn -1;\n'
     '}\n'
     '#endif /* STAR2LTE */\n', 1),
    ('#if defined(DREAMLTE)\n\tdreamlte_touch_start();   /* the A5 path below stays off */\n#endif\n',
     '#if defined(DREAMLTE) && !defined(STAR2LTE)\n'
     '\tdreamlte_touch_start();   /* the A5 path below stays off */\n#endif\n', 1),
])

# ------------------------------------------------------------ CPU / SMP
edit('iokit/Kernel/arm/SweetCPU.cpp', [
    # Logical order = boot cluster first; derived from the boot MPIDR.
    ('#if defined(DREAMLTE)\n\t/* Exynos 8895: logical 0..3 = A53 MPIDR 0x100..0x103 (boot cluster);\n',
     '#if defined(STAR2LTE)\n'
     '\t/* Exynos 9810: the boot cluster comes first (mkadt_star2lte.py). */\n'
     '\tuint32_t boot_cluster = A5_BOOT_MPIDR & 0x100U;\n'
     '\tuint32_t expected_mpidr = cpu->cpu_id < 4 ? boot_cluster + cpu->cpu_id :\n'
     '\t    (boot_cluster ^ 0x100U) + cpu->cpu_id - 4;\n'
     '#elif defined(DREAMLTE)\n'
     '\t/* Exynos 8895: logical 0..3 = A53 MPIDR 0x100..0x103 (boot cluster);\n', 1),
    # Mongoose PMU power-up + low trampoline: S8 only.
    ('#if defined(DREAMLTE)\n\t{\n\t\t/*\n\t\t * The entry is in the high RAM bank',
     '#if defined(DREAMLTE) && !defined(STAR2LTE)\n\t{\n\t\t/*\n\t\t * The entry is in the high RAM bank', 1),
])

# ---------------------------------------------------- framebuffer (DECON)
edit('iokit/Kernel/arm/SweetFramebuffer.cpp', [
    ('#if defined(DREAMLTE)\n/*\n * Boot 31 video: torn frames',
     '#if defined(DREAMLTE) && !defined(STAR2LTE)\n/*\n * Boot 31 video: torn frames', 1),
    ('#if defined(DREAMLTE)\n\tsweet_fb_wait_frame_done();\n#endif\n',
     '#if defined(DREAMLTE) && !defined(STAR2LTE)\n\tsweet_fb_wait_frame_done();\n#endif\n', 1),
])

# ------------------------------------------- klog in TWRP ramoops (S8 only)
edit('pexpert/arm/pe_serial.c', [
    ("#if defined(DREAMLTE)\n/*\n * Copy of the console in TWRP's ramoops pmsg zone",
     "#if defined(DREAMLTE) && !defined(STAR2LTE)\n/*\n * Copy of the console in TWRP's ramoops pmsg zone", 1),
    ('#if defined(DREAMLTE)\n\tklog_putc(c);\n#endif\n',
     '#if defined(DREAMLTE) && !defined(STAR2LTE)\n\tklog_putc(c);\n#endif\n', 1),
    ('#if defined(DREAMLTE)\n\tklog_init();\n#endif\n',
     '#if defined(DREAMLTE) && !defined(STAR2LTE)\n\tklog_init();\n#endif\n', 1),
])
