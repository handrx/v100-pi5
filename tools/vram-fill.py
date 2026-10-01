#!/usr/bin/env python3
"""Allocate as much VRAM as CUDA allows in 1 GiB chunks, fill each with its own pattern
(cuMemsetD32, on the GPU), then read back 4 MiB from the start, middle and end of every
chunk. Shows how much of the 32 GB is really usable, independent of BAR1's size."""
import ctypes as C, struct, sys

cu = C.CDLL("libcuda.so.1")
def ck(r, what):
    if r: sys.exit(f"{what} failed: {r}")

ck(cu.cuInit(0), "cuInit")
dev = C.c_int(); ck(cu.cuDeviceGet(C.byref(dev), 0), "cuDeviceGet")
ctx = C.c_void_p(); ck(cu.cuCtxCreate_v2(C.byref(ctx), 0, dev), "cuCtxCreate")
free, total = C.c_size_t(), C.c_size_t()
ck(cu.cuMemGetInfo_v2(C.byref(free), C.byref(total)), "cuMemGetInfo")
print(f"total {total.value / 2**30:.2f} GiB, free {free.value / 2**30:.2f} GiB")

GiB, PROBE = 2**30, 4 * 2**20
chunks = []
while True:
    d = C.c_uint64()
    if cu.cuMemAlloc_v2(C.byref(d), C.c_size_t(GiB)):
        break
    chunks.append(d.value)
ck(cu.cuMemGetInfo_v2(C.byref(free), C.byref(total)), "cuMemGetInfo")
print(f"allocated {len(chunks)} x 1 GiB, {free.value / 2**20:.0f} MiB left free")

for i, d in enumerate(chunks):
    ck(cu.cuMemsetD32_v2(C.c_uint64(d), C.c_uint(0x5A000000 | i), C.c_size_t(GiB // 4)), f"memset {i}")
ck(cu.cuCtxSynchronize(), "sync")

host = (C.c_char * PROBE)()
bad = 0
for i, d in enumerate(chunks):
    for off in (0, GiB // 2, GiB - PROBE):
        ck(cu.cuMemcpyDtoH_v2(host, C.c_uint64(d + off), C.c_size_t(PROBE)), f"DtoH {i}")
        want = struct.pack("<I", 0x5A000000 | i) * (PROBE // 4)
        if bytes(host) != want:
            bad += 1
            print(f"chunk {i} (va {d:#x}) +{off:#x}: MISMATCH")
print(f"{len(chunks)} GiB filled, {3 * len(chunks)} probes, {bad} bad ->", "OK" if not bad else "FAIL")
