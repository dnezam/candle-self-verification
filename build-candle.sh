#!/usr/bin/env bash
# Builds Candle's runtime in CANDLE/candle/build from the pinned CakeML
# bootstrap, as Candle's build-instructions.sh does, after checking the
# archive. The runtime is x86-64: on ARM64 it is cross-compiled with Zig and
# `cake` becomes a wrapper that runs it under QEMU (set QEMU to the absolute
# path of qemu-x86_64-static).
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: $0 /path/to/Candle" >&2
  exit 2
fi
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
pin() { python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$root/pins.json" "$1"; }
cd "$1"
mkdir -p candle/build
cd candle/build

curl -fL -o cake-x64.tar.gz \
  "https://cakeml.org/regression/artefacts/$(pin cakeml_bootstrap_job)/cake-x64.tar.gz"
echo "$(pin cakeml_bootstrap_archive_sha256)  cake-x64.tar.gz" | sha256sum -c -
tar xzf cake-x64.tar.gz --strip-components=1
patch cake.S ../cake.S.patch
patch basis_ffi.c ../basis_ffi.c.patch
case "$(uname -m)" in
  x86_64)
    make ;;
  aarch64)
    if [[ "${QEMU:-}" != /* || ! -x "$QEMU" ]]; then
      echo "set QEMU to the absolute path of qemu-x86_64-static" >&2
      exit 2
    fi
    cc=(python-zig cc -target x86_64-linux-musl -static)
    "${cc[@]}" -O2 -DEVAL -c cake.S -o cake.o
    "${cc[@]}" -O2 -DEVAL -include sys/time.h -c basis_ffi.c -o basis_ffi.o
    "${cc[@]}" cake.o basis_ffi.o -o cake.x86 -lm
    printf '#!/bin/sh\nexec %q "$(dirname "$0")/cake.x86" "$@"\n' "$QEMU" > cake
    chmod +x cake ;;
  *)
    echo "this recipe needs x86-64 or ARM64 Linux, not $(uname -m)" >&2
    exit 1 ;;
esac
./cake --types < /dev/null > types.txt 2>&1
python3 ../insulate.py types.txt insulate.ml
cat ../chdir_to_root.ml >> candle_boot.ml
echo "Candle runtime built in $PWD"
