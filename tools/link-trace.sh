#!/bin/sh
# Next-boot run (tryboot, clean state): RM PCIe link-speed lock + ASPM off, and full diagnostics:
# RM print stacks, every RM register write/read via nvrtrace.ko (kprobes on regWrite032 _nv052186rm /
# regRead032 _nv052181rm; tracefs kprobe events refuse blob functions), link-watch.py (GPU+RC link regs, PMU falcon).
# v2: nvrtrace probe=1 (snapshot + 20ms hold before the PMU ENGCTL write, then us-sampling until BOOT0 dies),
#     ftrace clock = mono (same clock as link-watch.py), watcher v4 reads GPU config space too.
# v3: nvrtrace v4 (V lines = PMU VA walk at each PMU TLB invalidate), don't block on a wedged nvidia-smi.
# v4: nvrtrace v5 probe=0 ceu=1 (C lines = RM CeUtils self-test _nv042796rm: step rcs, compared values, sysmem PA + DRAM
#     contents), nv_pi5_debug=1 (kmap cache types). The PMU hang is only the unwind after that test fails.
# v5: fix the nvidia-smi wait (dash has no `jobs -r`), nvidia-smi rc printed despite set -e.
# Usage: ./link-trace.sh ["<RegistryDwords>"]   default keys below.
set -e
cd /root/v100-pi
KEYS=${1:-"RMBar1ApertureSizeMB=8192;RMPcieLinkSpeed=0x800000a8;RMDisableGpuASPMFlags=3"}
S=$(date +%H%M)
RC=0001:00:00.0
echo "RC DevSta before: $(setpci -s $RC CAP_EXP+0xa.w)  LnkSta: $(setpci -s $RC CAP_EXP+0x12.w)" | tee link-pre-$S.txt
setpci -s $RC CAP_EXP+0xa.w=000f            # W1C the RC's latched error bits
echo "RC DevSta cleared: $(setpci -s $RC CAP_EXP+0xa.w)" | tee -a link-pre-$S.txt
./load-v100.sh nv_pi5_nc_min_pages=2 nv_pi5_debug=1 "NVreg_RegistryDwords=$KEYS"
TR=/sys/kernel/tracing
echo 0 > $TR/tracing_on
echo > $TR/trace
echo 16384 > $TR/buffer_size_kb
echo mono > $TR/trace_clock
echo 'p:nvp nvidia:nv_printf fmt=+0(%x1):string' >> $TR/kprobe_events
echo 'p:nvle nvidia:os_log_error fmt=+0(%x0):string' >> $TR/kprobe_events
echo stacktrace > $TR/events/kprobes/nvp/trigger
echo stacktrace > $TR/events/kprobes/nvle/trigger
echo 1 > $TR/events/kprobes/enable
insmod /root/v100-pi/nvrtrace/nvrtrace.ko probe=0 ceu=1  # RM regRead/regWrite -> trace (W addr=val / R addr:val)
echo 1 > $TR/tracing_on
setsid ./link-watch.py linkwatch-$S.txt 60 </dev/null >/dev/null 2>&1 &
sleep 0.5
# v3: a wedged nvidia-smi stays a D-state zombie that timeout never reaps -> don't wait on it past 65s
(set +e; timeout 60 nvidia-smi; echo "nvidia-smi rc=$?") &
NS=$!   # v5: dash has no `jobs -r`; poll the subshell pid instead
i=0; while [ $i -lt 65 ] && kill -0 $NS 2>/dev/null; do sleep 1; i=$((i+1)); done
[ $i -ge 65 ] && echo "nvidia-smi still stuck after 65s (wedged) - saving trace anyway"
sleep 2
echo 0 > $TR/tracing_on
cat $TR/trace > link-trace-$S.txt
echo 0 > $TR/events/kprobes/enable
timeout 5 rmmod nvrtrace || true
for e in nvp nvle; do echo '!stacktrace' > $TR/events/kprobes/$e/trigger; done
echo > $TR/trace
echo > $TR/kprobe_events
echo local > $TR/trace_clock
echo "RC DevSta after: $(setpci -s $RC CAP_EXP+0xa.w)  LnkSta: $(setpci -s $RC CAP_EXP+0x12.w)" | tee -a link-pre-$S.txt
sync
echo "trace -> link-trace-$S.txt, watch -> linkwatch-$S.txt"
