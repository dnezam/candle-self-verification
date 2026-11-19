# HOL proof-trace regressions in Candle

HOL4's proof-trace regression fixtures (`src/postkernel/prooftrace/tests` in
HOL) cover bugs found in the trace producer and converter. HOL replays them
itself; this directory checks that Candle replays the `candle` ruleset
outputs too, and that each replayed theorem has exactly the expected sequent.
A replay that merely succeeds can hide a converter bug that changes a theorem,
so `check.ml` compares 24 theorems' hypotheses and conclusions with sequents
built independently in Candle.

## What you need

- A Candle checkout whose `candle/pft/replay.ml` reads PFT 0.1.0
  ([CakeML/candle#25](https://github.com/CakeML/candle/pull/25)), built with
  its `./build-instructions.sh`.
- A HOL4 checkout to test, built with the trace kernel on a Poly/ML that
  provides `exportSmall`, plus the converter driver:

  ```sh
  poly < tools/smart-configure.sml
  bin/build --trknl --seq=tools/sequences/upto-hol
  bin/Holmake --poly_not_hol -C src/postkernel/prooftrace PFTCLI.uo
  ```

## Running the check

First produce the fixtures with HOL's regression runner, which also checks HOL
replay of them:

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

Candle `04ea204ec81f861af8316058335246b0de410429`, HOL
`179b872513cbdb51b8d922b3177e115a997cfb1b`, Poly/ML
[`digama0/polyml@95414c58`](https://github.com/digama0/polyml/commit/95414c58c36f2cce2c1838bc4ec0716ddfe6c540).
