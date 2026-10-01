#!/usr/bin/env python3
# Walk the GPU's BAR2 page tables via PRAMIN to read the RM's non-replayable MMU fault buffer (BAR2 VA from 0x100e24).
# Sets the PRAMIN window (0x1700), so only use when RM is dead/wedged.
# v2: usage pramin-walk.py [VA [INST]]  (INST = instance block PA in vidmem, default BAR2's); tables in sysmem via /dev/mem.
import mmap,struct,sys
f=open('/sys/bus/pci/devices/0001:01:00.0/resource0','r+b')
m=mmap.mmap(f.fileno(),0x1000000,mmap.MAP_SHARED,mmap.PROT_READ|mmap.PROT_WRITE)
r=lambda a: struct.unpack_from('<I',m,a)[0]
w=lambda a,v: struct.pack_into('<I',m,a,v)
def vr32(pa):   # read vidmem via PRAMIN
    win=pa>>16
    if r(0x1700)!=win: w(0x1700,win); r(0x1700)
    return r(0x700000+(pa&0xffff))
def vr64(pa): return vr32(pa)|(vr32(pa+4)<<32)
IB=0x1000000000   # pcie1 inbound: CPU 0 -> bus 0x10_0000_0000
def sr64(pa):     # read sysmem (bus addr) via /dev/mem
    with open('/dev/mem','rb') as d: d.seek(pa-IB); return struct.unpack('<Q',d.read(8))[0]
def rd64(ap,pa): return vr64(pa) if ap==1 else sr64(pa)
blk=r(0x1714); inst=(blk&0xfffffff)<<12
if len(sys.argv)>2: inst=int(sys.argv[2],0)
print(f'BAR2_BLOCK {blk:08x} inst {inst:#x} target {(blk>>28)&3}')
lo,hi=vr32(inst+0x200),vr32(inst+0x204)
pdb=((hi<<32)|(lo&~0xfff)); print(f'PDB lo {lo:08x} hi {hi:08x} -> {pdb:#x} tgt {lo&3} ver2 {(lo>>10)&1} big64k {(lo>>11)&1}')
va=int(sys.argv[1],0) if len(sys.argv)>1 else ((r(0x100e28)<<32)|(r(0x100e24)&~0xfff))
print(f'VA {va:#x}')
def pde(e):   # V2 PDE: bits 2:1 aperture (0 invalid,1 vid,2 syscoh,3 sysnc), addr bits from 8 (vid) <<4
    ap=(e>>1)&3; addr=((e>>8)&((1<<46)-1))<<12
    return ap,addr
tbl,tap=pdb,{0:1,2:2,3:3}.get(lo&3,1)
for lvl,(sh,bits) in enumerate([(47,2),(38,9),(29,9)]):
    idx=(va>>sh)&((1<<bits)-1); e=rd64(tap,tbl+idx*8); ap,addr=pde(e)
    print(f'PD{3-lvl} idx {idx} @ {tbl+idx*8:#x} (ap {tap}): {e:016x} ap {ap} -> {addr:#x}')
    if ap==0: sys.exit('invalid')
    tbl,tap=addr,ap
idx=(va>>21)&0xff; e0=rd64(tap,tbl+idx*16); e1=rd64(tap,tbl+idx*16+8)
print(f'PD0 idx {idx} @ {tbl+idx*16:#x} (ap {tap}): big {e0:016x} small {e1:016x}')
for e,small in ((e1,1),(e0,0)):
    ap,addr=pde(e)
    if ap==0: continue
    if small: pi=(va>>12)&0x1ff
    else: pi=(va>>16)&0x1f
    pte=rd64(ap,addr+pi*8)
    pap=(pte>>1)&3; ppa=((pte>>8)&((1<<46)-1))<<12
    print(f'PTE ({"4K" if small else "64K"}) {pte:016x} valid {pte&1} aperture {pap} pa {ppa:#x}')
    if pte&1:
        off=va&(0xfff if small else 0xffff)
        print(f'=> VA {va:#x} = PA {ppa+off:#x} aperture {pap} (1=vidmem 2=sys coh 3=sys noncoh)')
        if pap==1:
            for i in range(0,64,4): print(f'  +{i:02x}: {vr32(ppa+off+i):08x}')
    break
