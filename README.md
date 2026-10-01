# Tesla V100 on a Raspberry Pi 5

A Tesla V100-PCIE-32GB running CUDA and llama.cpp on a Raspberry Pi 5, connected through the external PCIe
port with an OCuLink adapter.

| | |
|---|---|
| Qwen2.5-7B-Instruct Q4_K_M, all layers on the GPU | **2787 t/s** prompt (pp512), **99.6 t/s** generation (tg128) |
| CUDA | all of `tools/cuda-smoke.py` (copies, kernels, zero-copy, managed memory), cuBLAS SGEMM 12.0 TFLOPS, HGEMM 81 TFLOPS |
| Host <-> GPU copies | ~0.4 GB/s each way (PCIe gen2 x1) |
| Idle / load | ~31 W idle, peak 181 W at 39 °C under llama-bench (with a fan on the passive heatsink) |

Raw results in [`results/`](results). The full story (every decision, what failed and why) is in
[`docs/REVIEW.md`](docs/REVIEW.md); the step-by-step log is [`docs/STATUS.md`](docs/STATUS.md).

## Why it doesn't just work

Three separate problems, each with its own fix:

1. **Address space.** The V100's BAR1 is a fixed 32 GB and must be 32 GB aligned on the bus. The Pi 5's
   external PCIe window is only 14 GB, so Linux leaves BAR1 unassigned.
   - `overlay/v100-pcie-overlay.dts` moves the window's *bus* address to 0x8_0000_0000 (32 GB aligned). The CPU
     side and its size stay the same.
   - `kernel/v100_bar/v100_bar.c` programs BAR1 to that bus address and exposes only the first 8 GB of it to
     Linux, and puts BAR3 into the 32-bit window. The NVIDIA driver accepts an 8 GB BAR1 when told
     `RMBar1ApertureSizeMB=8192`.
2. **Volta needs the closed driver.** NVIDIA's open kernel modules only support Turing and newer, so this uses
   the closed 580.95.05 aarch64 kernel module (the last branch with Volta, and CUDA 12.9 is the last toolkit
   with sm_70).
3. **The Pi's PCIe is not cache-coherent**, and the closed driver assumes it is on arm64. The GPU then reads
   stale data from RAM and the CPU reads its own cached writes back. This shows up as many different failures
   (Xid 79 "fallen off the bus", MMU faults, hung `cuInit`, ~1% corrupted copies), all with the same cause.
   The fixes are in `driver/`:
   - glue-layer patches (MIT-licensed source) that map GPU-shared system memory uncached, keep tiny
     allocations cached (BCM2712 aborts CPU atomics on uncached memory, and RM uses them), force UVM's
     allocations uncached, and make the cache-flush calls libcuda relies on actually flush (on arm64 they
     were silent no-ops);
   - two binary patches to the closed RM blob: the chipset "IO coherent" default set to FALSE (the same
     change the open-RM non-coherent fork makes in source), and a NULL check in an error-unwind path.

## What's in here

```
driver/patches/       7 patches against the stock 580.95.05 closed kernel source (glue code, dkms.conf)
driver/blob-patch.py  byte patches for nvidia/nv-kernel.o_binary (checks stock + result sha256)
kernel/v100_bar/      the BAR placement module (+ DKMS config)
overlay/              the device-tree overlay source
system/               modprobe.d config and the on-demand load guard
cuda/                 glibc 2.41 fix for CUDA 12.9's math_functions.h
tools/                test and debug tools (cuda-smoke.py, copy-diag.py, cublas-test.cu, nvrtrace kprobe tracer, ...)
docs/                 REVIEW.md (the write-up) and STATUS.md (the running log)
results/              benchmark output
```

NVIDIA's driver and its blob are not included; you need your own copy.

## Setup

Tested on: Raspberry Pi 5 (16 GB), Raspberry Pi OS / Debian 13 (trixie), kernel 6.18.34+rpt-rpi-2712, driver
580.95.05, CUDA 12.9.1. Everything below runs as root.

1. **Overlay.** Build it, then add it under `[all]` in `/boot/firmware/config.txt`:
   ```sh
   dtc -@ -I dts -O dtb -o /boot/firmware/overlays/v100-pcie.dtbo overlay/v100-pcie-overlay.dts
   echo dtoverlay=v100-pcie >> /boot/firmware/config.txt
   ```
   Safer the first time: put it in `/boot/firmware/tryboot.txt` (a copy of `config.txt` plus the line) and
   boot it once with `reboot "0 tryboot"`. A power-cycle falls back to the normal config.
2. **v100_bar.** `cp -r kernel/v100_bar /usr/src/v100-bar-1.0 && dkms install v100-bar/1.0`
3. **Driver.** Extract `NVIDIA-Linux-aarch64-580.95.05.run --extract-only` and use its `kernel/` directory:
   ```sh
   cp -r NVIDIA-Linux-aarch64-580.95.05/kernel /usr/src/nvidia-580.95.05-v100
   cd /usr/src/nvidia-580.95.05-v100
   git init -q && git add -A && git commit -qm stock
   git am /path/to/this/repo/driver/patches/*.patch
   /path/to/this/repo/driver/blob-patch.py nvidia/nv-kernel.o_binary
   dkms install nvidia/580.95.05-v100
   ```
   The user-space parts (`nvidia-smi`, `libcuda`) come from the same `.run` (install with `--no-kernel-modules`).
4. **Loading.** `system/v100.conf` goes to `/etc/modprobe.d/`, `system/v100-modprobe-guard` to
   `/usr/local/sbin/`. Nothing loads at boot; the first `nvidia-smi` or CUDA program loads `v100_bar`, `nvidia`
   and `nvidia_uvm` through the guard. The guard refuses if the overlay isn't active, if `v100.noload` is on
   the kernel command line, or if a previous load never finished (it hung the Pi): `rm /var/lib/v100/loading`
   to retry.
5. **CUDA 12.9.** The runfile needs ~4 GB free; the per-component redist tarballs (linux-sbsa) are much
   smaller. Then `cuda/fix-glibc241-math.sh` so nvcc works with glibc 2.41.
6. **Check.** `nvidia-smi`, then `tools/cuda-smoke.py 7` (needs only libcuda, no toolkit).
7. **llama.cpp.** `cmake -B build-v100 -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=70 && cmake --build build-v100 -j4`

### Driver parameters

| Parameter | Default | |
|---|---|---|
| `nv_pi5_force_uncached` | 1 | map GPU-shared system memory uncached |
| `nv_pi5_nc_min_pages` | 1 | only force allocations of at least this many pages uncached; **use 2** |
| `nv_pi5_uvm_uncached` | 1 | force UVM's allocations uncached regardless of size |
| `nv_pi5_no_iomap_wc` | 1 | never map GPU MMIO write-combined |
| `nv_pi5_debug` | 0 | 1 logs allocations and mappings, 2 also logs user-page flushes |

Plus `NVreg_RegistryDwords="RMBar1ApertureSizeMB=8192;RMPcieLinkSpeed=0x800000a8;RMDisableGpuASPMFlags=3"`
(all set in `system/v100.conf`).

## Limits

- Only 8 of the 32 GB BAR1 is mapped. All 32 GB of VRAM is usable by CUDA; BAR1 only limits direct CPU
  mappings of VRAM.
- PCIe gen2 x1 (~0.4 GB/s): model loading is slow, inference speed is unaffected once the model is in VRAM.
- The GPU has no function-level reset. If the driver wedges, only a reboot recovers it.
- The tools in `tools/` were written for this bring-up and have paths like `/root/v100-pi` hard-coded.

## Credits

The non-coherent approach follows mariobalanica's `non-coherent-arm-fixes` fork of NVIDIA's open kernel
modules, which made an RTX 4060 Ti work on the same Pi first.
