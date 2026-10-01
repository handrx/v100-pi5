#!/usr/bin/env python3
# READ-ONLY watcher for RM init: logs changes of a few PMC/bus/FB regs + the MMU fault latch.
# Never touches PRAMIN (a PRAMIN read while RM has the window on WPR raises an MMU REGION_VIOLATION
# fault) and never writes. Times are CLOCK_MONOTONIC = dmesg time. Usage: vram-watch.py out.txt [secs]
import mmap, os, struct, sys, time
fd = os.open("/sys/bus/pci/devices/0001:01:00.0/resource0", os.O_RDONLY | os.O_SYNC)
m = mmap.mmap(fd, 0x1000000, mmap.MAP_SHARED, mmap.PROT_READ)
rd = lambda o: struct.unpack_from("<I", m, o)[0]
regs = [("BOOT0", 0x0), ("PCFG_ID", 0x88000), ("ENABLE", 0x200), ("INTR0", 0x100), ("PBUS_INTR", 0x1100),
        ("LMR", 0x100ce0), ("BAR0WIN", 0x1700), ("PRIVRING", 0x120058),
        ("FLT_ADDR_LO", 0x100e4c), ("FLT_ADDR_HI", 0x100e50), ("FLT_INST_LO", 0x100e54),
        ("FLT_INFO", 0x100e5c), ("FLT_STATUS", 0x100e60)]
out = open(sys.argv[1], "w", buffering=1); last = None
end = time.monotonic() + (float(sys.argv[2]) if len(sys.argv) > 2 else 90)
while (t := time.monotonic()) < end:
    v = tuple(rd(o) for _, o in regs)
    if v != last:
        out.write(f"{t:10.4f} " + " ".join(f"{n}={x:08x}" for (n, _), x in zip(regs, v)) + "\n")
        last = v
    time.sleep(0.0005)
