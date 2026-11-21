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

Build Poly/ML, the tracing HOL and Candle as the [top-level
README](../README.md#setup) says, with the HOL checkout to test in place of
the pinned one if you like. Then build the converter driver in that HOL:

```sh
(cd /path/to/HOL && bin/Holmake --poly_not_hol -C src/postkernel/prooftrace PFTCLI.uo)
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

The HOL and Candle revisions in [`pins.json`](../pins.json), on an ARM64 host
with Candle's x86-64 runtime under QEMU.
