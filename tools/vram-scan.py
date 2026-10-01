#!/usr/bin/env python3
# Scan vidmem [start,end) via PRAMIN for dwords in [lo,hi] (e.g. PDE values pointing at given pages). RM must be dead/wedged.
# usage: vram-scan.py start end lo hi
import mmap,struct,sys,time
start,end,lo,hi=(int(x,0) for x in sys.argv[1:5])
f=open('/sys/bus/pci/devices/0001:01:00.0/resource0','r+b')
m=mmap.mmap(f.fileno(),0x1000000,mmap.MAP_SHARED,mmap.PROT_READ|mmap.PROT_WRITE)
r=lambda a: struct.unpack_from('<I',m,a)[0]
w=lambda a,v: struct.pack_into('<I',m,a,v)
old=r(0x1700); t=time.time(); hits=0
for win in range(start>>16,end>>16):
    w(0x1700,win); r(0x1700)
    for o in range(0,0x10000,4):
        v=r(0x700000+o)
        if lo<=v<=hi:
            pa=(win<<16)+o; hits+=1
            print(f"{pa:#x}: {v:08x}  next {r(0x700000+o+4) if o<0xfffc else 0:08x}",flush=True)
            if hits>200: break
w(0x1700,old); r(0x1700)
print(f"done {hits} hits in {time.time()-t:.1f}s",file=sys.stderr)
