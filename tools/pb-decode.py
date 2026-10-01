#!/usr/bin/env python3
# Decode a GPU pushbuffer segment from sysmem (CPU PA) via /dev/mem: pb-decode.py PA LEN
import mmap, os, struct, sys
pa, n = int(sys.argv[1], 0), int(sys.argv[2], 0)
fd = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)
base = pa & ~0xfff
m = mmap.mmap(fd, (pa - base + n + 0xfff) & ~0xfff, mmap.MAP_SHARED, mmap.PROT_READ, offset=base)
w = struct.unpack_from('<%dI' % (n // 4), m, pa - base)
ops = {1: 'INC', 3: 'NONINC', 4: 'IMMD', 5: 'ONEINC'}
i = 0
while i < len(w):
    h = w[i]; op = h >> 29; cnt = (h >> 16) & 0x1fff; sc = (h >> 13) & 7; mth = (h & 0xfff) * 4
    if op == 4:
        print("%04x: %08x sc%d IMMD   m=%04x val=%x" % (i * 4, h, sc, mth, cnt)); i += 1; continue
    if op not in ops or h == 0:
        print("%04x: %08x ?" % (i * 4, h)); i += 1; continue
    print("%04x: %08x sc%d %-6s m=%04x n=%d: %s" % (i * 4, h, sc, ops[op], mth, cnt, " ".join("%08x" % x for x in w[i + 1:i + 1 + cnt])))
    i += 1 + cnt
