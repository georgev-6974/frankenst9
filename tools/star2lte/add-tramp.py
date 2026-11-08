cat > tools/star2lte/add-tramp.py <<'E'
import re, sys
p = sys.argv[1]; s = open(p).read()
if 'TRAMP_PA' in s: sys.exit('already applied')
a1 = re.compile(r'(\t__builtin_arm_dsb\(DSB_SY\);\n)(\tint32_t rc = sweet_psci_cpu_on\(cpu->phys_id, entry, getCPUNumber\(\)\);)')
b1 = r'''#if defined(STAR2LTE)
	{
		const uint64_t TRAMP_PA = 0x89f00000ULL;
		static vm_offset_t tv;
		if (tv == 0) tv = ml_io_map(TRAMP_PA, 0x1000);
		volatile uint32_t *t = (volatile uint32_t *)tv;
		uint64_t real = (uint64_t)ml_static_vtop((vm_offset_t)&sweet_secondary_entry);
		static const uint32_t code[6] = { 0x100000C3, 0x528EE022, 0xB9000062, 0xD5033F9F, 0x58000081, 0xD61F0020 };
		for (int i = 0; i < 6; i++) t[i] = code[i];
		t[6] = 0; t[7] = 0; t[8] = (uint32_t)real; t[9] = (uint32_t)(real >> 32);
		__builtin_arm_dsb(DSB_SY);
		IOLog(CPU_PORT_NAME " CPU: cpu=%u tramp pa=0x%llx -> real entry 0x%llx\n", getCPUNumber(), TRAMP_PA, real);
		entry = (vm_offset_t)TRAMP_PA;
	}
#endif
'''
if len(a1.findall(s)) != 1: sys.exit('anchor 1 (dsb + rc line) not found exactly once')
s = a1.sub(lambda m: m.group(1) + b1 + m.group(2), s)
a2 = re.compile(r'^(\t+)(panic\(CPU_PORT_NAME " CPU: cpu=%u startup timeout)', re.M)
b2 = r'''#if defined(STAR2LTE)
	{
		vm_offset_t fv = ml_io_map(0x89f00000ULL, 0x1000);
		IOLog(CPU_PORT_NAME " CPU: cpu=%u tramp flag=0x%x (0x7701 = reached trampoline, 0 = never)\n", getCPUNumber(), ((volatile uint32_t *)fv)[6]);
	}
#endif
'''
if len(a2.findall(s)) == 1:
    s = a2.sub(lambda m: b2 + m.group(1) + m.group(2), s)
else:
    print('WARN: panic anchor not found, no flag readback added')
open(p, 'w').write(s); print('ok')
