#!/usr/bin/env python3
# Probe V100 VRAM through the BAR0 PRAMIN window (GPU-internal, no BAR1/PCIe window involved)
# plus a few FB/priv registers. Safe to run with or without nvidia.ko loaded (reads, plus one
# save/write/restore at the probe addresses). Usage: vram-probe.py [label]
import mmap, os, struct, sys

DEV = "/sys/bus/pci/devices/0001:01:00.0/resource0"
fd = os.open(DEV, os.O_RDWR | os.O_SYNC)
m = mmap.mmap(fd, 0x1000000, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
rd = lambda o: struct.unpack_from("<I", m, o)[0]
wr = lambda o, v: struct.pack_into("<I", m, o, v)

print("==", sys.argv[1] if len(sys.argv) > 1 else "probe")
for name, off in [("PMC_BOOT_0", 0x0), ("PMC_ENABLE", 0x200), ("PMC_INTR_0", 0x100),
                  ("PBUS_INTR_0", 0x1100), ("MMU_LOCAL_MEMORY_RANGE", 0x100ce0),
                  ("NISO_FLUSH_SYSMEM_ADDR", 0x100c10), ("PRIV_RING_INT_STATUS0", 0x120058),
                  ("SYS_PRIV_ERROR_ADR", 0x122120), ("SYS_PRIV_ERROR_CODE", 0x12212c),
                  ("PMU_FALCON_CPUCTL", 0x10a100), ("PBUS_BAR1_BLOCK", 0x1704),
                  ("PBUS_BAR2_BLOCK", 0x1714)]:
    print(f"{name:24s} +{off:#08x} = {rd(off):#010x}")

old = rd(0x1700)  # NV_PBUS_BAR0_WINDOW (vidmem addr >> 16, target 0 = VID_MEM)
ok = 0
for addr in [0x0, 0x100000, 0x40000000, 0x200000000, 0x7fff00000]:
    wr(0x1700, addr >> 16); rd(0x1700)
    p = 0x700000 + (addr & 0xffff)
    sv = rd(p); wr(p, 0x5a5aa5a5); r = rd(p); wr(p, sv)
    good = r == 0x5a5aa5a5
    ok += good
    print(f"vidmem {addr:#012x}: was {sv:#010x}, write test {'OK' if good else f'FAIL (read {r:#010x})'}")
wr(0x1700, old)
print(f"VRAM {'WORKS' if ok == 5 else 'BROKEN'} ({ok}/5)")
