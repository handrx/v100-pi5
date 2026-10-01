#!/bin/sh
# CUDA 12.9's crt/math_functions.h declares sinpi/sinpif/cospi/cospif without noexcept, but
# glibc 2.41 (Debian 13) declares them noexcept, so nvcc fails on anything that includes <cmath>.
# Adds "noexcept (true)" to those 4 declarations; keeps the original as math_functions.h.orig.
set -e
F=${1:-/usr/local/cuda-12.9/include/crt/math_functions.h}
[ -e "$F.orig" ] || cp "$F" "$F.orig"
sed -i -E 's/^(extern __DEVICE_FUNCTIONS_DECL__ __device_builtin__ (double|float) +(sinpi|sinpif|cospi|cospif)\((double|float) x\));$/\1 noexcept (true);/' "$F"
grep -cE '(sinpi|sinpif|cospi|cospif)\((double|float) x\) noexcept \(true\);' "$F"
