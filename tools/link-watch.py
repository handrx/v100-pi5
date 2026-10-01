#!/usr/bin/env python3
# READ-ONLY watcher (v4: + GPU config space via sysfs = over the link, answered by the GPU PCIe core, not host/PRI)
# (v3): GPU BAR0 regs + GPU PCIe link regs via the PCFG mirror (BAR0 0x88000, exp cap 0x78)
# + PMU falcon state + root-port (0001:00:00.0, exp cap 0xac) DevSta/LnkSta via sysfs config (local, no link traffic).
# No PRAMIN, no writes. Times = CLOCK_MONOTONIC = dmesg. Usage: link-watch.py out.txt [secs]
import mmap, os, struct, sys, time
fd = os.open("/sys/bus/pci/devices/0001:01:00.0/resource0", os.O_RDONLY | os.O_SYNC)
m = mmap.mmap(fd, 0x1000000, mmap.MAP_SHARED, mmap.PROT_READ)
rc = os.open("/sys/bus/pci/devices/0001:00:00.0/config", os.O_RDONLY)
gc = os.open("/sys/bus/pci/devices/0001:01:00.0/config", os.O_RDONLY)
gcr = lambda o: struct.unpack("<I", os.pread(gc, 4, o))[0]
rd = lambda o: struct.unpack_from("<I", m, o)[0]
rcr = lambda o: struct.unpack("<I", os.pread(rc, 4, o))[0]
P = 0x88000 + 0x78
regs = [("BOOT0", 0x0), ("ENABLE", 0x200), ("INTR0", 0x100), ("PBUS_INTR", 0x1100),
        ("G_LNKCTL_STA", P + 0x10), ("G_LNKCTL2", P + 0x30), ("G_DEVCTL_STA", P + 0x08),
        ("PMU_CPUCTL", 0x10a100), ("PMU_MB0", 0x10a040), ("PMU_MB1", 0x10a044), ("PMU_IRQSTAT", 0x10a008),
        ("FLT_STATUS", 0x100e60)]
rcregs = [("RC_DEVCTL_STA", 0xac + 0x08), ("RC_LNKCTL_STA", 0xac + 0x10), ("RC_LNKCTL2", 0xac + 0x30)]
out = open(sys.argv[1], "w", buffering=1); last = None
end = time.monotonic() + (float(sys.argv[2]) if len(sys.argv) > 2 else 90)
gcregs = [("GC_ID", 0x0), ("GC_CMD_STA", 0x4), ("GC_DEVCTL_STA", 0x78 + 0x08), ("GC_LNKCTL_STA", 0x78 + 0x10)]
names = [n for n, _ in regs] + [n for n, _ in rcregs] + [n for n, _ in gcregs]
while (t := time.monotonic()) < end:
    v = tuple(rd(o) for _, o in regs) + tuple(rcr(o) for _, o in rcregs) + tuple(gcr(o) for _, o in gcregs)
    if v != last:
        out.write(f"{t:10.4f} " + " ".join(f"{n}={x:08x}" for n, x in zip(names, v)) + "\n")
        last = v
    time.sleep(0.0005)
