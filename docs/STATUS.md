# 2026-10-01 ~22:00 (Pi clock; `date` said 21:42, clock lags): STEP 5 VERIFIED after a NORMAL reboot. The V100 setup is now permanent.
- tryboot=0 (normal config.txt), pcie@1000110000 ranges 2nd entry 43000000 00000008 (overlay applied). Nothing nvidia at boot;
  first load at 186 s, ~7 s after the user's root login (on demand via v100-guard: v100_bar, nvidia, nvidia_uvm). No marker left.
- nvidia-smi rc=0 (V100 32GB, 30C, 31W). cuda-smoke.py 7 ALL OK (pinned 0.40/0.42 GB/s). llama-bench Qwen2.5-7B Q4_K_M -ngl 99:
  pp512 2787, tg128 99.6 t/s (llama-bench-2.txt). No Xid/abort/oops in dmesg.
- Next (open): storage for a ~30B model (SD card ~5 GB free); optional cleanup of old traces/builds.
# 2026-10-01 21:55 (Pi clock): user OK ("Yes, reboot now") -> Claude ran sync; reboot (NORMAL, clean). Next: verify per the 21:52 entry.
# 2026-10-01 21:52 (Pi clock): STEP 5 INSTALLED, needs one normal reboot to verify.
- DKMS: nvidia/580.95.05-noncoherent REMOVED (source kept in /usr/src, re-add to go back), v100-bar/1.0 + nvidia/580.95.05-v100 INSTALLED
  (dkms nvidia.ko == tested /usr/src build after strip --strip-debug, srcversion B7BF03810697D711E05FA15, blob patch 3901a83f present). dkms-v100.log.
- /etc/modprobe.d/v100-no-autoload.conf deleted (copy: v100-no-autoload.conf.bak). New /etc/modprobe.d/v100.conf: blacklist (no udev autoload),
  install nvidia/nvidia_uvm -> /usr/local/sbin/v100-modprobe-guard (needs overlay active, no v100.noload on cmdline, no crash marker
  /var/lib/v100/loading; loads v100_bar first), drm/modeset/peermem -> /bin/false, options nc_min_pages=2 + RegistryDwords.
- Guard bug fixed: nvidia-modprobe gives modprobe an empty env -> set PATH in the script. (A stray test of mine ran the guard once
  with a bogus option: rc=141, nothing loaded.) Marker refusal tested (rc=1).
- Live test (rmmod nvidia_uvm nvidia, v100_bar kept): bare nvidia-smi -> guard loaded nvidia + nvidia_uvm with the right params;
  cuda-smoke.py 7 ALL OK; llama-bench 2717 pp512 / 99.3 tg128. No Xid.
- /boot/firmware/config.txt now == tryboot.txt (dtoverlay=v100-pcie under [all]); backup config.txt.bak-pre-step5.
- Next: user OK -> sync; reboot (NORMAL). Check: tryboot=0, ranges 2nd entry 43000000 00000008, nothing nvidia loaded at boot,
  then nvidia-smi (guard loads v100_bar+nvidia), cuda-smoke.py 7, llama-bench.
# 2026-10-01 21:45 (Pi clock): STEP 5 started (user: "go on with the next step"). Plan: DKMS swap (noncoherent out, nvidia/580.95.05-v100 + v100-bar/1.0 in), modprobe.d guard (load on demand via nvidia-modprobe only if overlay applied + no crash marker /var/lib/v100/loading), then overlay into config.txt + normal reboot.
# 2026-10-01 21:33 (Pi clock): FIRST LLM INFERENCE ON THE V100 (user confirmed fan fitted). llama-bench Qwen2.5-7B-Instruct Q4_K_M -ngl 99: pp512 2752 t/s, tg128 99.4 t/s; peak 39C / 181 W at 1380 MHz (thermal-bench-1.txt, llama-bench-1.txt). llama-completion temp 0: correct answers (Canberra, 391, Jupiter), 95 t/s (llama-gen-1.txt). No Xid. Next: REVIEW Step 5 (make permanent, tryboot-tested step by step) + storage for a ~30B model.
# 2026-10-01 ~21:35 (Pi clock): llama.cpp (bbdd9f2) BUILT in /root/llama.cpp/build-v100 (CUDA 12.9, sm_70, Release, ninja 572/572, ~35 min; log llama-build.log). Links libcudart.so.12/libcublas.so.12 from /usr/local/cuda-12.9 + driver libcuda. Only harmless warning: server web UI dist.tar.gz download failed. 5.3G free. Only model on disk: /root/models/Qwen2.5-7B-Instruct-Q4_K_M.gguf (4.7G); a ~30B model will not fit on the SD card. Next: first inference run - needs a fan on the V100 first (passive heatsink).
# 2026-10-01 20:58 (Pi clock): CUDA 12.9.1 TOOLKIT INSTALLED from NVIDIA redist tarballs (linux-sbsa, sha256 OK; nvcc cudart cublas cccl nvrtc nvml_dev profiler_api cuobjdump nvdisasm, 1 GB dl, 2.5 GB) -> /usr/local/cuda-12.9 (lib64 -> lib), /usr/local/cuda symlink, /etc/ld.so.conf.d/cuda-12-9.conf. glibc 2.41 fix: noexcept(true) on sinpi/sinpif/cospi/cospif in include/crt/math_functions.h (orig .orig). cublas-test.cu (nvcc -arch=sm_70): saxpy OK, sgemm1024 err 1.9e-5 OK, 12.0 TFLOPS fp32, 81 TFLOPS hgemm TC, 31C. 6.1G free. Next: llama.cpp build-v100 (sm_70).
# 2026-10-01 20:50 (Pi clock): user OK ("remove cuda 13"): rm -rf /usr/local/cuda-13.0 + /usr/local/cuda symlink + /etc/ld.so.conf.d/cuda-13-0.conf, ldconfig. Driver libcuda (/lib/aarch64-linux-gnu, 580.95.05) untouched, cuInit OK. Free 2.4G -> 8.6G. /root/llama.cpp/build (4060Ti, libcudart.so.13) is now broken. Next: CUDA 12.9 toolkit (runfile --toolkit only).
# 2026-10-01 20:45 (Pi clock): STEP 4 RUN 21: CUDA WORKS (3728361 + 4f88bf9). No reboot: rmmod nvidia_uvm nvidia (GPU stayed
#   on the bus), ./cuda-run.sh 7 -> ALL 7 stages OK (pageable+pinned copies, memset, PTX JIT sm_70, zero-copy, managed/UVM),
#   pinned ~0.40/0.42 GB/s (gen2 x1). copy-diag.py all 20 checks OK (copy-diag-2.txt). No Xid/abort. Log cuda-run-2041.log.
#   State: nvidia + nvidia_uvm + v100_bar loaded, healthy. REVIEW.md updated (D29, runs 20-21). Next: REVIEW Step 4.2 (disk,
#   CUDA 12.9 toolkit, llama.cpp sm_70, fan).
# 2026-10-01 20:40 (Pi clock): STEP 4 RUN (2031): UVM FIX 3728361 WORKS - cuInit + cuCtxCreate OK (driver 13000, sm_70, 32494 MB).
- Stage 2 FAILS: pageable round trip 227456/16.7M words bad. copy-diag.py (copy-diag-1.txt): ONLY pageable H2D is bad
  (D2H pageable/pinned and pinned H2D all OK, 64KB OK); bad data = whole 64B lines, at 64MB = src from -2MB (stale staging).
- Staging buffers = 2x 2MB "/dev/zero (deleted)" MAP_SHARED in the process (OS-descriptor user pages, write-back mapped).
  kprobes: one 4MB pageable H2D -> 8x os_flush_user_cache, 56x os_flush_cpu_cache_all (libcuda's FLUSH_USER_CACHE ctrl).
  On arm64 both -> flush_cache_all(), which doesn't exist (WARN_ONCE(0,..) never prints) -> NO-OP -> CE reads stale DRAM.
- Fix 4f88bf9 (glue): track nv_register_user_pages allocs; os_flush_user_cache/os_flush_cpu_cache_all DC CIVAC every
  registered page by VA (nv_pi5_debug=2 prints "user flush N pages"). Built 20:39, build-userflush.log; prev nvidia.ko.3728361.
- State: not wedged. Next: rmmod nvidia_uvm nvidia; ./cuda-run.sh 7 (if GPU drops off the bus -> user OK -> reboot "0 tryboot").
# 2026-10-01 20:31 (Pi clock): tryboot OK (tryboot=1, overlay applied, GPU on the bus, clean, nothing loaded). Running ./cuda-run.sh 7 (tests 3728361) -> cuda-run-2031.log.
# 2026-10-01 20:37 (Pi clock): user OK ("go on, reboot") -> Claude ran sync; reboot -ff "0 tryboot" (wedged UVM ioctl). Next: check tryboot=1 + overlay, ./cuda-run.sh 7 (tests 3728361).
# 2026-10-01 20:35 (Pi clock): STEP 4 RUN 19: cuInit HANGS in UVM GPU registration -> fix 3728361 BUILT (not tested).
- cuda-smoke.py 1 (cuInit) stuck R-state, unkillable: uvm_api_register_gpu -> add_gpu -> uvm_channel_manager_create ->
  channel_pool_add -> uvm_push_end_and_wait -> uvm_spin_loop (sysrq-l backtrace).
- fifo-dump.py (read-only BAR0): no PFIFO/PBDMA intr, no MMU fault. ch0-3 enabled. ch2 = RM GR (902d, PBDMA0), ch3 =
  UVM CE channel (c3b5 + c076 UVM_SW, PBDMA7, inst 0x7fd6e9000): GP_GET==GP_PUT, GET==PUT -> GPU consumed everything.
- pb-decode.py: ch3 push = CE SEMAPHORE_A/B 0x1_01000000 payload 1, LAUNCH_DMA 0xc (flush + release).
  pramin-walk: VA 0x101000000 -> sysmem bus 0x120accb000 aperture 2 (SYS COHERENT => RM allocated it CACHED);
  DRAM there (/dev/mem O_SYNC) = 0. UVM semaphore page = 1 page (UVM_SEMAPHORE_PAGE_SIZE) -> nc_min_pages=2 kept it cached.
- Fix 3728361 (glue): nv_uvm_interface.c marks current task around rm_gpu_ops_{memory_alloc_sys,tsg_allocate,
  channel_allocate,init_fault_info,init_access_cntr_info,paging_channel_allocate}; nv_alloc_pages forces marked CACHED
  allocs NC regardless of size (param nv_pi5_uvm_uncached=1; pi5dbg prints "UVM alloc +N pages forced uncached").
  nvidia.ko rebuilt 20:26 (blob patch 163fb0e verified present). Build log build-uvmnc.log.
- New tools: cuda-smoke.py (staged libcuda/PTX test, no toolkit), fifo-dump.py, pb-decode.py, cuda-run.sh (next boot).
- State: WEDGED (UVM ioctl unkillable; nvidia+nvidia_uvm loaded; GPU healthy). Next: user OK -> sync; reboot -ff "0 tryboot";
  check tryboot=1; ./cuda-run.sh 7 ; on hang re-run fifo-dump.py + sysrq-l.
# 2026-10-01 20:30 (Pi clock): STEP 4 started: insmod nvidia-uvm.ko (stock UVM = fork UVM modulo feature gates; loads clean, major 505), mknod /dev/nvidia-uvm{,-tools}, nv_pi5_debug=0. Running ./cuda-smoke.py stage by stage (libcuda + PTX JIT, no toolkit).
# 2026-10-01 20:20 (Pi clock): STEP 2 WORKS (run 2014, 163fb0e) - nvidia-smi LISTS THE V100. RmInitAdapter succeeds.
- clpeek: IO_COHERENT[106]=0 at runtime. CeUtils self-test: all rcs 0, compare vid=aabbccdd sys(readback)=aabbccdd MATCH;
  sysmem surface now kmapped via vmalloc (ffffffc0..., NC), DRAM holds aabbccdd. No Xid, no RmInit error, no LDXR, no oops.
- nvidia-smi: Tesla V100-PCIE-32GB, 32768 MiB, BAR1 8192 MiB, PCIe gen2 x1 (regkey lock), 32-33C, ~32W P0, ECC on.
  A second nvidia-smi (re-init, no persistence mode) also rc=0. Log run-1001-2014.log, trace link-trace-2014.txt.
- State: nvidia + v100_bar loaded, GPU healthy. Next = REVIEW.md Step 4 (nvidia-uvm Pi treatment, disk space, CUDA 12.9 toolkit).
# 2026-10-01 20:15 (Pi clock): tryboot OK (tryboot=1, overlay applied, GPU back on the bus, clean, nvidia.ko = 163fb0e build). Running ./link-trace.sh = Step 2 retest (163fb0e).
# 2026-10-01 20:14 (Pi clock): user OK ("go on reboot") -> Claude ran sync; reboot "0 tryboot" (clean, nothing wedged). Next: check tryboot=1 + overlay, ./link-trace.sh (tests 163fb0e), clpeek check (IO_COHERENT must be 0), grep -aE "nvrtrace: C|Xid|RmInit|flush_cache_all|external abort|Unable to handle" run-*.log
# 2026-10-01 20:12 (Pi clock): STEP 2 RUN (2002) = c1ed779 HAD NO EFFECT; patched the WRONG function. Real fix built: 163fb0e.
- Run 2002: same as 1945: C compare vid=aabbccdd sys=11223345 MISMATCH, sysmem surface still kmapped via the cached LINEAR
  map (ffffff830cb0c000), Xid 79, RmInitAdapter 0x25:0x40, not wedged. No LDXR, no flush_cache_all msg. Log run-1001-2002.log.
- clpeek/clpeek.ko (reads g_pSys(_nv028167rm)->[520]=pCl ->[106] via get_kernel_nofault, never stays loaded):
  IO_COHERENT[106]=1 at runtime with c1ed779 loaded, [107]=0.
- Why: _nv000042rm is NOT the OBJCL ctor; it is a chipset-table setupFunc (6 entries, never runs on the Pi). The earlier
  "only store" search missed `strb w2,[x1,#106]`. The Pi (14e4:2712) hits the table's terminating "Unknown" entry
  (.data 0x97a8, vendor/dev 0), whose setupFunc is NULL -> nothing overrides the ctor default.
  The default: _nv019217rm = stock clConstruct_IMPL (called by OBJCL objCreate _nv006544rm, size 0x498):
  [106]=1 (IO_COHERENT), [128]=0 (EnteredRecovery), [192]=NULL (pPcieConfigSpaceBase) - matches the fork's source minus
  the line ac7630de removed. 10 other identical "mov w2,#1; strb w2,[x1,#106]" stubs are chipset-table setupFuncs.
- Fix: 86da3e1 reverts c1ed779; 163fb0e patches _nv019217rm+0xc strb w2 -> strb wzr (file off 0x79b7c, 3901a822->3901a83f).
  nvidia.ko rebuilt 20:10 (verified in the .ko). Old builds: nvidia.ko.c572858, nvidia.ko.c1ed779 (both IO_COHERENT=1).
- State: GPU OFF THE BUS again (config all-ones) -> needs reset. nvidia rmmod'ed clean, v100_bar loaded.
  Next: user OK -> sync; reboot "0 tryboot"; ./link-trace.sh; check: insmod clpeek/clpeek.ko psys=0x$(awk '$3=="_nv028167rm"{print $1}' /proc/kallsyms)
  -> IO_COHERENT must be 0; grep -aE "nvrtrace: C|Xid|RmInit|flush_cache_all|external abort|Unable to handle" run-*.log
# 2026-10-01 20:03 (Pi clock): tryboot OK (tryboot=1, overlay applied, GPU back on the bus, clean). Running ./link-trace.sh (v5) = Step 2 test of c1ed779.
# 2026-10-01 20:08 (Pi clock): user OK ("go on, reboot") -> Claude ran sync; reboot "0 tryboot" (clean, nothing wedged). Next: check tryboot=1 + overlay, ./link-trace.sh (v5) to test c1ed779 (coherency default FALSE); grep -aE "nvrtrace: C|Xid|RmInit|flush_cache_all|external abort" run-*.log; then update REVIEW.md Step 2.
# 2026-10-01 20:05 (Pi clock): GPU OFF THE BUS since run 1945 (config space all-ones, lspci "Unknown header type 7f"; did not recover like the earlier ~15 s outages). nvidia unloaded (clean), v100_bar loaded. Needs a reset: user OK -> sync; reboot "0 tryboot" (clean); then ./link-trace.sh (v5) to test c1ed779.
# 2026-10-01 19:58 (Pi clock): STEP 2 FIX BUILT: blob commit c1ed779 = OBJCL ctor _nv000042rm+0x8 strb w1 -> strb wzr [x0,#106]
#   (PDB_PROP_CL_IS_CHIPSET_IO_COHERENT default FALSE, like fork ac7630de). nvidia.ko rebuilt; old build saved as
#   /root/v100-pi/nvidia.ko.c572858. link-trace.sh v5 (nvidia-smi wait fixed). rmmod nvidia clean; v100_bar loaded; GPU needs reset.
#   Next: user OK -> sync; reboot "0 tryboot" (clean); ./link-trace.sh; grep -aE "nvrtrace: C|Xid|RmInit|flush_cache_all|external abort" run-*.log
# 2026-10-01 19:50 (Pi clock): STEP 1 DONE (run 1945, link-trace v4 / nvrtrace v5): self-test buffer is CPU-MAPPED CACHED.
- C lines: all steps rc=0; compare vid=aabbccdd sys(readback)=11223345 MISMATCH; sysmem surface kmap va ffffff8302af8000
  = LINEAR MAP of pa 0x302af8000 (cached), not an NC vmap -> RM handed it to the glue layer as CACHED although
  memmgrTestCeUtils asks NV_MEMORY_UNCACHED; nc_min_pages=2 kept the 1-page alloc cached. DRAM after dc ivac = 11223345
  (inconclusive: dirty line can be written back over the CE's data).
- Why: open RM os.c:916 osAllocPagesInternal forces NV_MEMORY_CACHED on arm64 if PDB_PROP_CL_IS_CHIPSET_IO_COHERENT;
  stock clConstruct sets it TRUE by default (fork commit ac7630de removed that and queries dev_is_dma_coherent()).
  Blob: rm_is_chipset_io_coherent reads g_pSys(_nv028167rm)->[520]=pCl ->[106]; the only store is _nv000042rm+0x8
  (= stock OBJCL ctor: strb w1,[x0,#106]; +107 = DISABLE_IOMAP_WC conditional).
- Not wedged (nv_queue S); Xid 79 + RmInitAdapter 0x25:0x40 as before. link-trace.sh bug: dash has no `jobs -r`.
- Next (Step 2): binary-patch _nv000042rm+0x8 -> strb wzr (IO_COHERENT default FALSE, like the fork), rebuild, rerun.
# 2026-10-01 19:45 (Pi clock): tryboot OK (tryboot=1, overlay applied, clean). Running ./link-trace.sh v4 (nvrtrace v5 ceu=1) = REVIEW.md Step 1.
# 2026-10-01 19:30 (Pi clock): REVIEW.md written (every decision + why, conclusions, next steps). State: tryboot=1, overlay applied, clean, nothing loaded (up since ~19:10). Next unchanged: ./link-trace.sh; grep -E "nvrtrace: C|pi5dbg: kmap" run-*.log
# 2026-10-01 ~19:25 (Pi clock): user OK ("go on and reboot") -> Claude ran sync; reboot -ff "0 tryboot" (wedged). Next: check tryboot=1 + overlay, ./link-trace.sh, grep -E "nvrtrace: C|pi5dbg: kmap" run-*.log
# 2026-10-01 19:20 (Pi clock): ROOT FAILURE FOUND - RM's CeUtils SELF-TEST FAILS; the PMU fault/Xid 79 is only the UNWIND.
- link-trace 1858 (nvrtrace v4 V lines): PMU VA 0x4010000 IS mapped (inval#2-4 -> vidmem 0x7fdba8000), then unmapped
  (inval#5/6) and the whole PD3 wiped ~65us before the ENGCTL write. Dmesg = trace(mono) + 0.2867s.
- Decoded the trace with RM stacks (nvp kprobe): _nv042802rm creates internal channel 0 (_nv042903rm) and channel 1 via
  _nv042796rm = memmgrTestCeUtils (open src: src/kernel/gpu/mem_mgr/mem_mgr.c:408, magic 0xAABBCCDD/0x11223345):
  CE memset vid=0, CPU write vid=AABBCCDD, CPU write 1-page UNCACHED sysmem=11223345, CE copy vid->sys, CPU read sys,
  compare -> MISMATCH -> NV_ERR_INVALID_STATE (0x40, line 602) = the RmInitAdapter 0x25:0x40. All 5 calls return OK (~80us).
  Then RM unwinds: ch1/ch0 unbind, VAS 7fdf64/7fdf6c freed, all CEs reset, PMU VAS unmapped -> PMU ctxsw-save (ENGCTL=1)
  faults on its freed VA (NR fault) / with no hold drops the GPU off PCIe (Xid 79). Everything since 09-29 21:35 = symptom.
- nc_min_pages rule only touches CACHED requests; this surface is requested UNCACHED -> stays NC. So not that (directly).
- Built nvrtrace v5 (ceu=1: "C" lines = rc of each test step, compared values, kmap PA of the sysmem surface + its DRAM
  value via linear map before/after dc ivac). Load-tested OK (renamed copy). link-trace.sh v4: probe=0 ceu=1, nv_pi5_debug=1.
  Old: nvrtrace.c.v4, link-trace.sh.v3. Trace: link-trace-1858.txt, run-1001-1858.log.
- Readback tells: 11223345 = CE write not seen (DRAM value then says wrong address vs stale/completion), 00000000 = CPU
  vid write (BAR path) lost, else other.
- State: WEDGED (60s PMU poll + memcpy_toio oops, nv_queue D). Next: user OK -> sync; reboot -ff "0 tryboot";
  ./link-trace.sh; grep -E "nvrtrace: C|pi5dbg: kmap" run-*.log | tail -30
# 2026-10-01 18:58 (Pi clock): tryboot OK (tryboot=1, overlay applied, clean). Running ./link-trace.sh (nvrtrace v4).
# 2026-10-01 ~19:00 (Pi clock): user OK ("carry on") -> Claude ran sync; reboot -ff "0 tryboot" (wedged). Next: check tryboot=1 + overlay, ./link-trace.sh, grep -E "nvrtrace: (V|F|P)" run-*.log
# 2026-10-01 18:55 (Pi clock): NR FAULT PACKET DECODED - the PMU faults on an UNMAPPED VA in its own address space.
- link-trace 1841 (nvrtrace v3): v3 OOPSED in its own dump (bar0 ioremap was 2M, PRAMIN is BAR0+0x700000 -> the 18:55
  "walk ok" test was reading unrelated vmalloc memory). The oops killed RM's init thread inside the ENGCTL kprobe, so
  RM never tore down -> read everything from userspace afterwards (pramin-walk.py v2 = [VA [INST]], sysmem via /dev/mem).
- Packet (sysmem bus 0x130f870000): fdf7e000 00000007 04010000 00000000 115d56c0 18da78b4 00000006 80111200
  = inst 0x7fdf7e000 (PMU instblk), ENGINE 6 = PWR_PMU, HUB client 0x12 = PMU, VA 0x04010000, VIRT WRITE, type 0 = INVALID PDE.
- PMU VAS: PDB 0x7fdf7d000 (vidmem, ver2, 64K big) - PD3 page ALL ZERO, and the pages 0x7fdf78000..7c000 too.
  No PDE anywhere in the top 64MB of VRAM points at them (vram-scan.py). Other VAS (PDB 0x7fdf77000) has a proper chain
  -> RM page-table writes via BAR2 DO land (also verified by hand: BAR3 write -> PRAMIN readback OK; RM's own BAR2 verify passes).
  PDBs 0x7fdf6c000 and 0x7fdf64000 are empty too.
- Trace: TLB invalidates (0x100cb8) of PDB 7fdf7d0 at 128.708, 128.727 (around W 10a480=407fdf7e NEW_INSTBLK) and 128.821
  (right after the CE reset, just before ENGCTL). So RM likely MAPS then UNMAPS (or never maps) what the PMU writes to at 0x4010000.
- Note: PTE aperture 0 = vidmem (PDE: 1 = vidmem). BAR3 has no sysfs resource3 file; use /dev/mem @0x1b82000000.
- Built: nvrtrace v4 (16M bar0 map, PTE aperture fix, "V" lines = walk of watch_va 0x4010000 in pmu_pdb at every PMU-PDB
  TLB invalidate + at the hold; dump path tested OK via a renamed copy). link-trace.sh v3: no longer blocks on the wedged
  nvidia-smi zombie (saves the trace after 65s). Old: nvrtrace.c.v3, link-trace.sh.v2, pramin-walk.py.v1.
- State: WEDGED (nv_queue D, old nvrtrace stuck loaded). Next: user OK -> sync; reboot -ff "0 tryboot"; ./link-trace.sh;
  grep -E "nvrtrace: (V|F|P)" run-*.log  -> was 0x4010000 ever mapped (inval#1/2/3) and what does it point at?
# 2026-10-01 18:42 (Pi clock): tryboot OK (tryboot=1, overlay applied, clean). Running ./link-trace.sh (nvrtrace v3).
# 2026-10-01 ~19:00: user OK ("good to reboot") -> Claude ran sync; reboot -ff "0 tryboot" (wedged). Next: check tryboot=1 + overlay, ./link-trace.sh, grep -E "nvrtrace: (P|F)" run-*.log
# 18:55: nvrtrace v3 BUILT + dump path tested (insmod probe=1 dump_now=1 -> prints F lines, walk ok; tables now garbage post-teardown). v2 = nvrtrace.c.v2.
#   P/F lines now in dmesg (run-*.log). Next: user OK -> sync; reboot -ff "0 tryboot" (WEDGED); then ./link-trace.sh;
#   read: grep -E "nvrtrace: (P|F)" run-*.log  -> decode the NR fault packet (engine id, client, fault type, addr).
# 2026-10-01 18:45: link-trace 1831 (nvrtrace probe=1 = 20ms hold BEFORE the PMU ENGCTL write): GPU DID NOT FALL OFF THE BUS.
- linkwatch-1831: BOOT0 never ffffffff, GC_ID fine all run. Instead RM polled PMU 0x10a0dc = 000ab0fd (ctxsw state 3,
  bit1 done=0) for ~60s (no timeout!) until timeout killed nvidia-smi; then oops: memcpy_toio write to an unmapped
  ioremap in rm_init_adapter (teardown raced the still-running init). WEDGED (nv_queue D). Log: oops-1001-1834.log.
- Timeline (mono clock, watcher): 61.27 PMU booted (CPUCTL 0x10 -> 0x40/0x60, RTOS running, MB0 40002077),
  61.3708 CE reset (ENABLE 1fecdff1 -> 1e0cd131), 61.3836 MMU FAULT_STATUS (0x100e60) = 0x200 = NON-REPLAYABLE FAULT,
  i.e. 13ms after the CE reset and BEFORE RM's ENGCTL write (still in the hold). NR fault buffer (0x100e24..34):
  lo=02000000 (BAR2 VA 0x2000000) GET=0 PUT=1 -> exactly ONE fault packet. FLT_ADDR/INST/INFO snap regs = 0.
- So: theory (A)-ish: some engine faults right after the CE reset; with no delay the PMU ctxsw hits that within
  0.5ms and the GPU drops off PCIe; with 20ms delay the fault is reported and the PMU ctxsw just stalls (state 3).
- Could not read the packet: RM's teardown already wiped BAR2 (PD3 @0x7fffa2000 all zero; BAR1 tables still fine).
  pramin-walk.py = BAR2 VA -> PA walker via PRAMIN (only when RM is dead).
- ftrace ring overflowed (36M entries: the 60s 10a0dc poll) -> P/S lines and the early W lines were lost.
- Next: nvrtrace v3 = dedupe repeated reads + at the end of the hold dump fault regs AND the NR fault packet
  (walk BAR2 via PRAMIN in-kernel, save/restore 0x1700). Then sync; reboot -ff "0 tryboot" (wedged).
# 2026-10-01 18:3x: tryboot OK (tryboot=1, overlay applied, clean). Running ./link-trace.sh (v2, probe=1).
# 2026-10-01 18:3x: user OK ("carry on the reboot") -> Claude ran sync; reboot "0 tryboot" (clean). Next: check tryboot=1 + overlay, then ./link-trace.sh
# 2026-10-01 18:28: Pi came up on NORMAL config (tryboot=0, overlay not applied, up 4min; the 09-29 21:47 tryboot never ran or was power-cycled). Nothing loaded, kernel unchanged (6.18.34), nvidia.ko c572858 / v100_bar / nvrtrace v2 all built for it, tryboot.txt intact. Next: user OK -> sync; reboot "0 tryboot"; then ./link-trace.sh
# 21:47: user will reboot themselves (asked to use: sync; reboot "0 tryboot"). After boot: ./link-trace.sh
# 21:23-21:45 (Pi clock): link-trace run 2123 DONE. Link lock + ASPM off did NOT help. Key corrections + next step:
- RMPcieLinkSpeed/RMDisableGpuASPMFlags worked (G LnkCtl2 3->2, link 5GT/s x1 throughout) -> still Xid 79 = not gen-switch/ASPM.
- CLOCK SKEW: link-watch (CLOCK_MONOTONIC) runs ~192ms AHEAD of dmesg/ftrace (local clock): the trace's
  W 000200=1e0cd131 @62.5833 shows up in the watcher @62.7756. (The 21:04 "Xid while BAR0 fine" was this skew.)
- Real timeline (trace clock): 62.5833 RM clears PMC_ENABLE CE0..CE8 (all 9 copy engines: 1fecdff1->1e0cd131)
  62.58375 W 10a0a4=1 (= PWR_FALCON_ENGCTL per nvgpu hw_pwr_gv100.h), R 10ac0c:0 still OK (2us after)
  ~62.5839 whole BAR0 incl. PCFG mirror all-ones (watcher) -> RM's next read R 10a0dc = ffffffff -> sanity check
  (_nv015645rm reg-read core -> _nv030270rm) confirms for 150ms -> Xid 79 @62.738. Outage ~15s, then recovers w/o reset.
- _nv050638rm = falcon ctxsw handshake: after ENGCTL|=1 polls 0x10a0dc bits14:12 (2 -> W 10a058(CTXACK)=1, 5 -> =2),
  bit1 = done. PMU NEW_INSTBLK 0x10a480 = 0x407fdf7e (vidmem 0x7fdf7e000). Afterwards CURCTX = 407fdf7e (switch finished
  later), 0dc=000aa0fd, DMATRFCMD=00000600, EXTERRSTAT 0, MMU FAULT_STATUS 40000000 (BUSY only, NO fault). pmu-regs-2123.txt
- GPU DevCtl2 CTO = 50us-50ms (so not a GPU-side DMA read timeout). RC afterwards: UESta CmpltTO+, CESta AdvNonFatalErr+
  = RC's CPU reads got no completions for ~15s.
- Checked & dropped: nv_phys_to_dma() is identity here (conftest phys_to_dma includes the wrong header), but on 6.x
  nv_dma_maps_swiotlb()=false -> will_remap -> RM maps via dma_map_* (DMEM args show correct 0x10_/0x12_ bus addrs).
- Two theories left: (A) GPU-internal host/FB hang during the PMU ctx switch (config space would still answer),
  (B) PCIe-level stall (e.g. GPU upstream posted write the Pi can't sink, completions stuck behind it) -> config dead too.
- Built for next run: nvrtrace v2 (probe=1: snapshot + 20ms hold BEFORE the ENGCTL write = tests the CE reset alone,
  then 2us sampling of BOOT0/DMATRFCMD/0dc/CPUCTL/CURCTX until BOOT0 dies; "P"/"S" lines in the trace), link-watch v4
  (+ GPU config space GC_* via sysfs), link-trace.sh v2 (ftrace clock=mono = watcher clock). Old: *.v1/*.v3. Load test OK.
- State: nvidia loaded but failed (not wedged), GPU recovered. Next: user OK -> sync; reboot "0 tryboot"; then ./link-trace.sh
  Read: grep -E " (P|S) " link-trace-*.txt ; GC_ID in linkwatch-* during the outage (1db610de = theory A, ffffffff = B).
# 21:23 (Pi clock): tryboot OK (overlay applied, clean). Running ./link-trace.sh.
# 21:38: user OK ("go on") -> Claude ran sync; reboot "0 tryboot" (clean). Next: ./link-trace.sh
# 2026-09-29 21:35: XID 79 = THE GPU DROPS OFF PCIe ~5ms AFTER RM STARTS THE PMU FALCON (not a bad RM read).
- xid-trace-2114.txt + watch-2114.txt: 100.1349 last RM prints (nv_free_pages via _nv030325rm->_nv050226rm), then
  100.1399 the WHOLE BAR0 (incl. PCFG mirror 0x88000) reads all-ones for 13.4s; RM polls PMU status for 150ms and
  calls the lost-GPU handler -> Xid 79 at 100.289. (At 21:04 the 2ms watcher + PRAMIN polling missed/skewed this.)
- Xid call chain decoded: _nv050973rm (gpuStateLoad?) -> ... -> _nv050655rm (PMU state load) -> _nv050654rm (writes
  PMU falcon 0x10a0a4|=1, 0x10a050 = start) -> _nv050640rm -> _nv050638rm (polls 0x10ac0c / 0x10a0dc) ->
  _nv015645rm -> _nv030270rm (osHandleGpuLost, prints Xid). RM reg helpers: _nv052181rm = regRead032(ra,0,0,addr=w3,ts),
  _nv052186rm = regWrite032(ra,0,0,addr=w3,val=w4,ts), ra = pGpu+0x4160.
- Root port DevSta afterwards: CorrErr+ NonFatalErr+ (latched by the RC itself; AER counters 0; no brcm-pcie log).
  GPU LnkCap says max 5GT/s now, LnkCtl2 target Gen2, ASPM off, ClockPM+ (GPU); RC LnkCap Gen2, ASPM L1 capable.
- Theory: PMU ucode (now fed correctly thanks to NC sysmem; with cached sysmem it halted = Xid 62) does a PCIe
  gen switch / ASPM change that the Pi RC (Gen2, no CLKREQ on oculink?) doesn't survive. Regkeys in the blob:
  RMPcieLinkSpeed (0x800000a8 = no Gen3/4/5 + LOCK_AT_LOAD, per open nvrm_registry.h), RMDisableGpuASPMFlags
  (bit0 L0s, bit1 L1), RMPcieGenSwitchOnPmu, RmForceEnablePcieGenSwitching, RMEnableASPMAtLoad, DisablePexLinkSpeedWAR.
- tracefs kprobe events refuse blob functions ("notrace") -> nvrtrace/nvrtrace.ko (raw kprobes, trace_printk
  "W addr=val" / "R addr:val" for every RM regWrite/regRead). Tested: loads/unloads clean.
- New: link-watch.py (read-only: BAR0 + GPU LnkCtl/Sta/LnkCtl2 via PCFG mirror 0x88000+0x78, PMU CPUCTL/MB0/MB1,
  RC DevSta/LnkSta via sysfs config) and link-trace.sh (clears RC DevSta, loads with RegistryDwords
  "RMBar1ApertureSizeMB=8192;RMPcieLinkSpeed=0x800000a8;RMDisableGpuASPMFlags=3", nvp/nvle stacks + nvrtrace + watcher,
  nvidia-smi). Arg 1 overrides the RegistryDwords.
- Next (state clean, not wedged; GPU broken until reset): user OK -> sync; reboot "0 tryboot"; then ./link-trace.sh
  Read: last "W" lines before BOOT0 goes ffffffff in linkwatch-*, link regs changes, RC DevSta after.
# 21:14: tryboot OK (overlay applied, clean). Running ./xid-trace.sh.
# 21:12: kprobe syntax verified, pi5dbg uses printk. User OK ("go on") -> Claude ran sync; reboot "0 tryboot" (clean). Next: ./xid-trace.sh
# ~21:20: prepared (UNTESTED, Bash checker was down): xid-trace.sh = load-v100.sh (nv_pi5_debug=0) + kprobes with
  stacktrace on nvidia:nv_printf / nvidia:os_log_error + vram-watch.py v2 (no PRAMIN, + fault latch, abs times) + nvidia-smi.
  State now: nvidia rmmod'ed (clean), v100_bar loaded, GPU FB broken until reset.
  Next: chmod +x xid-trace.sh; check `grep pi5dbg nvidia/*.c` uses printk not nv_printf; (user OK) sync; reboot "0 tryboot";
  then ./xid-trace.sh and read the stack under the "Xid" event in xid-trace-*.txt.
# 2026-09-29 ~21:15: "DEAD VRAM" THEORY WRONG - FB is fine during init; it dies only in the teardown AFTER the failure.
- Fresh (before nvidia, after `echo 1 > .../enable` for mem decode): devinit not run (normal: no x86 POST on a Pi). Not informative.
- vram-watch.py (read-only regs every 2ms during nvidia-smi; log watch-2104.txt; t0 = boot 114.084, clocks match dmesg):
    115.02 LMR=0x20a (RM devinit/HBM training OK), PRAMIN reads 0x00000000 (VRAM alive, not bad0...)
    115.443 channel B setup (last reg change)  |  115.600 Xid 79 while BAR0+PRAMIN still read fine (!)
    115.710 RmInitAdapter failed  |  115.857-130.95 FULL BAR0 outage (all-ones 15s, card not reset: LMR/BAR blocks kept)
    then PBUS FB_REQ/ACK timeouts (0xb0) + PRAMIN 0xbad0fb.. = the "dead FB" seen at 21:00 is a teardown casualty.
- BAR1 via /dev/mem @0x1800000000 (after rmmod) returns 0xbad0fbXX = GPU answers -> Pi outbound >32G bus translation OK.
- Latched MMU fault (ENG PHYSICAL, HUB_HOST_CPU, PHYS_READ, REGION_VIOLATION) = self-inflicted by the watcher's PRAMIN
  read at window 0x7fff0 (WPR at FB top). The 21:00 run had no fault bit and failed the same -> ignore. Don't poll PRAMIN.
- No FLR (FLReset-), only bus reset via the RC -> reboot needed to reset the GPU.
- Open question: WHAT access returned all-ones at 115.600? Plan: kprobe+stacktrace on the blob's print path (nv_printf /
  nv_log_error, filter "*Xid*") to get the RM call chain; watcher without PRAMIN + fault regs.
# 21:04: fresh probe (mem decode on, before nvidia): devinit NOT run (PMC_ENABLE=0x40000020, LMR=0, PRAMIN=0xbad0ac..) = normal un-POSTed state, inconclusive. Now: load-v100.sh + read-only vram-watch.py during nvidia-smi.
# 21:03: tryboot OK (overlay applied). Running v100_bar + vram-probe fresh, then load-v100.sh + nvidia-smi + vram-probe after.
# 2026-09-29 21:12: user OK -> Claude ran sync; reboot "0 tryboot" (clean). Next: insmod v100_bar.ko; ./vram-probe.py "fresh, before nvidia"; then load-v100.sh nv_pi5_nc_min_pages=2 NVreg_RegistryDwords=RMBar1ApertureSizeMB=8192; timeout 60 nvidia-smi; ./vram-probe.py "after init".
# 2026-09-29 21:10: ROOT CAUSE NARROWED: the GPU's FB (VRAM path) is dead after the failed init.
- RmInitAdapter (0x25:0x40:1623) = RM_INIT_GPU_LOAD_FAILED / NV_ERR_INVALID_STATE -> gpuStateInit passed, gpuStateLoad failed.
- rmmod nvidia worked cleanly (first time; NOT wedged). v100_bar still loaded.
- vram-probe.py (new; PRAMIN window at BAR0+0x700000, GPU-internal, no BAR1/Pi window involved):
  with driver loaded: all vidmem reads 0xffffffff; after rmmod: 0xbad0fbXX (FB access error), writes don't stick.
  PBUS_INTR_0=0x800000bc (PRI_TIMEOUT + FB_REQ/ACK_TIMEOUT), priv ring SYS error @0x10ecc0 code 0xbadf1301,
  GPC/FBP errors @0x419c84 code 0xbadf5040. Dumps: regs-after-2055.txt.
- Config/priv side fine: PMC_BOOT_0 OK, LOCAL_MEMORY_RANGE=0x20a (=32GB, devinit ran), BAR1/BAR2 inst blocks in vidmem
  @0x7fffa0000, NISO flush sysmem addr = bus 0x10_1027_8000 (valid, inside the IB window).
- So Xid 79 was RM tripping on the dead FB; channel B's setup/scrub is where it died.
- Open question: is VRAM already broken before nvidia.ko (not trained at power-on / after PERST), or does the driver
  break it (e.g. devinit/HBM training failing on this platform, or a GPU DMA error hanging the FB hub)?
- Next boot (clean state -> plain reboot "0 tryboot" is fine):
    insmod /root/v100-pi/v100_bar.ko ; ./vram-probe.py "fresh, before nvidia"
  then ./load-v100.sh nv_pi5_nc_min_pages=2 NVreg_RegistryDwords=RMBar1ApertureSizeMB=8192 ; timeout 60 nvidia-smi ;
  ./vram-probe.py "after init"
# 2026-09-29 21:00: null-patch c572858 WORKS: no oops, NOT wedged (nv_queue S). RM's real error surfaced:
- ~150ms after channel B setup (BAR1 ioremap 0x1800090000 + 109p kmap): "Xid 79, GPU has fallen off the bus",
  then "RmInitAdapter failed! (0x25:0x40:1623)" = NV_ERR_INVALID_DATA / NV_ERR_INVALID_STATE, line 1623. Log: run-0929-2055.log.
- BUT the GPU is alive afterwards: config ID 1db610de, BAR0 via resource0 reads PMC_BOOT_0=0x140000a1, PCFG mirror OK,
  link 5GT/s x1. Pi RC returns all-ones (no SError) on a bad read here. So Xid 79 = a transient/specific all-ones read.
- Pending after fail: PMC_INTR_0=0x50108000, PBUS_INTR_0=0x80000000, PMC_ENABLE=0x1e0cd131.
- Windows: pcie1 IB CPU 0..64G -> bus 0x10_0000_0000 (no overlap with BAR1 bus 0x8_...). DMA mask 47 bits.
# 2026-09-29 20:55: tryboot OK (overlay applied). Running load-v100.sh nv_pi5_nc_min_pages=2 NVreg_RegistryDwords=RMBar1ApertureSizeMB=8192 + timeout 60 nvidia-smi (null-patched blob c572858).
# 2026-09-29 20:52: user OK -> Claude ran sync; reboot -ff "0 tryboot". Next: load-v100.sh nv_pi5_nc_min_pages=2 NVreg_RegistryDwords=RMBar1ApertureSizeMB=8192 ; timeout 60 nvidia-smi (null-patched blob c572858).
# 2026-09-29 20:50: ResmanDebugLevel=0 run -> SAME NULL deref; RM core prints nothing (only interface "VM:" prints). Wedged. Log: run-0929-2045.log.
- Alloc pattern before the oops: 2 identical channel-like setups A and B (109p + 1p + 2x4p contig + BAR1 64K ioremap
  0x1800080000 / 0x1800090000 + 109p kmap), then a 1p contig alloc+free (~117us), then ONLY B is freed -> oops.
  => B's construction fails FAST (no timeout), the unwind crashes in fifoChidMgrIdleChannels.
- Binary-patched _nv026674rm (commit on /usr/src/nvidia-580.95.05-v100): cbz on ->[80] -> returns FALSE (caller just
  skips, no spin). nvidia.ko rebuilt. Goal: survive the unwind so RM prints "RmInitAdapter failed! (0x..:0x..:line)".
- Next boot (wedged -> sync; reboot -ff "0 tryboot"):
    ./load-v100.sh nv_pi5_nc_min_pages=2 NVreg_RegistryDwords=RMBar1ApertureSizeMB=8192 ; timeout 60 nvidia-smi
# 2026-09-29 20:45: tryboot OK (overlay applied). Running load-v100.sh nv_pi5_nc_min_pages=2 NVreg_ResmanDebugLevel=0 NVreg_RmMsg=: RMBar1ApertureSizeMB=8192 + timeout 60 nvidia-smi.
# 2026-09-29 20:43: user OK -> Claude ran sync; reboot -ff "0 tryboot". Next: ResmanDebugLevel=0 run (see below).
# 2026-09-29 20:25: RMBar1ApertureSizeMB=8192 WORKS (BAR1 top map now phys 0x19ffdf0000, inside the window) but the SAME
  NULL deref (pc _nv026674rm+0x34, fault addr 0x30, x5=6) -> the BAR1 map was NOT the cause. Wedged again. Log: oops-null-2021.log.
- RE: _nv026674rm(pGpu, a, pObj) = bool helper, asserts at lines 170/172: pObj->[1160]->[696] = idx (6);
  pGpu->[8984]->[2480] non-NULL, its ->[80] (array of per-idx objects) is NULL -> deref. Then vcall slot +96.
  Caller _nv026697rm references __FUNCTION__ "fifoChidMgrIdleChannels_IMPL" (physical FIFO, not in open RM source).
  Right before: 2x (BAR1 64K ioremap + 109-page sysmem kmap) = probably internal channel setup (CE scrubber?).
  Theory: an init step fails and the idle-channels unwind crashes on a half-built object -> real error is hidden.
- Next boot (wedged -> sync; reboot -ff "0 tryboot"): same run + RM verbose logging:
    ./load-v100.sh nv_pi5_nc_min_pages=2 NVreg_ResmanDebugLevel=0 NVreg_RmMsg=: NVreg_RegistryDwords=RMBar1ApertureSizeMB=8192 ; timeout 60 nvidia-smi
  Look for the first RM error/assert before the oops.
- Fallback idea: binary-patch _nv026674rm to also return FALSE when ->[80] is NULL (fits by folding mov x16/br).
# 2026-09-29 20:21: tryboot OK (overlay applied). Running load-v100.sh nv_pi5_nc_min_pages=2 NVreg_RegistryDwords=RMBar1ApertureSizeMB=8192 + timeout 60 nvidia-smi.
# 2026-09-29 20:19: user OK -> Claude ran sync; reboot -ff "0 tryboot". Next: load-v100.sh nv_pi5_nc_min_pages=2 NVreg_RegistryDwords=RMBar1ApertureSizeMB=8192 ; timeout 60 nvidia-smi.
# 2026-09-29 20:17: nc_min_pages=2 -> NO LDXR, NO Xid 62. New: NULL deref (addr 0x30) in RM init, driver wedged again.
- Oops in _nv026674rm <- _nv026697rm ... rm_init_adapter (nv_open_q). Log: oops-null-2016.log.
  Then nvidia-smi was killed by the timeout -> 2nd oops in rm_cleanup_file_private; nv_queue D -> wedged.
- Suspect: the last ioremap before the oops is phys 0x1fffdf0000 = BAR1 base + 32GB - 2.06MB, OUTSIDE the
  pcie1 window (pref window ends at 0x1b80000000). nv->fb->size is 8GB (v100_bar), so RM takes BAR1's size from
  the hardware (32GB) and puts something at the top of the aperture.
- Blob has regkey RMBar1ApertureSizeMB -> try capping RM's BAR1 aperture to the 8GB exposed.
- Next boot (wedged -> sync; reboot -ff "0 tryboot"):
    ./load-v100.sh nv_pi5_nc_min_pages=2 NVreg_RegistryDwords=RMBar1ApertureSizeMB=8192 ; timeout 60 nvidia-smi
  Check: no pi5dbg ioremap with phys >= 0x1a00000000.
# 2026-09-29 20:16: tryboot OK (overlay applied). Running load-v100.sh nv_pi5_nc_min_pages=2 + timeout 60 nvidia-smi.
# 2026-09-29 20:15 (real clock): user OK -> Claude ran sync; reboot -ff "0 tryboot". Next: ./load-v100.sh nv_pi5_nc_min_pages=2 ; timeout 60 nvidia-smi.
# 2026-09-29 20:20: built+committed 67d88ec: nv_pi5_nc_min_pages (allocs < N pages stay cached, still cleaned at alloc).
- Next boot (wedged -> sync; reboot -ff "0 tryboot"): ./load-v100.sh nv_pi5_nc_min_pages=2 ; timeout 60 nvidia-smi.
  If the LDXR moves to a bigger alloc, raise N (grep pi5dbg for x0's kmap size).
# 2026-09-29 20:15: nv_pi5_force_uncached=0 -> NO LDXR abort (confirms the NC/atomic theory), but new failure:
- RM init proceeds (chipset warning, GPU UUID read) then "Xid 62, 00000154 0000014c ..." = internal falcon (PMU) halt.
  Nothing after it; nvidia-smi zombie, nv_queue D in nvidia_close_deferred -> wedged, needs `sync; reboot -ff "0 tryboot"`.
  Log: xid62-2010.log. Reading: with everything cached, CPU writes to sysmem (ucode/queues) aren't visible to the GPU falcon.
  => need a middle ground: NC for GPU-shared buffers but cached for the ones RM uses atomics on.
# 2026-09-29 20:10: tryboot OK. Running load-v100.sh nv_pi5_force_uncached=0 + timeout 60 nvidia-smi.
# 2026-09-29 ~20:07: user OK -> Claude ran sync; reboot -ff "0 tryboot". Next: ./load-v100.sh nv_pi5_force_uncached=0 ; timeout 60 nvidia-smi.
# 2026-09-29 ~20:05: nv_pi5_debug run -> culprit identified; driver wedged again
- load-v100.sh fix: overlay check failed because od wraps "43000000 | 00000008" across lines (now -w64 + tr).
- nvidia-smi -> same LDXR external abort in _nv030663rm, x0=ffffffc083729010.
  pi5dbg: "kmap ffffffc083729000 +1 pages cache=1(req 0) contig=1" -> RM asked CACHED, nv_pi5_force_uncached made it NC.
  ALL RM kmaps were req 0 (cached) -> forced NC. BCM2712 aborts exclusives/atomics on NC memory. Log: oops-ldxr-2005.log.
- Next boot (sync; reboot -ff "0 tryboot" since wedged): ./load-v100.sh nv_pi5_force_uncached=0 ; timeout 60 nvidia-smi.
  If that works, the coherency cost has to be handled differently (keep cached + dma_sync), not by forcing NC.
- Also: disk / has only 4 GB free, CUDA 12.9 toolkit (needed for sm_70) is ~4-5 GB -> free space first (CUDA 13.0 can go).

# 2026-09-29 20:03: tryboot OK (overlay applied). Running load-v100.sh (nv_pi5_debug=1) + timeout 60 nvidia-smi.
# 2026-09-29 ~20:00: the tryboot reboot HUNG (wedged driver blocks clean shutdown); user power-cycled -> normal config.
- Rule: if nvidia is wedged, use `sync; reboot -ff "0 tryboot"` (skips service shutdown, still passes tryboot). Clean state -> plain reboot "0 tryboot" is fine.
- 20:00: clean state, rebooting with reboot "0 tryboot". Next: load-v100.sh; timeout 60 nvidia-smi; grep pi5dbg for x0.

# 2026-09-29 ~20:00: Claude killed the stuck timeout/nvidia-smi and ran reboot "0 tryboot" (user OK). Next: load-v100.sh; timeout 60 nvidia-smi.

# 2026-09-29 ~19:55: fix 19763e5 WORKS (no flush oops). New: external abort in RM (driver wedged, needs reboot)
- Boot was tryboot (overlay OK). insmod v100_bar + patched nvidia.ko OK. nvidia-smi -> NO hard lock, but
  "synchronous external abort" in _nv030663rm (rm_init_adapter <- nv_open_device), insn c85f7c03 = LDXR x3,[x0],
  x0=0xffffffc083dde010 (vmalloc area). Log: oops-ldxr-1950.log. nv_queue stuck in D state -> rmmod impossible.
- Reading: exclusive/atomic on non-cacheable memory -> BCM2712 answers with external abort. On arm64
  NV_MEMORY_UNCACHED sysmem is already Normal-NC, and nv_pi5_force_uncached=1 turns RM's CACHED allocs NC.
- Added nv_pi5_debug=1 (commit f563b88, rebuilt): logs every multi-page kmap/ioremap with %px + caller +
  requested/actual cache type, so the next oops's x0 identifies the allocation.
- Next boot: reboot "0 tryboot"; /root/v100-pi/load-v100.sh (logs /dev/kmsg synced to run-*.log);
  timeout 60 nvidia-smi; grep pi5dbg for x0's page. Likely fix: keep CPU-atomic allocs cached
  (e.g. try load-v100.sh nv_pi5_force_uncached=0 once to confirm).

# 2026-09-29 ~19:55: rebooting with reboot "0 tryboot" to test the patched driver. Patched nvidia.ko is /usr/src/nvidia-580.95.05-v100/nvidia.ko (not kernel/).

# 2026-09-29 19:50: cause = bare nvidia-smi (no insmod) -> nvidia-modprobe loaded the DKMS 4060Ti open driver -> hard lock.
- Added /etc/modprobe.d/v100-no-autoload.conf (blacklist + install /bin/false for nvidia*). Patched fix 19763e5 still UNTESTED.

# 2026-09-29 19:41: nvidia-smi hard-locked the Pi; systemd watchdog (RuntimeWatchdogUSec=1min) reset it
- Not a manual reboot. panic/panic_on_oops=0, so a plain oops would not reboot: this was a hard lockup (or SError panic) -> watchdog.
- Came back on normal config (tryboot=0): overlay NOT applied now, nothing nvidia loaded. No pstore/ramoops, volatile journal -> no logs.
- Unknown yet: was it with v100_bar + patched nvidia.ko insmod'ed (testing fix 19763e5), or bare nvidia-smi (autoloads 4060Ti open driver)?
- Next: capture the crash (netconsole / dmesg -w over ssh from another machine) before retrying.

# 2026-09-29 night: v100_bar OK, closed driver oopsed in our patch -> fixed, needs reboot
- `insmod /root/v100-pi/v100_bar.ko` (rebuilt): BAR1 8G @ bus 0x8_0000_0000, BAR3 32M; PMC_BOOT_0 = 0x140000a1. No hang.
- Closed driver built in place (NOT via DKMS): `make -j4 SYSSRC=/lib/modules/$K/source SYSOUT=/lib/modules/$K/build IGNORE_CC_MISMATCH=1 modules`
  (SYSSRC must be .../source, else stdarg.h error).
- insmod nvidia.ko OK; nvidia-smi -> Oops in nv_pi5_flush_alloc (dma_sync on nv_phys_to_dma() = raw CPU addr,
  outside dma-ranges -> dcache_clean_inval_poc on 0xffff..ffc0). Log: insmod-nvidia.log.
- Fixed (commit on top of /usr/src/nvidia-580.95.05-v100: map/unmap page instead), rebuilt, not yet tested.
- After reboot (must be `reboot "0 tryboot"` for the overlay): do NOT run nvidia-smi first (would autoload the 4060Ti open driver).
  insmod v100_bar.ko; insmod /usr/src/nvidia-580.95.05-v100/nvidia.ko; then nvidia-smi.

# 2026-09-29 late: tryboot with overlay BOOTED OK
- tryboot flag = 1, pcie1 ranges 2nd entry = 43000000 00000008 00000000 (overlay applied), V100 still BAR0-only.
- So the overlay alone is NOT the boot blocker. Still reverted: v100_bar DKMS, patched closed driver, modprobe.d files.
- Next: rebuild/load v100_bar by hand (no autoload), then the closed driver by hand.

# RESUMED 2026-09-29 (evening)
- Pi boots fine with V100 attached on the reverted config (only BAR0 assigned). Journal is volatile: no logs of the failed boot.
- Nothing autoloads nvidia (no modules-load entry, no persistenced) -> overlay is prime suspect.
- Rebuilt overlays/v100-pcie.dtbo; /boot/firmware/tryboot.txt = config.txt + dtoverlay=v100-pcie.
- Next: `reboot "0 tryboot"`. If it hangs, power-cycle -> normal config. If it boots, check the pcie1 ranges (2nd entry should be 43000000 00000008 ...), then modprobe v100_bar by hand.

# REVERTED on 2026-09-29
With the V100 connected, the Pi would not boot. All V100 system changes were reverted:
config.txt restored from config.txt.bak-pre-v100 (dtoverlay=v100-pcie removed), v100-pcie.dtbo deleted,
/etc/modprobe.d/v100-*.conf deleted, DKMS v100-bar and nvidia/580.95.05-v100 removed,
DKMS nvidia/580.95.05-noncoherent (the original 4060 Ti open driver) reinstalled, initramfs rebuilt.
Kept for reference only: this directory and /usr/src/nvidia-580.95.05-v100.
Suspected cause: the pcie1 window-move overlay (not verified).

# Tesla V100 32GB on Pi 5 (oculink) — bring-up in progress (started 2026-09-24)

The RTX 4060 Ti was replaced by a Tesla V100-PCIE-32GB. Blockers found:
1. BAR1 is a fixed 32GB; Pi 5 pcie1 only has a 14GB prefetchable window
   -> "BAR 1 ... can't assign; no space".
2. Volta has no GSP -> the open kernel modules refuse it; the closed
   module is needed, but the Pi non-coherent fixes (mariobalanica fork) are
   mostly inside the closed RM blob.
3. CUDA 13 dropped sm_70 -> need CUDA 12.x (12.9 supports sm_70 and sm_89).

## What was done (before reboot #1)
- /boot/firmware/overlays/v100-pcie.dtbo (src: v100-pcie-overlay.dts), enabled
  with `dtoverlay=v100-pcie` in config.txt [pi5]. Moves the pcie1 pref window
  (CPU 0x18_0000_0000, 14GB) to bus 0x8_0000_0000 (32GB aligned).
  Backup: /boot/firmware/config.txt.bak-pre-v100.
- v100_bar.ko (src: v100_bar.c, DKMS `v100-bar/1.0`): programs BAR1 at bus
  0x8_0000_0000 exposing only the first 8GB (param bar1_gb) to Linux, BAR3 into
  the 32-bit window after BAR0. `softdep nvidia pre: v100_bar` in
  /etc/modprobe.d/v100-bar.conf.
- Closed 580.95.05 kernel modules patched in /usr/src/nvidia-580.95.05-v100
  (git repo; `git diff HEAD~2 HEAD~1` = patches), DKMS `nvidia/580.95.05-v100`:
  force uncached sysmem + flush linear alias (nv_pi5_force_uncached=1), never
  skip DMA CPU sync, no WC MMIO (nv_pi5_no_iomap_wc=1).
  The old open/4060Ti DKMS package was removed from DKMS; its source is still
  at /usr/src/nvidia-580.95.05-noncoherent (re-`dkms add` it to go back).
- /etc/modprobe.d/v100-first-boot.conf blacklists nvidia autoload for the first
  boot (safety: test manually first). Delete it once working.

## Next after reboot
    getconf PAGE_SIZE      # 4096
    od -An -tx4 --endian=big /proc/device-tree/axi/pcie@1000110000/ranges  # 2nd entry must be 43000000 00000008 ...
    modprobe v100_bar; dmesg | tail -3; lspci -vv -s 0001:01:00.0 | grep Region
    modprobe nvidia && nvidia-smi; dmesg | grep -iE "nvrm|nvidia" | tail -30
Then: replace CUDA 13.0 with CUDA 12.9 (toolkit only), rebuild llama.cpp with
-DCMAKE_CUDA_ARCHITECTURES=70, pick a ~30B model for 32GB.
