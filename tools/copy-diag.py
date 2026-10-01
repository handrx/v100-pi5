#!/usr/bin/env python3
# Characterise copy corruption: D2H alone (device memset -> host), H2D alone (host -> device -> memset-verified path),
# pageable vs pinned, several sizes. Prints bad-word counts, 64B-line clustering, and what the bad words contain.
import ctypes as C, os, sys, array, collections
cu = C.CDLL("libcuda.so.1")
MB = 1 << 20
def ck(r, w):
    if r: raise SystemExit(f"FAIL {w}: {r}")
ck(cu.cuInit(0), "init"); dev = C.c_int(); ck(cu.cuDeviceGet(C.byref(dev), 0), "dev")
ctx = C.c_void_p(); ck(cu.cuCtxCreate_v2(C.byref(ctx), 0, dev), "ctx")

def analyse(tag, want, got, src=None):
    a, b = array.array("I", want), array.array("I", got)
    bad = [i for i in range(len(a)) if a[i] != b[i]]
    if not bad:
        print(f"  {tag}: OK"); return
    lines = collections.Counter(i // 16 for i in bad)
    pages = collections.Counter(i // 1024 for i in bad)
    full = sum(1 for v in lines.values() if v == 16)
    zero = sum(1 for i in bad if b[i] == 0)
    print(f"  {tag}: {len(bad)}/{len(a)} bad words, {len(lines)} lines ({full} full), {len(pages)} pages, "
          f"zero={zero}, first@{bad[0]*4:#x} want {a[bad[0]]:08x} got {b[bad[0]]:08x}")
    runs, s = [], bad[0]
    for p, q in zip(bad, bad[1:] + [None]):
        if q != p + 1: runs.append((s * 4, (p + 1) * 4)); s = q
    print(f"    runs: {len(runs)}; first: {[(hex(x), y - x) for x, y in runs[:6]]}")
    if src is not None:
        idx = {}
        s = array.array("I", src)
        for k in range(len(s)): idx.setdefault(s[k], k)
        hits = [(i, idx.get(b[i])) for i in bad[:2000] if b[i] in idx]
        d = collections.Counter((j - i) * 4 for i, j in hits)
        print(f"    bad words found elsewhere in src: {len(hits)}/{min(len(bad),2000)}, offsets: {d.most_common(4)}")

for N in (64 * 1024, 1 * MB, 16 * MB, 64 * MB):
    print(f"N={N // 1024} KB")
    d = C.c_uint64(); ck(cu.cuMemAlloc_v2(C.byref(d), C.c_size_t(N)), "alloc")
    src = C.create_string_buffer(os.urandom(N), N); dst = C.create_string_buffer(N)
    # D2H alone: device memset -> pageable host
    ck(cu.cuMemsetD32_v2(d, C.c_uint(0xA5C3E1F0), C.c_size_t(N // 4)), "memset"); ck(cu.cuCtxSynchronize(), "sync")
    C.memset(dst, 0, N); ck(cu.cuMemcpyDtoH_v2(dst, d, C.c_size_t(N)), "DtoH")
    analyse("D2H pageable (memset)", bytes.fromhex("f0e1c3a5") * (N // 4), C.string_at(dst, N))
    # pinned
    hp = C.c_void_p(); ck(cu.cuMemAllocHost_v2(C.byref(hp), C.c_size_t(N)), "allochost")
    C.memset(hp, 0, N); ck(cu.cuMemcpyDtoH_v2(hp, d, C.c_size_t(N)), "DtoH pinned")
    analyse("D2H pinned   (memset)", bytes.fromhex("f0e1c3a5") * (N // 4), C.string_at(hp, N))
    # H2D pageable, read back via pinned and via pageable
    ck(cu.cuMemcpyHtoD_v2(d, src, C.c_size_t(N)), "HtoD")
    C.memset(hp, 0, N); ck(cu.cuMemcpyDtoH_v2(hp, d, C.c_size_t(N)), "DtoH pinned")
    analyse("H2D pageable -> D2H pinned", C.string_at(src, N), C.string_at(hp, N), C.string_at(src, N))
    C.memmove(hp, src, N); ck(cu.cuMemcpyHtoD_v2(d, hp, C.c_size_t(N)), "HtoD pinned")
    C.memset(dst, 0, N); ck(cu.cuMemcpyDtoH_v2(dst, d, C.c_size_t(N)), "DtoH")
    analyse("H2D pinned -> D2H pageable", C.string_at(src, N), C.string_at(dst, N), C.string_at(src, N))
    C.memset(dst, 0, N); ck(cu.cuMemcpyDtoH_v2(dst, d, C.c_size_t(N)), "DtoH")
    analyse("  same D2H pageable again ", C.string_at(src, N), C.string_at(dst, N), C.string_at(src, N))
    cu.cuMemFreeHost(hp); cu.cuMemFree_v2(d)
    sys.stdout.flush()
