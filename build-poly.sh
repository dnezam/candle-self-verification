#!/usr/bin/env bash
set -euo pipefail

BUILD=$(pwd)/build
PREFIX=$BUILD/polyml

mkdir -p "$BUILD" "$PREFIX"
cd "$BUILD"

echo "==> Downloading patched version of PolyML"
curl -L -o polyml-exportSmall.tar.gz https://github.com/digama0/polyml/archive/refs/heads/exportSmall.tar.gz
tar xvf polyml-exportSmall.tar.gz
rm polyml-exportSmall.tar.gz

echo "==> Installing PolyML into $PREFIX"
(
  cd polyml-exportSmall
  ./configure --prefix="$PREFIX"
  make
  make install
)
rm -rf polyml-exportSmall
