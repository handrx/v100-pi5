#!/bin/sh
# Next-boot run: kernel stack of every RM print (nv_printf / os_log_error) -> the RM call chain behind
# "Xid 79" shows which access read all-ones. Plus the read-only register watcher.
# Usage (tryboot, clean state): ./xid-trace.sh [extra nvidia.ko params]
set -e
cd /root/v100-pi
./load-v100.sh nv_pi5_nc_min_pages=2 NVreg_RegistryDwords=RMBar1ApertureSizeMB=8192 nv_pi5_debug=0 "$@"
TR=/sys/kernel/tracing
echo 0 > $TR/tracing_on
echo > $TR/trace
echo 8192 > $TR/buffer_size_kb
echo 'p:nvp nvidia:nv_printf fmt=+0(%x1):string' >> $TR/kprobe_events
echo 'p:nvle nvidia:os_log_error fmt=+0(%x0):string' >> $TR/kprobe_events
echo stacktrace > $TR/events/kprobes/nvp/trigger
echo stacktrace > $TR/events/kprobes/nvle/trigger
echo 1 > $TR/events/kprobes/enable
echo 1 > $TR/tracing_on
S=$(date +%H%M)
setsid ./vram-watch.py watch-$S.txt 60 </dev/null >/dev/null 2>&1 &
sleep 0.5
timeout 60 nvidia-smi || echo "nvidia-smi rc=$?"
sleep 2
echo 0 > $TR/tracing_on
cat $TR/trace > xid-trace-$S.txt
echo 0 > $TR/events/kprobes/enable
echo > $TR/kprobe_events
sync
echo "trace -> xid-trace-$S.txt, watch -> watch-$S.txt"
