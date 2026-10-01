# V100 on the Raspberry Pi 5: review of the bring-up

Written 2026-10-01 (~19:30 BST), updated after each step since (latest: Step 4 UVM fix built, ~20:35). Sources: the ~20 Claude sessions since Sep 24, `STATUS.md`, the patched
driver's git history and the run logs in this directory. Times are Pi clock (BST). The time labels inside
`STATUS.md` run up to ~15 minutes ahead of the real clock.

## Where it stands

- **Goal:** a Tesla V100-PCIE-32GB on the Pi 5 over OCuLink, running llama.cpp.
- **Solved: the address-space problem.** The card's fixed 32 GB BAR1 is placed with a device-tree overlay plus a
  small kernel module. 8 GB of it is reachable, and the NVIDIA driver accepts that.
- **Progress:** NVIDIA's closed driver, patched for the Pi, now gets deep into GPU init: VRAM training, page
  tables, power-management controller boot, internal copy-engine channel.
- **Current blocker (found Oct 1 ~19:08):** the driver's own copy-engine self-test fails. The GPU copies a value
  from VRAM into a 1-page buffer in the Pi's RAM, the CPU reads it back, and the value is wrong. That is the Pi's
  non-coherent PCIe problem in its smallest form.
- **Why (Step 1, Oct 1 19:45):** the CPU reached that buffer through its *cached* mapping, so it read back its own
  write from its cache.
  - Stock RM assumes the PCIe bus is cache-coherent unless the chipset is a known non-coherent one (only Tegra).
    On arm64 it then turns every system-RAM request into a cached one, including this "uncached" buffer.
  - My 2-page rule (D13) then left the 1-page buffer cached.
  - The 4060 Ti fork fixed exactly this assumption in RM's source; here it has to be patched in the binary (D26).
- **Everything else seen since Sep 29 is a side effect of that failed self-test.** That includes Xid 79 "GPU has
  fallen off the bus", the power-controller fault and the 15 s PCIe outage: they are the driver tearing down,
  not separate problems.
- **Step 2, first try (`c1ed779`, run 17, Oct 1 20:02): no effect.** It patched the wrong function, and the flag
  read back as still TRUE at runtime (D27).
- **Step 2, second try (`163fb0e`, run 18, Oct 1 20:14): WORKS.** The same one-instruction patch, now on the real
  default in RM's `clConstruct` (D27). The flag reads 0 at runtime, the self-test matches (`aabbccdd`), and init
  completes: `nvidia-smi` lists the Tesla V100-PCIE-32GB (32 GB VRAM, 8 GB BAR1, PCIe gen2 x1, ~32 W idle). No Xid,
  no crash, and a second `nvidia-smi` re-inits cleanly.
- **Step 4 (UVM, CUDA), run 19:** `cuInit` hung in UVM's GPU registration. Same non-coherency problem: one
  1-page UVM semaphore page stayed cached (D28).
- **Run 20 (Oct 1 20:31):** `3728361` works: `cuInit` and context creation succeed. Pageable host-to-device
  copies were ~1.4% wrong: libcuda's cache-flush requests were silently no-ops on arm64 (D29).
- **Run 21 (Oct 1 20:41, `4f88bf9`, no reboot needed): CUDA WORKS.** `cuda-smoke.py` passes all 7 stages
  (pageable and pinned copies, memset, PTX kernel JIT for sm_70, zero-copy, managed memory / UVM migration), and
  `copy-diag.py` passes all 20 checks (64 KB to 64 MB). Copy bandwidth ~0.4 GB/s each way (gen2 x1 link).
- **Oct 1 21:33: llama.cpp runs on the V100.** CUDA 12.9 from the redist tarballs, llama.cpp built for sm_70.
  Qwen2.5-7B-Instruct Q4_K_M, fully offloaded: 2752 t/s prompt processing, 99 t/s generation, peak 39 C / 181 W
  with your fan. Answers are correct at temperature 0.
- **Oct 1 ~22:00: Step 5 DONE.** The setup survives a normal reboot; the driver loads on demand behind a guard.
- **Next:** storage for a ~30B model: the SD card has ~5 GB free.
- **Cost so far:** 19 test boots (21 driver runs) in about 4.5 hours of hands-on sessions. Each run costs a
  reboot, because the GPU has no function-level reset and the driver usually wedges.

Terms used below:
- **RM:** the closed "resource manager" core of the NVIDIA driver (a binary blob).
- **CE:** the GPU's copy engine (its DMA engine).
- **PMU:** the GPU's power-management microcontroller.
- **NC:** a non-cacheable memory mapping.
- **sysmem:** the Pi's RAM as the GPU sees it.
- **Wedged:** a driver thread is stuck in the kernel, so the module can't be unloaded.
- **tryboot:** the Pi's one-shot alternate boot config.

## 1. Starting point

- Raspberry Pi 5 running Debian 13 and kernel 6.18.34+rpt-rpi-v8 (4K pages via `kernel=kernel8.img`). OCuLink
  on the external PCIe port (pcie1), Gen2 x1.
- The RTX 4060 Ti worked here (Sep 14). It used:
  - the open NVIDIA modules from the mariobalanica `non-coherent-arm-fixes` fork;
  - a 4K-page kernel;
  - CUDA 13.0;
  - llama.cpp built for sm_89 (45.8 tok/s on Qwen2.5-7B Q4).

  Its problem was the same kind as today's: the Pi's PCIe doesn't keep CPU caches coherent with device DMA. The
  fork fixes that in the driver source.
- The V100 brought three blockers (Sep 24):
  1. BAR1 is a fixed 32 GB, but pcie1's prefetchable window is only 14 GB ("BAR 1: can't assign; no space").
     This card has no resizable BAR.
  2. Volta has no GSP, so the open modules refuse it. The closed modules are needed, and the fork's coherency
     fixes live in RM, which is a binary in the closed driver.
  3. CUDA 13 dropped Volta (sm_70). That means CUDA 12.x (12.9) and a llama.cpp rebuild for arch 70.

## 2. Run log

| # | When (BST) | What was tried | Result |
|---|---|---|---|
| 0 | Sep 24, 14:35-14:48 | Everything at once, in the normal boot path (D2-D4) | Pi wouldn't boot with the V100 attached (reported Sep 29). No logs survived. |
| - | Sep 29 19:15 | Full revert | Boots fine with the V100 attached (BAR0 only) |
| 1 | 19:27 | Overlay only, via tryboot | Boots fine, overlay applied |
| 2 | 19:32 | `v100_bar` and patched `nvidia.ko` by hand, then `nvidia-smi` | BAR1 (8 GB) and BAR3 assigned, GPU answers. `nvidia-smi`: oops in our own `nv_pi5_flush_alloc` patch, fixed in `19763e5` |
| - | ~19:41 | Bare `nvidia-smi` with nothing loaded | Hard lock, then watchdog reset: it had auto-loaded the 4060 Ti driver against the V100 |
| 3 | 19:48 | Fixed driver | Synchronous external abort on an atomic load (LDXR) inside RM; wedged |
| - | 19:56 | Plain `reboot "0 tryboot"` while wedged | Hung; the Pi had to be unplugged |
| 4 | 20:03 | `nv_pi5_debug=1` | The atomic hit a 1-page buffer that RM asked for as cached and our patch had made NC |
| 5 | 20:10 | `nv_pi5_force_uncached=0` | No abort, but Xid 62 instead (PMU halted) |
| 6 | 20:16 | `nv_pi5_nc_min_pages=2` (`67d88ec`) | Abort and Xid 62 both gone; NULL dereference in RM (`_nv026674rm`); wedged |
| 7 | 20:21 | Added `RMBar1ApertureSizeMB=8192` | RM's BAR1 mappings now inside the window; same NULL dereference |
| 8 | 20:45 | Added RM verbose logging | No RM messages (compiled out of the blob); same NULL dereference |
| 9 | 20:55 | RM blob binary-patched with a NULL check (`c572858`) | No oops, no wedge, clean `rmmod`. RM's real error: Xid 79 + `RmInitAdapter failed! (0x25:0x40:1623)` |
| 10 | 21:03 | VRAM probe before/after; read-only register watcher | "Dead VRAM" theory disproved: VRAM is fine during init and only fails in the teardown |
| 11 | 21:14 | Call stacks on RM's log prints (`xid-trace.sh`) | GPU stops answering on PCIe ~5 ms after RM starts the PMU |
| 12 | 21:23 | Link speed locked, ASPM off, full register trace (`nvrtrace`) | Still Xid 79, so link speed and ASPM are ruled out. Trigger narrowed to the PMU context-switch write, 0.4 ms after a copy-engine reset |
| - | Oct 1 18:28 | (nothing run) | Pi was on the normal config (a shutdown/power-on always is), so another tryboot was needed |
| 13 | 18:31 | 20 ms hold just before that PMU write | GPU stays on the bus. Instead: one MMU fault, PMU stalls, RM polls 60 s, teardown oops |
| 14 | 18:41 | `nvrtrace` v3 dumps the fault record | v3 crashed in its own dump, which froze RM with the GPU state intact. Record read from userspace: the PMU wrote to an unmapped address in its own address space |
| 15 | 18:58 | `nvrtrace` v4 follows that address | The address was mapped, then unmapped by RM's cleanup. RM's call stacks lead to the failed CE self-test: **root failure** |
| 16 | 19:45 | `nvrtrace` v5 measures the self-test (Step 1) | CPU read back its own `11223345`. The buffer's CPU mapping is the *cached* linear map, so RM handed it to the glue layer as cached, even though the self-test asks for uncached (D25). No wedge. Afterwards the GPU stayed off the bus (config space reads all-ones). In earlier runs it came back after ~15 s |
| 17 | 20:02 | RM coherency default patched to FALSE, `c1ed779` (Step 2, D26) | No change: same mismatch, same cached linear map. `clpeek` read the flag at runtime: still 1. `c1ed779` had patched a chipset-table function that never runs on the Pi (D27). GPU off the bus again |
| 18 | 20:14 | RM coherency default patched in `clConstruct`, `163fb0e` (Step 2 retry, D27) | **Works.** Flag 0 at runtime, self-test matches, RM init completes, `nvidia-smi` lists the V100 (32 GB, 8 GB BAR1, gen2 x1). No Xid, no crash |
| 19 | 20:30 | `nvidia-uvm` loaded by hand; `cuda-smoke.py` stage 1 (`cuInit`) (Step 4) | Hangs in UVM GPU registration: the CE's semaphore release isn't visible to the CPU (1-page UVM allocation kept cached, D28). GPU healthy, ioctl unkillable |
| 20 | 20:31 | UVM allocations forced NC, `3728361` (D28); `cuda-run.sh 7` | `cuInit` + context OK. Stage 2 fails: pageable H2D ~1.4% of 64 B lines stale (D29). Not wedged |
| 21 | 20:41 | user-page cache flush, `4f88bf9` (D29); driver reloaded without reboot | **CUDA works:** all 7 smoke stages + all 20 copy-diag checks pass. ~0.4 GB/s copies. No Xid |

## 3. Decisions and why

### Phase 0, Sep 24: first attempt, all at once

**D1. Try it on the Pi anyway.**
- Claude's first verdict was that the BAR1 size made the V100 impossible on the Pi.
- It recommended an x86 host (with "Above 4G decoding") or putting the 4060 Ti back.
- The user chose to try on the Pi. In hindsight the "impossible" verdict was wrong, because D2 got around it.

**D2. Fit BAR1 by moving the window's bus address and exposing only part of BAR1.**
- *What:* the overlay `v100-pcie` keeps pcie1's 14 GB CPU window at `0x18_0000_0000` but maps it to PCIe bus
  address `0x8_0000_0000`. `v100_bar.ko` programs BAR1 there and registers only the first 8 GB with Linux
  (`bar1_gb=8`). BAR3 (32 MB) goes into the 32-bit window after BAR0.
- *Why:* a BAR must sit at a multiple of its size, so a 32 GB BAR1 needs a 32 GB-aligned bus address, and the
  stock `0x4_0000_0000` isn't. The CPU-side window can't grow, because the next controller's range starts right
  after it.
  - The card still decodes all 32 GB on the bus, so nothing else may sit between bus `0x8_0000_0000` and
    `0xF_FFFF_FFFF`. That's why BAR3 went into the 32-bit window.
  - To the driver, 8 GB looks like a consumer card's small BAR.
- *Outcome:* works. Reads through BAR1 come back from the GPU, and with D14 RM keeps its own mappings inside the
  8 GB.

**D3. Use the closed 580.95.05 driver, patched for the Pi in its open "glue" layer.**
- *What:*
  - `nv_pi5_force_uncached=1` turns every sysmem buffer RM asks for as cached into an uncached one, and flushes
    its CPU cache lines.
  - CPU cache maintenance is never skipped on DMA mapping.
  - GPU registers are never mapped write-combined (`nv_pi5_no_iomap_wc=1`).
  - The driver version matches the installed userspace.
- *Why:* Volta needs the closed driver, and its RM core is a binary, so the fork's RM-level fixes can't be
  ported. Making all shared memory uncached was the bluntest fix possible from outside the blob. Matching the
  version avoids the userspace/kernel mismatch seen on Sep 14.
- *Outcome:* partly right. The GPU does need uncached memory (D12), but uncached memory broke the CPU's atomic
  instructions (D11-D13), and the flush helper had a bug (D10).

**D4. Install it permanently and boot into it.**
- *What:*
  - The overlay went into `config.txt`.
  - Both modules went into DKMS, with `softdep nvidia pre: v100_bar`.
  - The 4060 Ti driver was removed from DKMS.
  - A `blacklist` file was meant to stop NVIDIA modules loading on the first boot.
- *Why:* to survive kernel updates and to test with a single reboot.
- *Outcome:* the Pi wouldn't boot with the V100 attached. The cause was never found, because no logs survived.
  In hindsight:
  - Untested code went into the boot path with no fallback.
  - `blacklist` only stops automatic loading by device ID. Anything that loads `nvidia` by name still loads it,
    including the setuid `nvidia-modprobe` helper that NVIDIA's userspace uses (nvidia-smi, and the X driver
    installed here). The softdep then pulls in `v100_bar` too.
  - The driver at that point still had the two crash bugs found later (D10, D11).
  - The likely story is a load by name during boot that hit those bugs, but that is unverified.

### Phase 1, Sep 29: revert, then a safe method

**D5. Revert everything (the user's request), but keep the sources.**
The Pi then booted with the V100 attached, so the card alone doesn't block boot.

**D6. One change per boot; the overlay only through tryboot; modules only by hand.**
- *What:* `/boot/firmware/tryboot.txt` is `config.txt` plus `dtoverlay=v100-pcie`, booted with
  `reboot "0 tryboot"`. Modules are `insmod`ed from their build directories, with nothing in DKMS or autoload.
- *Why:* failed boots leave no logs, because the journal lives in RAM only. Tryboot applies once, and any
  power-cycle falls back to the normal config, so a bad boot can't lock the Pi out.
- *Outcome:* the overlay alone boots fine (19:27), and every failure since has been recoverable. Used for all
  runs.

**D7. Block every NVIDIA autoload with `install nvidia /bin/false` in `/etc/modprobe.d/v100-no-autoload.conf`.**
- *Why:* at ~19:41 a bare `nvidia-smi` hard-locked the Pi, and the 1-minute systemd watchdog reset it.
  `nvidia-modprobe` had loaded the 4060 Ti open driver against the V100, and a blacklist doesn't stop that.
- *Outcome:* no accidental loads since. Side effect: the 4060 Ti driver won't load either until this file is
  deleted.

**D8. Write the kernel log to disk synchronously (`dd if=/dev/kmsg ... oflag=dsync` in `load-v100.sh`).**
- *Why:* there is no persistent journal and no pstore. netconsole was offered, but it needs a second machine.
- *Outcome:* every run since has a complete `run-*.log`.

**D9. Reboot rule: if the driver is wedged, use `sync; reboot -ff "0 tryboot"`.**
- *Why:* a wedged driver blocks a clean shutdown. At 19:56 a plain reboot hung, and the Pi had to be unplugged.

### Phase 2: getting past the driver's own crashes

**D10. Fix our flush helper (`19763e5`).**
`nv_pi5_flush_alloc` synced a raw CPU address as if it were a DMA address. (`nv_phys_to_dma()` is a
pass-through here, because a build check looks in the wrong header.) That address is outside the Pi's DMA range,
so it oopsed. The helper now maps and unmaps each page with `dma_map_page`.

**D11. Instrument instead of guessing (`nv_pi5_debug=1`, `f563b88`).**
This logs every kernel mapping with its real address and its requested versus actual cache type. It identified
the buffer behind the atomic abort in one run.

**D12. Confirm the theory before fixing it: one run with `nv_pi5_force_uncached=0`.**
- The abort went away, which confirmed the theory, but Xid 62 (PMU halt) appeared instead.
- So the constraint cuts both ways:
  - NC memory breaks the CPU's atomic instructions; the BCM2712 answers them with an external abort.
  - Cached memory hides CPU writes from the GPU.

**D13. Add a size rule, `nv_pi5_nc_min_pages=2` (`67d88ec`).**
Buffers smaller than 2 pages stay cached (flushed once when allocated); larger ones are made NC.
- *Why:* the atomic hit a 1-page buffer, and the buffers the PMU needs are bigger. It was quick to build and
  test.
- *Outcome:* both failures are gone. But size is only a proxy: small buffers the GPU shares with the CPU are now
  cached and can go stale. That makes the rule a standing suspect for future silent-corruption bugs.
- **Correction (Step 1):** this review first said the rule had nothing to do with the self-test failure, because
  the test asks for an uncached buffer. That was wrong. RM turns the request into a cached one before it reaches
  the glue layer (D25), so the rule did keep the self-test's 1-page buffer cached.

**D14. Cap RM's view of BAR1 (`RMBar1ApertureSizeMB=8192`).**
- *Why:* RM read BAR1's 32 GB size from the hardware and mapped something near its top (`0x1fffdf0000`), which is
  outside the window.
- *Outcome:* the mappings moved inside the window, but the NULL dereference stayed. Kept in all later runs.

**D15. Try RM's verbose logging (`NVreg_ResmanDebugLevel=0`, `NVreg_RmMsg`).**
It printed nothing: the release blob has RM's own messages compiled out. From here on, all information came from
kprobes and disassembly.

**D16. Binary-patch the RM blob (`c572858`).**
The patch adds a NULL check to `_nv026674rm`, a helper of `fifoChidMgrIdleChannels`, so that it returns FALSE.
- *Why:* the NULL dereference sat in error-cleanup code. It hid the real error and wedged the driver on every run.
  The caller just skips an entry on FALSE, so the patch can't cause a loop.
- The first attempt wrote at the wrong offset. The file was restored from a backup and patched again.
- *Outcome:* the turning point.
  - No oops, no wedge, and a clean `rmmod`.
  - RM's real error appeared: Xid 79 + `RmInitAdapter failed! (0x25:0x40:1623)`. That means the GPU "load"
    stage failed with `NV_ERR_INVALID_STATE`.

### Phase 3: chasing Xid 79, which turned out to be a symptom

**D17. Test the "dead VRAM" theory.**
- After the failure, VRAM reads returned errors, which suggested broken VRAM.
- A probe before and after, plus a read-only register watcher during init, showed VRAM is fine while RM runs.
  - RM trains the HBM itself. That is normal on a Pi, because nothing runs the GPU BIOS at boot.
  - VRAM only goes bad during a 15 s PCIe outage in the teardown, so the theory was dropped.
- The run also showed two more things:
  - The card has no function-level reset; only a reboot resets it.
  - Reading VRAM through the PRAMIN window from userspace caused an MMU fault of its own, so the watcher stopped
    doing that.

**D18. Capture RM's call stack at every log print (`xid-trace.sh`).**
- The GPU stops answering ~5 ms after RM starts the PMU.
- Theory: the PMU changes the link speed or power state (ASPM), and the Pi's Gen2 link doesn't survive it.

**D19. Build a register tracer, `nvrtrace.ko`.**
It puts raw kprobes on RM's register read/write helpers.
- *Why:* the kernel's tracefs kprobes refuse to attach to functions inside the blob.
- *Outcome:* the main tool from here on (v1 to v5).

**D20. Lock the link speed and turn off ASPM (`RMPcieLinkSpeed=0x800000a8`, `RMDisableGpuASPMFlags=3`).**
- Both settings took effect, and neither helped, which ruled them out.
- The same run exposed a 192 ms clock skew between the watcher and dmesg. That skew had produced the earlier
  reading "Xid while BAR0 still read fine".

**D21. Hold 20 ms just before the PMU write (`nvrtrace` v2).**
The GPU stayed on the bus; an MMU fault showed up instead, and the PMU stalled. So "fallen off the bus" is a
consequence, not a cause.

**D22. Decode the fault (`nvrtrace` v3/v4, `pramin-walk.py`).**
- The PMU wrote to an address in its own address space after RM had unmapped it.
- v3 crashed in its own dump: it mapped only 2 MB of the GPU's register space. An earlier "dump tested OK" had in
  fact been reading unrelated memory.
- The crash happened to freeze RM with the GPU state intact, so the fault record was read from userspace instead.

### Phase 4, Oct 1: the root failure

**D23. Follow RM's call stacks back to the first function that failed, not to the first thing that looked
broken.**
- The unmap came from RM's cleanup. The first failure is `_nv042796rm`.
- That function matches `memmgrTestCeUtils` in the open RM source of the same version
  (`src/kernel/gpu/mem_mgr/mem_mgr.c:408`), identified by its magic values `0xAABBCCDD` and `0x11223345`.
- `memmgrInitCeUtils` creates RM's internal copy-engine channel and runs this test right away:
  1. The CE clears a word in VRAM, and the CPU writes `0xAABBCCDD` into it through a BAR.
  2. The CPU writes `0x11223345` into a 1-page **uncached** sysmem buffer.
  3. The CE copies the VRAM word into the sysmem buffer. RM waits until the CE's completion semaphore reaches
     the target value (a plain `>=` check).
  4. The CPU reads the sysmem buffer and compares. They don't match, so the test returns
     `NV_ERR_INVALID_STATE`.
- Every step returns OK, and the whole test takes ~80 us.
- On failure RM destroys the channel. That teardown (channels freed, copy engines reset, PMU mappings removed)
  produced every symptom seen since Sep 29.

**D24. Measure the mismatch before trying fixes (`nvrtrace` v5 with `ceu=1`, `link-trace.sh` v4).**
- It logs:
  - each step's return code;
  - the value the CPU read back;
  - the buffer's physical address;
  - what's in RAM there, read through the kernel's cached mapping before and after a cache invalidate.
- Ran on Oct 1 at 19:45 (run 16); see D25.

### Phase 5, Oct 1 evening: after the review

**D25. Step 1 result: the self-test buffer is CPU-mapped cached (run 16).**
- *The measurement:*
  - The CE wrote `AABBCCDD`, but the CPU read back `11223345`, its own earlier write.
  - Both the cached read and a read after a cache invalidate show `11223345`.
  - The buffer's kernel address is `ffffff8302af8000`, which is the cached linear-map address of physical
    `0x302af8000`. An uncached buffer would have a separate non-cacheable mapping at `0xffffffc0...`.
  - All earlier steps of the test returned OK.
- *Why it's cached:* the glue layer only hands out the linear map when the allocation is cached, so RM must have
  asked for cached memory. The open RM source explains it:
  - `osAllocPagesInternal` (`arch/nvalloc/unix/src/os.c:916`) forces `NV_MEMORY_CACHED` on arm64 whenever the
    chipset property `PDB_PROP_CL_IS_CHIPSET_IO_COHERENT` is set.
  - Stock RM sets that property to TRUE by default in OBJCL's constructor ("only Tegra chipsets override this").
  - The fork's first commit (`ac7630de`, "Query OS for chipset I/O cache coherency") removed that default and asks
    Linux instead (`dev_is_dma_coherent()`). That's what made the 4060 Ti work.
  - The closed blob still has the stock default. So on the Pi, RM believes PCIe is coherent and maps even the
    buffers it wants uncached as cached. My 2-page rule (D13) then leaves the 1-page ones cached.
- *What's still unknown:* whether the CE's write reached RAM at all. The CPU's dirty cache line from its own write
  can be written back over it, or the invalidate in the measurement can write it back, so the RAM value proves
  nothing either way. Other GPU DMA to RAM is known to work: RM's fault buffer, and the PMU reading its code.
- *Side note:* run 16 hit a bug in `link-trace.sh`: `/bin/sh` has no `jobs -r`, so the script stopped waiting
  after ~2 s. The measurement lines still made it to dmesg. Fixed in v5 of the script.

**D26. Step 2 fix: make RM's "chipset is I/O-coherent" default FALSE, with a one-byte binary patch (`c1ed779`).**
- *What:* in the blob's OBJCL constructor (`_nv000042rm`), `strb w1, [x0, #106]` becomes `strb wzr, [x0, #106]`
  (file offset `0x7af38`, `3901a801` to `3901a81f`).
  - How it was located: `rm_is_chipset_io_coherent`, which the blob exports, reads the property at
    `g_pSys->pCl + 106`. This constructor is the only place in the blob that stores to it.
  - The neighbouring byte (`+107`, "disable WC iomaps") is unchanged.
  - The previous build is kept as `/root/v100-pi/nvidia.ko.c572858` for A/B tests.
- *Why this fix:*
  - It's the same change the fork made for the working 4060 Ti, so RM behaves as it was designed to on a
    non-coherent platform. Uncached requests stay uncached, "default" requests become uncached, and copy-engine
    channels use non-snooped DMA.
  - RM's own comment says buffers that need CPU atomics are requested *cached* explicitly on ARM, so those should
    stay cached and not bring back the atomic crash from run 3.
  - Alternatives rejected:
    - Dropping the size rule (`nc_min_pages=1`) brings back the atomic crash.
    - A list of RM callers to keep cached would be fragile.
    - Patching only the allocation override in `os.c` is narrower, but it leaves RM's other "coherent" paths in
      place (snooped DMA, defaults turned cached).
- *What else changes:*
  - When RM asks for a full CPU cache flush, the glue layer now calls `flush_cache_all()`. arm64 doesn't have it,
    so it just prints `kernel does not provide flush_cache_all()` once. Seeing that in dmesg means RM relied on a
    flush that didn't happen.
  - If the atomic crash (LDXR external abort) returns, the atomic-used buffer wasn't requested cached, and it
    needs a separate fix.
- *Kept the same for this run* (one change per run): `nv_pi5_force_uncached=1`, `nv_pi5_nc_min_pages=2`, the
  regkeys, and the instrumentation.
- *Status:* run 17, no effect: it hit the wrong function (see D27).

**D27. Step 2 retry: `c1ed779` patched the wrong function; the real default is in `clConstruct` (`163fb0e`).**
- *What run 17 showed:* nothing changed. The self-test buffer was still CPU-mapped through the cached linear map.
  - `clpeek/clpeek.ko` is a tiny read-only module that reads `g_pSys->pCl->[106]`. It showed the flag
    (`IO_COHERENT`) still set to 1 at runtime.
- *Why:* `_nv000042rm` isn't the OBJCL constructor. It's a chipset setup function referenced by 6 entries of
  RM's chipset ID table, so it never runs on the Pi.
  - My earlier search only matched `strb w1, [x0, #106]` and missed the `strb w2, [x1, #106]` form.
  - The Pi's root port (14e4:2712) falls through to the table's terminating "Unknown" entry, whose setup function
    is NULL. So nothing overrides the constructor's default.
  - That default is set in `_nv019217rm`, the constructor called by OBJCL's NVOC create function
    (`_nv006544rm`). It stores `[106]=TRUE` (IO_COHERENT), `[128]=FALSE` (EnteredRecovery) and `[192]=NULL`
    (pPcieConfigSpaceBase). That matches stock `clConstruct_IMPL`, including the line the fork's `ac7630de`
    removed.
- *Fix:* `86da3e1` reverts `c1ed779`. `163fb0e` changes `_nv019217rm+0xc` from `strb w2` to `strb wzr` (file
  offset `0x79b7c`, `3901a822` to `3901a83f`). Verified in the rebuilt `nvidia.ko`.
  - Previous builds are kept for A/B tests: `nvidia.ko.c572858` and `nvidia.ko.c1ed779` (both leave the flag at 1).
- *Everything D26 says about why and what else changes still applies*, now to the right instruction.
- *Status:* works (run 18, Oct 1 20:14): RM init completes and `nvidia-smi` lists the GPU.

**D28. Step 4: UVM's allocations must be NC too, whatever their size (`3728361`).**
- *What run 19 showed:* `nvidia-uvm.ko` loads cleanly. The first CUDA call (`cuInit`) hangs in the UVM ioctl that
  registers the GPU (`channel_pool_add` -> `uvm_push_end_and_wait`, spinning in `uvm_spin_loop`, unkillable).
  - BAR0 (`fifo-dump.py`, read-only): no interrupt, no MMU fault, no busy engine. UVM's channel (ch 3, PBDMA 7,
    objects `c3b5` copy engine + `c076` UVM SW) has consumed its whole GPFIFO and pushbuffer.
  - The pushbuffer (`pb-decode.py`, via the channel's page tables) ends with a CE semaphore release: payload 1 to
    GPU VA `0x1_0100_0000`. That page is in sysmem, and RAM there reads 0. The CPU waits for 1.
  - RM maps UVM's sysmem with the *coherent* aperture, so it allocated it CACHED. (In the open source, RM asks
    for UVM sysmem as CACHED if `kbifIsSnoopDmaCapable()`.)
- *Why it fails:* UVM's semaphore pages are exactly one page. D13's rule keeps 1-page CACHED requests cached, so
  the CPU reads (and may write back) a stale cached line, and the GPU's release never becomes visible.
- *Fix:* in the glue, `nv_uvm_interface.c` marks the calling task around the UVM calls that make RM allocate
  sysmem (MemoryAllocSys, TsgAllocate, ChannelAllocate, PagingChannelAllocate, InitFaultInfo,
  InitAccessCntrInfo). `nv_alloc_pages` forces marked allocations NC whatever their size (`nv_pi5_uvm_uncached=1`).
  RM's own 1-page allocations stay cached, which keeps D13's fix for RM's CPU atomics.
  - Precedent: the fork ran the 4060 Ti's UVM on all-NC sysmem, so UVM itself copes with NC.
- *Status:* works (run 20, Oct 1 20:31): `cuInit` and context creation succeed.

**D29. libcuda's "flush user cache" requests must actually flush on arm64 (`4f88bf9`).**
- *What run 20 showed:* stage 2 (pageable 64 MB round trip) had 227k of 16.7M words wrong. `copy-diag.py` split
  it: only *pageable host-to-device* is bad. Device-to-host and pinned copies are fine at every size, and 64 KB is
  fine. Bad data comes in whole 64 B cache lines, and at 64 MB most of it equals the source from exactly 2 MB
  earlier: the GPU read stale contents of a reused 2 MB staging buffer.
- *Why:* libcuda's staging buffers are its own memory (two 2 MB `/dev/zero` shared mappings), pinned and
  registered with RM as OS-descriptor memory. They stay write-back cacheable in the process, which our NC rules
  can't touch. libcuda knows that and asks RM to flush them around each copy (`NV0000_CTRL_CMD_OS_UNIX_FLUSH_USER_CACHE`;
  kprobes: 8 `os_flush_user_cache` + 56 `os_flush_cpu_cache_all` calls for one 4 MB copy). On arm64 the stock glue
  turns both into `flush_cache_all()`, which arm64 doesn't have, and the fallback is `WARN_ONCE(0, ...)`, which
  never prints. So every flush was a silent no-op.
- *Fix:* the glue keeps a list of the allocations made by `nv_register_user_pages`. Both flush calls now run
  `DC CIVAC` (clean + invalidate in one step, so a concurrent CPU write is never lost) over every registered page
  through the linear map. `nv_pi5_debug=2` logs "user flush N pages".
  - Cost: it flushes every registered page on each call, not just the requested range (the blob doesn't pass the
    range). That's fine for 4 MB of staging, but a large `cuMemHostRegister` buffer would make every flush slower.
  - Not covered: RM's own 1-page CACHED allocations (D13) still get no flush on a "flush all". Nothing has
    failed because of that so far.
- *Status:* works (run 21, Oct 1 20:41). The driver reloaded cleanly without a reboot (rmmod `nvidia_uvm` +
  `nvidia`, then `cuda-run.sh`).

### How the work was run

- `STATUS.md` (newest first) and a memory note were updated before every reboot, because each reboot ends the
  Claude session. About 20 sessions so far picked up this way. Downside: `STATUS.md` is now 31 KB, and its time
  labels drift.
- Claude asked before every reboot, and the user OK'd all of them.
- Every tool version (`*.v1` to `*.v4`) and every run's logs are kept. They take 141 MB in `/root/v100-pi`, and the
  disk had 3.6 GB free (2.7 GB on Oct 1 19:45, after the user installed other software).
- A few sessions lost Bash to permission-checker errors. They fell back to reading files, or to asking the user to
  run commands.

## 4. What's established

**Works on this Pi**
- The V100 enumerates at Gen2 x1, and the Pi boots with it attached on the stock config.
- The overlay (via tryboot) boots fine.
- `v100_bar` assigns BAR1 (8 of 32 GB, CPU `0x18_0000_0000` = bus `0x8_0000_0000`) and BAR3 (32 MB at
  `0x1b_8200_0000`). The GPU answers through both.
- The closed driver builds in place and loads by hand. RM then:
  - runs devinit and trains the HBM (32 GB of VRAM, working);
  - writes its BAR1/BAR2 page tables (verified by hand);
  - boots the PMU (with NC sysmem);
  - creates its internal channels.
- The DMA addresses RM gives the GPU are correct bus addresses, inside the `0x10_0000_0000` inbound window.

**Hard constraints found**
- CPU atomics on NC memory cause an external abort on the BCM2712.
- The GPU doesn't see CPU writes to cached memory (Xid 62), because there is no coherency.
- RM's log messages are compiled out, and tracefs kprobes refuse blob functions. All visibility comes from our own
  kprobe module and from disassembly.
- There is no function-level reset. Every failed init costs a reboot, usually a forced one, because the driver
  wedges.

**Ruled out**
- The overlay as the boot blocker.
- The BAR1 top-of-aperture mapping.
- Dead VRAM.
- PCIe link speed and ASPM.
- "GPU fell off the bus" as a cause.
- `nv_phys_to_dma()` on RM's DMA path.

**Current blocker:** the CE-to-sysmem-to-CPU readback in RM's self-test. **Cause (Step 1):** stock RM's default
"chipset is I/O-coherent" makes RM map its uncached system-RAM buffers cached on arm64 (D25).

## 5. Conclusions

1. **The address-space problem is solved.** The overlay, `v100_bar` and `RMBar1ApertureSizeMB` together handle
   the blocker that looked fatal on Sep 24.
2. **What's left is the hard part: sharing system RAM between the CPU and the GPU over non-coherent PCIe.**
   - The self-test is a small, repeatable reproducer: four steps, ~80 us.
   - CUDA copies and llama.cpp depend on the same path, so it has to be fixed, not skipped.
   - It's the same kind of problem the 4060 Ti needed source-level driver fixes for, except that here the code
     is a binary.
3. **Most of the effort went into symptoms.**
   - From run 9 on, RM's own error was "invalid state", meaning a failed check, not a timeout or a hang.
   - Runs 10-14 still went after the dramatic after-effects: Xid 79, the GPU leaving the bus, the PMU fault.
   - Run 15 finally traced the failure back to where it was raised.
   - Lesson: when the driver reports an error code, find the first function that returned it before
     investigating the hardware symptoms that follow.
4. **The cache policy cuts both ways, and the current split is a heuristic.**
   - Memory the GPU touches has to be uncached.
   - Memory RM uses atomic instructions on has to be cached.
   - "Smaller than 2 pages = cached" happens to satisfy both for the cases hit so far. It's the most likely
     source of the next silent bug.
   - **Step 1 showed it already caused one** (D25), together with RM's own coherency assumption.
   - The principled split is the one RM itself makes on a non-coherent platform: honour RM's own cached/uncached
     choice, which needs RM to know the platform isn't coherent (D26).
5. **Our own tooling caused several failures and wrong readings:**
   - the flush-helper bug;
   - `nvrtrace` v3's 2 MB mapping, and the false "tested OK";
   - the watcher's PRAMIN reads;
   - a line-wrap bug in `load-v100.sh`'s overlay check;
   - a wrong `nvidia.ko` path given to the user;
   - a binary patch first written at the wrong offset;
   - the 192 ms clock skew.

   Lesson: check tools against a known state before trusting what they show.
6. **The method made this tractable and safe:** tryboot, loading by hand, logs synced to disk, one change per run,
   and the next tool built before each reboot. It's slow (5-15 minutes per run, a reboot each). That can't be
   helped while the GPU can't be reset and the driver wedges.
7. **Outlook.** Getting the self-test to pass looks reachable. The data path is small, and the next run should
   show which half of it fails.
   - After that, expect more of the same kind of bug, each needing a fix from outside the blob (glue layer,
     regkeys, binary patches):
     - other RM code that assumes coherency;
     - `nvidia-uvm`, which the CUDA runtime needs and which hasn't been tested;
     - pinned host memory used by CUDA.
   - Then come CUDA 12.9 (which needs disk space) and llama.cpp.
   - A working 32 GB V100 on the Pi is not close yet. An x86 host remains the low-risk route to one.

## 6. Next steps

### Step 1: run the prepared measurement (DONE, Oct 1 19:45, run 16)

**Result:** the first row of the table below, and the cause is the CPU side. The CPU read `11223345` through the
buffer's cached linear-map mapping, because RM had made the buffer cached (D25). Step 2 is therefore the
coherency fix in D26.

The commands as run:

```
cd /root/v100-pi && ./link-trace.sh
grep -E "nvrtrace: C|pi5dbg: kmap" run-1001-*.log | tail -30
```

The run will probably end wedged. Afterwards: `sync; reboot -ff "0 tryboot"`.

How to read the `C compare` and `C kmap#` lines:

| CPU read back | RAM at the buffer (after invalidate) | Meaning | Look at next |
|---|---|---|---|
| `11223345` | `AABBCCDD` | The CE's data arrived, but after the CPU's read or invisibly to it | Is the CPU mapping really NC (cache type in the `pi5dbg: kmap` line)? Did the completion semaphore become visible before the data (ordering)? |
| `11223345` | `11223345` | The CE's data wasn't in that page at compare time | (a) The wait ended early: log the semaphore value RM read against its target, and re-read RAM a few ms later. (b) The CE wrote elsewhere: log the CE's destination address and aperture against the page's DMA address |
| `00000000` | (any) | The CE copied the cleared word: the CPU's BAR write of `AABBCCDD` hadn't reached VRAM | The BAR write path: is the write flushed before the CE reads? Which BAR mapping, and which memory type, did RM use? |
| anything else | (any) | An address is wrong somewhere | Dump the CE's source and destination addresses |

Also compare the "linear-map read" and "after dc ivac" values. If they differ, a stale line for that page was
sitting in the CPU cache through the kernel's normal, cached mapping.

### Step 2: fix the path the measurement points to (DONE, Oct 1 20:14, run 18: works)

**Result (run 18, `run-1001-2014.log`):** `clpeek` reads `IO_COHERENT=0`. The self-test's sysmem buffer gets an NC
`vmalloc` mapping (`ffffffc0...`), the compare reads `aabbccdd` (match) and RAM holds `aabbccdd`. RM init completes
and `nvidia-smi` lists the GPU (rc 0, twice). No LDXR abort, no `flush_cache_all` message, no Xid.

**Chosen fix (D26, corrected in D27):** patch RM's "chipset is I/O-coherent" default to FALSE. The first try,
`c1ed779`, hit the wrong function (run 17, no effect). The retry is `163fb0e`, with `nvidia.ko` rebuilt.

**State at ~20:12:** the GPU is off the bus again after run 17, so a reset is required. `nvidia` is unloaded and
nothing is stuck. The reset is a clean `sync; reboot "0 tryboot"`. Then test:

```
od -An -tx1 /proc/device-tree/chosen/bootloader/tryboot        # 00 00 00 01
cd /root/v100-pi && ./link-trace.sh                              # v5
insmod clpeek/clpeek.ko psys=0x$(awk '$3=="_nv028167rm"{print $1}' /proc/kallsyms); dmesg | grep clpeek  # IO_COHERENT must be 0
grep -aE "nvrtrace: C|Xid|RmInit|flush_cache_all|external abort|Unable to handle" run-1001-*.log | tail -40
```

What to expect:
- The self-test's sysmem buffer should get an NC mapping (`C kmap va ffffffc0...`, not `ffffff8...`), and the
  compare should match.
- After that, init either finishes (`nvidia-smi` lists the GPU) or fails further on. Either way it's new ground.

Watch for:
- the atomic crash (LDXR external abort) coming back;
- `kernel does not provide flush_cache_all()`.

**Rollback:** `cp /root/v100-pi/nvidia.ko.c572858 /usr/src/nvidia-580.95.05-v100/nvidia.ko` (or `git revert
163fb0e` and rebuild).

The candidates considered before Step 1, kept for reference:
- **CPU side:** make CPU reads of RM's uncached buffers go only through an NC mapping, and invalidate the cached
  alias first (in the glue layer: the kernel-mapping code, or `dma_sync_*_for_cpu`).
- **Ordering:** make sure the CE's data write is visible before its completion write.
  - RM already leaves PCIe relaxed ordering off by default (`RmSetPCIERelaxedOrdering`=0), so this is less likely.
  - The GPU's `DevCtl` still permits relaxed ordering (`RlxdOrd+`). Clearing that bit with `setpci` before
    loading is a cheap one-boot test.
- **BAR side:** read back after RM's BAR writes, or change how BAR1/BAR2 are mapped.

### Step 3 (optional, one boot): skip the self-test to see what's behind it

The blob has a regkey, `RmDisableGlobalCeUtils`, that skips creating RM's CE channel and its self-test. This run
shows whether anything else blocks init, and whether `nvidia-smi` then lists the GPU:

```
./link-trace.sh "RMBar1ApertureSizeMB=8192;RMPcieLinkSpeed=0x800000a8;RMDisableGpuASPMFlags=3;RmDisableGlobalCeUtils=1"
```

This is diagnostic only. It hides the data-path bug, so nothing built on top of it can be trusted.

### Step 4: once `nvidia-smi` lists the GPU (IN PROGRESS)

**Status (Oct 1 20:45):** 4.1 and the correctness half of 4.4 are DONE (runs 20-21, D28 + D29). With `3728361` +
`4f88bf9`, `./cuda-run.sh 7` passes every `cuda-smoke.py` stage (libcuda + a PTX kernel JIT-compiled for sm_70; no
toolkit needed): init, pageable and pinned copies with compare, bandwidth, memset, kernel, zero-copy, managed
memory. `copy-diag.py` passes too. Next: 4.2 (disk space; 2.5 GB free now).

1. `nvidia-uvm.ko` was built alongside `nvidia.ko` but never loaded. Give it the same Pi treatment, because the
   CUDA runtime needs it.
2. **DONE (Oct 1 20:50):** CUDA 13.0 removed at your request (`/usr/local/cuda-13.0`, the symlink and its
   `ld.so.conf.d` entry; the driver's `libcuda` is separate and untouched). Free space went from 2.4 to 8.6 GB.
   The old 4060 Ti build in `/root/llama.cpp/build` no longer runs (it needed `libcudart.so.13`).
   Original options were:
   - remove CUDA 13.0 (only the 4060 Ti build of llama.cpp uses it);
   - compress the old traces with `xz` (~140 MB);
   - use external storage.
3. **DONE (Oct 1 20:58), differently than planned:** instead of the ~4 GB runfile (which would not have fit),
   I installed NVIDIA's per-component redistributable tarballs for 12.9.1 linux-sbsa (sha256 checked): nvcc,
   cudart, cuBLAS, CCCL, NVRTC, NVML headers, profiler API, cuobjdump, nvdisasm. That's 1 GB to download and
   2.5 GB installed in `/usr/local/cuda-12.9` (`lib64` -> `lib`), with `/usr/local/cuda` pointing to it and
   `/etc/ld.so.conf.d/cuda-12-9.conf`. 6.1 GB is free afterwards.
   - glibc 2.41 (Debian 13) declares `sinpi`/`cospi` `noexcept`, and CUDA 12.9's `crt/math_functions.h` does
     not, so nvcc fails on any file that includes `<cmath>`. I added `noexcept (true)` to those 4
     declarations; the original is kept as `math_functions.h.orig`.
4. **DONE (Oct 1 20:58):** correctness before speed. `cuda-smoke.py` + `copy-diag.py` (runs 20-21), then
   `cublas-test.cu` built with nvcc for sm_70: saxpy exact, SGEMM 1024 max error 1.9e-5 against the CPU, SGEMM
   4096 at 12.0 TFLOPS fp32, tensor-core HGEMM at 81 TFLOPS. Copies run at ~0.4 GB/s each way (gen2 x1).
5. **DONE (Oct 1 ~21:35):** llama.cpp `bbdd9f2` built in `/root/llama.cpp/build-v100` (CUDA 12.9, sm_70, ~35 min). Then pick a
   model that fits in 32 GB.
6. Put a fan on the V100 before any real load; it has a passive heatsink.

### Step 5: make it permanent only once it works

**Status (Oct 1 ~22:00): DONE, verified after a normal reboot** (tryboot 0, overlay applied, nothing loaded at boot, on-demand load via the guard, `cuda-smoke.py 7` all OK, llama-bench 2787 / 99.6 t/s). Was (21:52): installed and tested live. Done differently from the
original plan: nothing loads the driver at boot any more. It loads on demand, behind a guard.
1. **DKMS:** `nvidia/580.95.05-noncoherent` (4060 Ti) removed; its source stays in `/usr/src`. `v100-bar/1.0` and
   `nvidia/580.95.05-v100` installed. The DKMS `nvidia.ko` is identical to the tested build (debug info aside).
2. **`/etc/modprobe.d/v100.conf`** replaces `v100-no-autoload.conf` (copy kept in `/root/v100-pi`):
   - the nvidia modules are blacklisted, so udev never loads them at boot;
   - an explicit load (`nvidia-smi` and libcuda call `nvidia-modprobe`, or `modprobe nvidia`) goes through
     `/usr/local/sbin/v100-modprobe-guard`. It loads `v100_bar` first, then `nvidia` / `nvidia_uvm`, with the
     options from runs 18-21;
   - the guard refuses if the overlay isn't active, if `v100.noload` is on the kernel command line, or if
     `/var/lib/v100/loading` exists. It creates that marker before a load and removes it after, so a load that
     hangs the Pi (and gets it reset by the watchdog) is not retried until you `rm` the marker;
   - `nvidia_drm`, `nvidia_modeset` and `nvidia_peermem` never load.
3. **Overlay in `config.txt`:** it is now identical to `tryboot.txt`. Backups: `config.txt.bak-pre-step5` and
   `config.txt.bak-pre-v100`.
- Live test without a reboot (unloaded `nvidia_uvm` + `nvidia`): a plain `nvidia-smi` loaded everything with the
  right parameters; `cuda-smoke.py 7` passed and llama-bench gave 2717 / 99 t/s.
- **To verify:** a normal `reboot`. Then check that `tryboot` is 0, the overlay is applied and nothing nvidia
  loaded at boot; that `nvidia-smi` loads the stack; and that `cuda-smoke.py 7` and llama-bench pass.
- **If the Pi doesn't boot:** take out the SD card and, on another computer, copy `config.txt.bak-pre-step5`
  over `config.txt` on the boot partition (or add `v100.noload` to `cmdline.txt` if the hang is in the driver).
- `load-v100.sh` and `cuda-run.sh` are no longer needed, and `reboot "0 tryboot"` is no longer needed either.

### Decision point

It's worth stepping back if Step 1 shows that the CE's writes never reach RAM. The same goes for a fix that would
need changes deep inside RM, out of reach of the glue layer, regkeys or small binary patches. Options then:
- **An x86 PC or server with Above-4G decoding.** The standard, low-risk setup: the 580 driver, CUDA 12.9 and
  llama.cpp built for arch 70.
- **The 4060 Ti back in the Pi.** Known to work (see below).
- **The fully open route (not checked).** That means the nouveau kernel driver, a Vulkan driver and llama.cpp's
  Vulkan backend. The appeal is that coherency fixes could be made in source, as the fork did for the 4060 Ti. But
  this kernel doesn't ship nouveau, and Volta support in the Vulkan driver hasn't been verified.

### If you put the 4060 Ti back

Since Step 5: remove `/etc/modprobe.d/v100.conf`, `dkms remove nvidia/580.95.05-v100 --all` and
`v100-bar/1.0`, then `dkms install nvidia/580.95.05-noncoherent` (its source is still in `/usr/src`), and restore
`config.txt.bak-pre-v100` on the boot partition.

## 7. Reference

- **Scripts and logs in `/root/v100-pi`:**
  - `STATUS.md`: the running log, newest first.
  - `load-v100.sh [nvidia.ko params]`: checks the overlay, loads `v100_bar` and the patched `nvidia.ko`, and syncs
    the kernel log to `run-*.log`.
  - `link-trace.sh ["RegistryDwords"]` (v5): the full instrumented run (register trace, RM print stacks, link
    watcher, `nvidia-smi`).
  - `nvrtrace/nvrtrace.c` (v5): the kprobe tracer. Params: `reads`, `probe`, `predelay_ms`, `sample_us`,
    `pmu_pdb`, `watch_va`, `ib_bus`, `ceu`, `dump_now`.
  - Helpers: `link-watch.py`, `vram-probe.py`, `vram-watch.py`, `xid-trace.sh`, `pramin-walk.py`, `vram-scan.py`.
- **BAR fix:** sources `v100_bar.c` and `v100-pcie-overlay.dts`. Installed: `/boot/firmware/overlays/v100-pcie.dtbo`,
  `/boot/firmware/tryboot.txt` and `/etc/modprobe.d/v100-no-autoload.conf`.
- **Patched closed driver (git repo):** `/usr/src/nvidia-580.95.05-v100`.
  - Commits: `7c9babd` base Pi patches, `19763e5` flush fix, `f563b88` debug prints, `67d88ec` `nc_min_pages`,
    `c572858` blob NULL check, `c1ed779` blob coherency default FALSE (D26, wrong function, reverted by
    `86da3e1`), `163fb0e` the same patch in `clConstruct` (D27), `3728361` UVM allocations NC (D28), `4f88bf9`
    user-page cache flush (D29).
  - Earlier builds are kept at `/root/v100-pi/nvidia.ko.c572858`, `nvidia.ko.c1ed779` and `nvidia.ko.3728361`.
  - CUDA tests: `cuda-run.sh [stage]` (loads everything, then runs `cuda-smoke.py`), `copy-diag.py` (copy
    corruption by path and size), `fifo-dump.py`, `pb-decode.py`.
  - `clpeek/clpeek.ko psys=<addr of _nv028167rm>`: prints RM's IO_COHERENT flag, then refuses to stay loaded.
  - Build: `make -j4 SYSSRC=/lib/modules/$K/source SYSOUT=/lib/modules/$K/build IGNORE_CC_MISMATCH=1 modules`.
- **Open RM source of the same version:** `/usr/src/nvidia-580.95.05-noncoherent/src`, for reading RM code (the
  CeUtils test, regkeys).
- **Driver params:** `nv_pi5_force_uncached` (default 1), `nv_pi5_no_iomap_wc` (default 1), `nv_pi5_nc_min_pages`
  (default 1; the runs use 2), `nv_pi5_uvm_uncached` (default 1), `nv_pi5_debug` (2 = also log user flushes).
- **Regkeys in use:** `RMBar1ApertureSizeMB=8192;RMPcieLinkSpeed=0x800000a8;RMDisableGpuASPMFlags=3`.
- **Boot check:** `od -An -tx1 /proc/device-tree/chosen/bootloader/tryboot` should print `00 00 00 01`.
- **Reboot:** `sync; reboot "0 tryboot"` when clean, `sync; reboot -ff "0 tryboot"` when wedged.
