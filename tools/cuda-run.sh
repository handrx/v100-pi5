#!/bin/sh
# Next-boot CUDA bring-up (tryboot, clean state): load nvidia (known-good params from run 2014) + nvidia-uvm,
# create the UVM device nodes, then run cuda-smoke.py stage by stage (stops at the first failure).
# Usage: ./cuda-run.sh [last_stage]     a stuck stage leaves an unkillable process -> sync; reboot -ff "0 tryboot"
set -e
cd /root/v100-pi
./load-v100.sh nv_pi5_nc_min_pages=2 "NVreg_RegistryDwords=RMBar1ApertureSizeMB=8192;RMPcieLinkSpeed=0x800000a8;RMDisableGpuASPMFlags=3"
lsmod | grep -q '^nvidia_uvm' || insmod /usr/src/nvidia-580.95.05-v100/nvidia-uvm.ko
M=$(awk '$2=="nvidia-uvm"{print $1}' /proc/devices)
[ -e /dev/nvidia-uvm ] || mknod -m 666 /dev/nvidia-uvm c $M 0
[ -e /dev/nvidia-uvm-tools ] || mknod -m 666 /dev/nvidia-uvm-tools c $M 1
timeout 60 nvidia-smi -L
sync
timeout 60 ./cuda-smoke.py 1 && echo 0 > /sys/module/nvidia/parameters/nv_pi5_debug
sync
[ "${1:-1}" -gt 1 ] && timeout 120 ./cuda-smoke.py "$1"
dmesg | grep -E "pi5dbg: UVM|Xid|NVRM: .*(error|fail)|nvidia-uvm:|Unable to handle|external abort" | tail -20
