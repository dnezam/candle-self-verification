# HOL proof-trace regressions in Candle

HOL4's proof-trace regression fixtures (`src/postkernel/prooftrace/tests` in
HOL) cover bugs found in the trace producer and converter. HOL replays all
but the compute-binder fixture itself; this directory checks that Candle
replays the `candle` ruleset outputs, and that each replayed theorem has
exactly the expected sequent. The compute-binder fixture is emitted only for
Candle, so its four checks here are its only replay.
A replay that merely succeeds can hide a converter bug that changes a theorem,
so `check.ml` compares 24 theorems' hypotheses and conclusions with sequents
built independently in Candle.

## What you need

- A Candle checkout at `master` (from `a9aeaa1`, which reads PFT 0.1.0), built
  with its `./build-instructions.sh`. That builds and runs an x86-64 CakeML
  binary, so on an ARM64 host the script stops at `make`. There, run its
  remaining steps by hand in `candle/build`, with the cross compiler and QEMU
  that [the historical baseline](../docs/historical-baseline.md) names:

  ```sh
  cc='python-zig cc -target x86_64-linux-musl -static'
  $cc -DEVAL -O2 -c cake.S -o cake.o
  $cc -DEVAL -O2 -include sys/time.h -c basis_ffi.c -o basis_ffi.o
  $cc cake.o basis_ffi.o -o cake.x86 -lm
  printf '#!/bin/sh\nexec %s "$(dirname "$0")/cake.x86" "$@"\n' \
    /path/to/qemu-x86_64-static > cake && chmod +x cake
  ./cake --types < /dev/null > types.txt 2>&1
  python3 ../insulate.py types.txt insulate.ml
  cat ../chdir_to_root.ml >> candle_boot.ml
  ```
- A HOL4 checkout to test, built with the trace kernel on a Poly/ML that
  provides `exportSmall`, plus the converter driver:

  ```sh
  poly < tools/smart-configure.sml
  bin/build --trknl --seq=tools/sequences/upto-hol
  bin/Holmake --poly_not_hol -C src/postkernel/prooftrace PFTCLI.uo
  ```

## Running the check

First produce the fixtures with HOL's regression runner, which also checks HOL
replay of all but the compute-binder fixture:

```sh
/path/to/HOL/src/postkernel/prooftrace/tests/run.sh all \
  /path/to/HOL/bin/hol /scratch/prooftrace
```

Then convert the theories the fixtures depend on and replay everything in
Candle:

```sh
hol-regressions/check.sh /path/to/Candle /path/to/HOL /path/to/HOL \
  /scratch/prooftrace
```

The two HOL arguments are the checkout whose converter is under test and the
tracing build whose theory traces are converted; they are usually the same.
The command fails if any replay raises an exception, a fixture is missing, or a
sequent differs; on success it prints `24 exact sequents checked`. Candle's
output is in `candle.log` in the fixture directory.

## Tested revisions

On an ARM64 host, with Candle's x86-64 binary under QEMU:
Candle `a9aeaa1dffd50f7cfeed811db6ee61f98e2234da`, HOL
`179b872513cbdb51b8d922b3177e115a997cfb1b`, Poly/ML
[`digama0/polyml@95414c58`](https://github.com/digama0/polyml/commit/95414c58c36f2cce2c1838bc4ec0716ddfe6c540).
