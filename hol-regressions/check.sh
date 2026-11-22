#!/usr/bin/env bash
# Replays HOL4's proof-trace regression fixtures in Candle and checks their
# exact sequents (check.ml). See README.md in this directory for the steps
# that build Candle, the tracing HOL4 and the fixtures first.
set -euo pipefail

if [ "$#" -ne 4 ]; then
  echo "usage: $0 /path/to/Candle /path/to/HOL /path/to/tracing /fixtures" >&2
  exit 2
fi
candle=$(CDPATH= cd -- "$1" && pwd)
hol=$(CDPATH= cd -- "$2" && pwd)
tracing=$(CDPATH= cd -- "$3" && pwd)
fixtures=$(CDPATH= cd -- "$4" && pwd)
# The path goes into an ML string, a sed replacement and replay's shell command.
case "$fixtures" in
  *[!A-Za-z0-9._/+-]*)
    echo "fixture path has a character replay can't pass on: $fixtures" >&2
    exit 2 ;;
esac
dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
pft="$hol/src/postkernel/prooftrace/pft.sh"
export PFT_HOL="${PFT_HOL:-$tracing/bin/hol}"

"$pft" preamble --output "$fixtures/preamble.pft"
for theory in bool/bool \
  marker/marker num/theories/num metis/normalForms combin/combin \
  simp/src/boolSimpsContext HolSat/sat refute/canonContext \
  metis/normalFormsContext metis/folToolsContext metis/folMappingContext \
  meson/src/mesonLibContext meson/src/Canon_Port_Context \
  IndDef/InductiveDefinitionContext relation/relation \
  num/theories/prim_rec quotient/src/quotient coretypes/pair \
  num/theories/arithmetic coretypes/sum coretypes/one coretypes/option \
  num/theories/While num/theories/numeral num/theories/cv
do
  "$pft" emit --ruleset candle \
    --trace "$tracing/src/${theory%/*}/.hol/objs/${theory##*/}Theory.tr.gz" \
    --output "$fixtures/${theory##*/}.candle.pft"
done
"$pft" compute-preamble --output "$fixtures/compute-preamble.pft"

# Candle starts in candle/build and moves to the Candle root, so the footer
# extractor is found from there; replay prefixes trace names with its `here`.
log="$fixtures/candle.log"
cd "$candle/candle/build"
{ sed -e "s|^let here = \"candle/pft/\";;|let here = \"$fixtures/\";;|" \
      -e 's|^let extract_footer_path = .*|let extract_footer_path = "candle/pft/extract_footer";;|' \
      -e '/^let _ = replay_all \[/d' "$candle/candle/pft/replay.ml"
  cat "$dir/check.ml"
} | ./cake --candle > "$log" 2>&1
# Candle can exit zero after an exception or a compile error, and keeps
# reading the phrases after one, so check the log itself.
exact=$(grep -c 'PFT_EXACT ' "$log" || true)
if [ "$exact" -ne 24 ] || ! grep -q 'ALL_CANDLE_PASS$' "$log" ||
   grep -q -E 'EXCEPTION:|ERROR:|Parsing failed' "$log"; then
  echo "Candle check failed ($exact of 24 exact sequents); see $log" >&2
  exit 1
fi
echo "24 exact sequents checked; log: $log"
