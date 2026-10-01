#!/usr/bin/env python3
# Read-only BAR0 dump of the GV100 host/FIFO state: PFIFO interrupts, MMU fault status, engine and PBDMA status,
# enabled channels (PCCSR) and each PBDMA's GPFIFO/pushbuffer pointers. Safe with nvidia.ko loaded (reads only).
import mmap, struct

f = open('/sys/bus/pci/devices/0001:01:00.0/resource0', 'rb')
m = mmap.mmap(f.fileno(), 0x1000000, mmap.MAP_SHARED, mmap.PROT_READ)
r = lambda o: struct.unpack_from('<I', m, o)[0]

print("BOOT0 %08x PMC_INTR0 %08x PMC_ENABLE %08x PFIFO_INTR_0 %08x INTR_EN_0 %08x FLT_STATUS %08x" %
      (r(0), r(0x100), r(0x200), r(0x2100), r(0x2140), r(0x100e60)))
print("NR fault buf GET %08x PUT %08x  R fault buf GET %08x PUT %08x" % (r(0x100e2c), r(0x100e30), r(0x100e4c), r(0x100e50)))
for i in range(16):
    v = r(0x2640 + i * 8)
    if v:
        print("ENGINE_STATUS[%2d] %08x" % (i, v))
for i in range(16):
    v = r(0x3080 + i * 4)
    if v:
        print("PBDMA_STATUS[%2d] %08x" % (i, v))
for c in range(512):
    st = r(0x800004 + c * 8)
    if st & 1:
        inst = r(0x800000 + c * 8)
        print("CH %3d inst %08x (pa %010x) ccsr %08x status %x busy %d pbdma_flt %d eng_flt %d next %d" %
              (c, inst, (inst & 0xfffffff) << 12, st, (st >> 24) & 0xf, (st >> 28) & 1, (st >> 22) & 1,
               (st >> 23) & 1, (st >> 1) & 1))
for p in range(14):
    b = 0x40000 + p * 0x2000
    ch = r(b + 0x120)
    vals = dict(GP_PUT=r(b), GP_GET=r(b + 0x14), GP_FETCH=r(b + 0x50), GP_BASE=(r(b + 0x4c) << 32) | r(b + 0x48),
                GET=(r(b + 0x1c) << 32) | r(b + 0x18), PUT=(r(b + 0x60) << 32) | r(b + 0x5c),
                HDR=r(b + 0x84), M0=r(b + 0xc0), D0=r(b + 0xc4), INTR=r(b + 0x108), CHAN=ch)
    if any(vals[k] for k in ("GP_PUT", "GP_GET", "GET", "PUT", "INTR")):
        print("PBDMA %2d " % p + " ".join("%s=%x" % kv for kv in vals.items()))
