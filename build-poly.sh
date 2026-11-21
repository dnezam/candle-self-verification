#!/usr/bin/env bash
# Builds the pinned Poly/ML into PREFIX and checks that exportSmallToFD writes
# the 64-bit heap layout the trace producer relies on.
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: $0 /absolute/install/prefix" >&2
  exit 2
fi
prefix=$1
case "$prefix" in
  /*) ;;
  *) echo "install prefix must be absolute: $prefix" >&2; exit 2 ;;
esac
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
pin() { python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$root/pins.json" "$1"; }
rev=$(pin polyml)

# Kept on failure for its logs (config.log and the like).
work=$(mktemp -d)
echo "building in $work"
cd "$work"
curl -fL -o polyml.tar.gz "https://codeload.github.com/digama0/polyml/tar.gz/$rev"
echo "$(pin polyml_archive_sha256)  polyml.tar.gz" | sha256sum -c -
tar xzf polyml.tar.gz
(cd "polyml-$rev" && ./configure --prefix="$prefix" && make -j8 && make install)

cat > probe.sml <<'EOF'
val fd = Posix.FileSys.creat ("probe.tr",
  Posix.FileSys.S.flags [Posix.FileSys.S.irusr, Posix.FileSys.S.iwusr]);
val () = PolyML.exportSmallToFD (fd, 17);
val () = Posix.IO.close fd;
EOF
"$prefix/bin/poly" --script probe.sml
# The tagged integer 17 is 2 * 17 + 1 = 0x23, as one little-endian word.
actual=$(od -An -tx1 probe.tr | tr -d ' \n')
if [ "$actual" != 2300000000000000 ]; then
  echo "exportSmallToFD probe wrote $actual; expected 2300000000000000" >&2
  exit 1
fi
rm -rf "$work"
echo "Poly/ML $rev installed in $prefix; export probe passed"
