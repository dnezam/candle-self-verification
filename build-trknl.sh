#!/usr/bin/env bash
set -euo pipefail

BRANCH=recode32
HOLDIR=HOL-"$BRANCH"
HOLTAR="$HOLDIR".tar.gz

BUILD=$(pwd)/build
POLY=$BUILD/polyml/bin/poly

mkdir -p "$BUILD"
cd "$BUILD"

echo "!! Assumption: patched PolyML has been installed into build/polyml !!"

echo "==> Downloading HOL with tracing support"
curl -L -o "$HOLTAR" https://github.com/HOL-Theorem-Prover/HOL/archive/refs/heads/"$BRANCH".tar.gz
tar xvf "$HOLTAR"
rm "$HOLTAR"

echo "==> Building HOL with the tracing kernel"
(
  cd "$HOLDIR"
  "$POLY" < tools/smart-configure.sml
  bin/build --trknl
)
