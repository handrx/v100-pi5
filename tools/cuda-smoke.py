#!/usr/bin/env python3
# CUDA driver-API smoke test for the V100 on the Pi 5: no toolkit needed (libcuda + PTX JIT only).
# Usage: cuda-smoke.py [last_stage]   stages run in order, stop after last_stage (default: all)
#   1 init/device info   2 pageable H2D/D2H   3 pinned H2D/D2H + bandwidth   4 memset
#   5 PTX kernel (sm_70 JIT)   6 zero-copy (kernel writes mapped pinned host mem)   7 managed memory (UVM migration)
import ctypes as C, os, sys, time

cu = C.CDLL("libcuda.so.1")
LAST = int(sys.argv[1]) if len(sys.argv) > 1 else 99
MB = 1 << 20


def ck(r, what):
    if r != 0:
        s = C.c_char_p()
        cu.cuGetErrorString(r, C.byref(s))
        raise SystemExit(f"FAIL {what}: {r} {s.value.decode() if s.value else ''}")


def stage(n, name):
    if n > LAST:
        print("stop"); sys.exit(0)
    print(f"[{n}] {name}", flush=True)


def check(buf_a, buf_b, n, what):
    if C.string_at(buf_a, n) == C.string_at(buf_b, n):
        print(f"    {what}: OK ({n // MB} MB)")
        return
    a, b = C.string_at(buf_a, n), C.string_at(buf_b, n)
    bad = [i for i in range(0, n, 4) if a[i:i + 4] != b[i:i + 4]]
    raise SystemExit(f"FAIL {what}: {len(bad)} of {n // 4} words differ, first at 0x{bad[0]:x}: "
                     f"want {a[bad[0]:bad[0]+4].hex()} got {b[bad[0]:bad[0]+4].hex()}")


def bw(fn, n, reps=5):
    cu.cuCtxSynchronize(); t = time.perf_counter()
    for _ in range(reps):
        ck(fn(), "copy")
    ck(cu.cuCtxSynchronize(), "sync")
    return n * reps / (time.perf_counter() - t) / 1e9


stage(1, "init / device")
ck(cu.cuInit(0), "cuInit")
v = C.c_int(); ck(cu.cuDriverGetVersion(C.byref(v)), "version")
dev = C.c_int(); ck(cu.cuDeviceGet(C.byref(dev), 0), "cuDeviceGet")
name = C.create_string_buffer(128); cu.cuDeviceGetName(name, 128, dev)
mj, mn = C.c_int(), C.c_int()
cu.cuDeviceGetAttribute(C.byref(mj), 75, dev); cu.cuDeviceGetAttribute(C.byref(mn), 76, dev)
tot = C.c_size_t(); cu.cuDeviceTotalMem_v2(C.byref(tot), dev)
print(f"    driver {v.value}, {name.value.decode()}, sm_{mj.value}{mn.value}, {tot.value // MB} MB")
ctx = C.c_void_p(); ck(cu.cuCtxCreate_v2(C.byref(ctx), 0, dev), "cuCtxCreate")
print("    context OK")

N = 64 * MB
src = C.create_string_buffer(os.urandom(N), N)
dst = C.create_string_buffer(N)
d = C.c_uint64(); ck(cu.cuMemAlloc_v2(C.byref(d), C.c_size_t(N)), "cuMemAlloc")

stage(2, "pageable H2D / D2H")
for i in range(3):
    C.memset(dst, 0, N)
    ck(cu.cuMemcpyHtoD_v2(d, src, C.c_size_t(N)), "HtoD")
    ck(cu.cuMemcpyDtoH_v2(dst, d, C.c_size_t(N)), "DtoH")
    check(src, dst, N, f"pageable round trip #{i}")

stage(3, "pinned H2D / D2H")
hp_src, hp_dst = C.c_void_p(), C.c_void_p()
ck(cu.cuMemAllocHost_v2(C.byref(hp_src), C.c_size_t(N)), "cuMemAllocHost src")
ck(cu.cuMemAllocHost_v2(C.byref(hp_dst), C.c_size_t(N)), "cuMemAllocHost dst")
C.memmove(hp_src, src, N)
for i in range(3):
    C.memset(hp_dst, 0, N)
    ck(cu.cuMemcpyHtoD_v2(d, hp_src, C.c_size_t(N)), "HtoD pinned")
    ck(cu.cuMemcpyDtoH_v2(hp_dst, d, C.c_size_t(N)), "DtoH pinned")
    check(hp_src, hp_dst, N, f"pinned round trip #{i}")
h2d = bw(lambda: cu.cuMemcpyHtoD_v2(d, hp_src, C.c_size_t(N)), N)
d2h = bw(lambda: cu.cuMemcpyDtoH_v2(hp_dst, d, C.c_size_t(N)), N)
print(f"    pinned bandwidth: H2D {h2d:.2f} GB/s, D2H {d2h:.2f} GB/s")

stage(4, "memset")
ck(cu.cuMemsetD32_v2(d, C.c_uint(0xA5C3E1F0), C.c_size_t(N // 4)), "memset")
ck(cu.cuMemcpyDtoH_v2(hp_dst, d, C.c_size_t(N)), "DtoH")
want = C.create_string_buffer(bytes.fromhex("f0e1c3a5") * (N // 4), N)
check(want, hp_dst, N, "memsetD32")

PTX = rb"""
.version 6.4
.target sm_70
.address_size 64
.visible .entry k(.param .u64 pin, .param .u64 pout, .param .u32 n)
{
  .reg .pred %p; .reg .b32 %r<8>; .reg .b64 %rd<8>;
  ld.param.u64 %rd1, [pin]; ld.param.u64 %rd2, [pout]; ld.param.u32 %r1, [n];
  mov.u32 %r2, %ctaid.x; mov.u32 %r3, %ntid.x; mov.u32 %r4, %tid.x;
  mad.lo.s32 %r5, %r2, %r3, %r4;
  setp.ge.u32 %p, %r5, %r1; @%p bra DONE;
  mul.wide.u32 %rd3, %r5, 4;
  add.s64 %rd4, %rd1, %rd3; add.s64 %rd5, %rd2, %rd3;
  ld.global.u32 %r6, [%rd4];
  mad.lo.s32 %r7, %r6, 3, %r5;
  st.global.u32 [%rd5], %r7;
DONE:
  ret;
}
"""


def launch(fn, pin, pout, n):
    a_in, a_out, a_n = C.c_uint64(pin), C.c_uint64(pout), C.c_uint(n)
    args = (C.c_void_p * 3)(C.addressof(a_in), C.addressof(a_out), C.addressof(a_n))
    ck(cu.cuLaunchKernel(fn, (n + 255) // 256, 1, 1, 256, 1, 1, 0, None, args, None), "launch")
    ck(cu.cuCtxSynchronize(), "sync after kernel")


def expect_kernel(inp, n):
    import array
    a = array.array("I", C.string_at(inp, n * 4))
    return array.array("I", [(x * 3 + i) & 0xffffffff for i, x in enumerate(a)]).tobytes()


stage(5, "PTX kernel (JIT for sm_70)")
mod = C.c_void_p(); ck(cu.cuModuleLoadData(C.byref(mod), C.c_char_p(PTX)), "cuModuleLoadData (PTX JIT)")
fn = C.c_void_p(); ck(cu.cuModuleGetFunction(C.byref(fn), mod, b"k"), "cuModuleGetFunction")
K = 4 * MB  # words
d2 = C.c_uint64(); ck(cu.cuMemAlloc_v2(C.byref(d2), C.c_size_t(K * 4)), "cuMemAlloc out")
ck(cu.cuMemcpyHtoD_v2(d, hp_src, C.c_size_t(K * 4)), "HtoD")
launch(fn, d.value, d2.value, K)
ck(cu.cuMemcpyDtoH_v2(hp_dst, d2, C.c_size_t(K * 4)), "DtoH")
want = C.create_string_buffer(expect_kernel(hp_src, K), K * 4)
check(want, hp_dst, K * 4, "kernel out = in*3 + i")

stage(6, "zero-copy: kernel writes mapped pinned host memory")
zc = C.c_void_p(); ck(cu.cuMemHostAlloc(C.byref(zc), C.c_size_t(K * 4), 0x2), "cuMemHostAlloc DEVICEMAP")
dzc = C.c_uint64(); ck(cu.cuMemHostGetDevicePointer_v2(C.byref(dzc), zc, 0), "cuMemHostGetDevicePointer")
C.memset(zc, 0x5A, K * 4)
launch(fn, d.value, dzc.value, K)
check(want, zc, K * 4, "zero-copy kernel output read by CPU")
C.memmove(zc, hp_src, K * 4)  # now the GPU reads host memory the CPU just wrote
launch(fn, dzc.value, d2.value, K)
ck(cu.cuMemcpyDtoH_v2(hp_dst, d2, C.c_size_t(K * 4)), "DtoH")
check(want, hp_dst, K * 4, "kernel reading zero-copy input")

stage(7, "managed memory (UVM migration)")
m = C.c_uint64(); ck(cu.cuMemAllocManaged(C.byref(m), C.c_size_t(K * 4), 1), "cuMemAllocManaged")
C.memmove(m.value, hp_src, K * 4)          # CPU first touch
launch(fn, m.value, d2.value, K)           # GPU reads -> migrate to GPU
ck(cu.cuMemcpyDtoH_v2(hp_dst, d2, C.c_size_t(K * 4)), "DtoH")
check(want, hp_dst, K * 4, "kernel reading managed input")
launch(fn, d.value, m.value, K)            # GPU writes managed
check(want, m.value, K * 4, "CPU reading managed output (migrate back)")
print("ALL OK")
