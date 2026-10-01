#!/bin/sh
# Load the V100 stack by hand. Needs the overlay boot: reboot "0 tryboot".
# Usage: load-v100.sh [extra nvidia.ko params, e.g. nv_pi5_force_uncached=0]
set -e
T=$(tr -d '\0' < /proc/device-tree/chosen/bootloader/tryboot 2>/dev/null | od -An -tu1 | tr -d ' ')
od -An -tx4 --endian=big -w64 /proc/device-tree/axi/pcie@1000110000/ranges | tr -s " \n" " " | grep -q "43000000 00000008" \
  || { echo "overlay not applied (tryboot=$T) - use: reboot \"0 tryboot\""; exit 1; }
L=/root/v100-pi/run-$(date +%m%d-%H%M).log
# one kmsg record per read, each write synced -> survives a hard lock
setsid sh -c "dd if=/dev/kmsg of=$L oflag=dsync bs=4096 status=none" </dev/null >/dev/null 2>&1 &
echo "kernel log -> $L"
sync
lsmod | grep -q '^v100_bar' || insmod /root/v100-pi/v100_bar.ko
lsmod | grep -q '^nvidia ' || insmod /usr/src/nvidia-580.95.05-v100/nvidia.ko nv_pi5_debug=1 "$@"
sync
echo "loaded; now: timeout 60 nvidia-smi"
