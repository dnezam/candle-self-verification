#!/usr/bin/env bash
set -euo pipefail

BUILD=$(pwd)/build
POLY=$BUILD/polyml/bin/poly

mkdir -p "$BUILD"
cd "$BUILD"

echo "!! Assumption: patched PolyML has been installed into build/polyml !!"

echo "==> Downloading HOL with tracing support"
curl -L -o HOL-trknl-master.tar.gz https://github.com/HOL-Theorem-Prover/HOL/archive/refs/heads/trknl-master.tar.gz

tar xvf HOL-trknl-master.tar.gz

rm HOL-trknl-master.tar.gz

echo "==> Building HOL with the tracing kernel"
(
  cd HOL-trknl-master
  poly < tools/smart-configure.sml
  bin/build --trknl
)
