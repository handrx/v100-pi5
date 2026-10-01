#!/usr/bin/env python3
"""Apply the Pi 5 / V100 binary patches to NVIDIA's closed RM blob.

The blob (nvidia/nv-kernel.o_binary from the 580.95.05 aarch64 driver) is NVIDIA
proprietary, so it is not in this repo. This script patches your own copy in place,
after checking that it is the exact stock file, and checks the result.

usage: blob-patch.py <driver-src>/nvidia/nv-kernel.o_binary
"""
import hashlib, sys

STOCK_SHA256   = "7284e69d1b4babd7702fe79562aa61c9d66ffd2e6b1a824f4bf02bba67fab1e4"
PATCHED_SHA256 = "49f52931e88d56b4a0acadd8930c3ae106d8048d9911eeaf04f9106f99fd5f8d"

# (file offset, stock bytes, patched bytes, what it does)
PATCHES = [
    (0x79b7c, "22a80139", "3fa80139",
     "_nv019217rm+0xc (clConstruct_IMPL): strb w2,[x1,#106] -> strb wzr,[x1,#106], so "
     "PDB_PROP_CL_IS_CHIPSET_IO_COHERENT defaults to FALSE (the Pi's PCIe is not "
     "cache-coherent; same change as the open-RM fork's ac7630de)"),
    (0x4d47c4,
     "007865f8e00000b4050040f9e10304aafd7bc1a8a43040f9f00304aa",
     "000100b4007865f8c00000b4050040f9e10304aafd7bc1a8b03040f9",
     "_nv026674rm (fifoChidMgrIdleChannels helper): add a NULL check on the per-runlist "
     "array before indexing it, so a failed RmInitAdapter unwinds instead of oopsing"),
]


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    data = bytearray(open(path, "rb").read())
    h = sha256(data)
    if h == PATCHED_SHA256:
        print("already patched")
        return
    if h != STOCK_SHA256:
        sys.exit(f"{path}: sha256 {h} is not the stock 580.95.05 aarch64 blob, refusing")
    for off, old, new, why in PATCHES:
        old, new = bytes.fromhex(old), bytes.fromhex(new)
        if data[off:off + len(old)] != old:
            sys.exit(f"unexpected bytes at {off:#x}, refusing")
        data[off:off + len(new)] = new
        print(f"patched {off:#x}: {why}")
    if sha256(data) != PATCHED_SHA256:
        sys.exit("result sha256 mismatch, file not written")
    open(path, "wb").write(data)
    print("ok:", PATCHED_SHA256)


if __name__ == "__main__":
    main()
