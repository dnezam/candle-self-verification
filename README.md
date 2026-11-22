## Candle Self-Verification

Coordination repository for replaying the proof of correctness of Candle's
machine-code implementation in Candle; [`plan.md`](plan.md) has the roadmap.

What runs here today answers a smaller question: can HOL export proofs, and
can both HOL and Candle recover the expected theorems after the proof traces
are converted and merged? `current.py` produces small fixture theories with a
tracing HOL, converts their traces to PFT for each reader, and replays them in
four fresh processes: separate files and one merged file, in HOL and in Candle.
Each process checks the exact hypotheses and conclusion of the same 11
theorems against sequents built independently of replay.
[`hol-regressions/`](hol-regressions/README.md) is an optional extra check
that replays HOL's proof-trace regression fixtures in Candle.

The revisions under test are in [`pins.json`](pins.json): the HOL producer and
converter (separate fields; they may differ when testing a converter port),
Candle, Poly/ML, and the CakeML bootstrap Candle is built from.
HOL's [`pft-cli.md`](https://github.com/HOL-Theorem-Prover/HOL/blob/179b872513cbdb51b8d922b3177e115a997cfb1b/src/postkernel/prooftrace/pft-cli.md)
documents the converter and merger commands, and
[`pft-format.md`](https://github.com/HOL-Theorem-Prover/HOL/blob/179b872513cbdb51b8d922b3177e115a997cfb1b/src/postkernel/prooftrace/pft-format.md)
the PFT format.

The first, historical HOL-to-Candle baseline (`baseline.py`, its fixtures and
reference results) is kept at
[`54561f2`](https://github.com/dnezam/candle-self-verification/tree/54561f2ca4fa7d5bfa3b1eac33302af695f9527e).

## Setup

You need Linux on x86-64 or ARM64, Python 3.11+, curl, patch, GNU make and C
and C++ compilers. Candle's runtime is an x86-64 binary: on ARM64, also install Zig
(`uv tool install ziglang==0.17.0` provides `python-zig`) and QEMU user mode.
The tested QEMU is `usr/bin/qemu-x86_64-static` from Ubuntu's
[`qemu-user-static_8.2.2+ds-0ubuntu1.18_arm64.deb`](https://ports.ubuntu.com/ubuntu-ports/pool/universe/q/qemu/qemu-user-static_8.2.2+ds-0ubuntu1.18_arm64.deb)
(SHA-256 `0565144632acc09b92da93e5ef9a2f44fa092797c5b0949744351b184ad948a8`),
unpacked without root by `dpkg-deb -x`.

1. Build Poly/ML. The producer writes traces with `PolyML.exportSmallToFD`,
   which the pinned fork provides; the script checks the archive's hash and
   probes the export layout.

   ```sh
   ./build-poly.sh "$PWD/build/polyml"
   export PATH="$PWD/build/polyml/bin:$PATH"
   ```

2. Build the tracing HOL in a clean HOL checkout at `producer_hol`. The
   fixtures depend on `cv`, which `upto-hol` builds.

   ```sh
   (
     cd /path/to/HOL
     poly < tools/smart-configure.sml
     bin/build --trknl --seq=tools/sequences/upto-hol
   )
   ```

3. Build Candle's runtime in a clean Candle checkout at `candle`. On ARM64,
   pass the absolute path of `qemu-x86_64-static` in `QEMU`.

   ```sh
   ./build-candle.sh /path/to/Candle                                   # x86-64
   QEMU=/path/to/qemu-x86_64-static ./build-candle.sh /path/to/Candle  # ARM64
   ```

## Running

```sh
python3 current.py --hol /path/to/HOL --converter /path/to/HOL \
  --candle /path/to/Candle --build-dir "$PWD/build/current"
```

It prints `Verified eleven exact sequents in separate and merged HOL/Candle
sessions.` and exits 0 only if every replay finished and every check passed.
A zero exit from a REPL never counts: the driver requires each replayed file's
completion line, each theorem's `CHECKED:` line exactly once and the final
marker, and rejects any `EXCEPTION:` or `ERROR:`.

`current.py` checks its sources first: the converter and Candle checkouts must
be clean at their pinned commits (`--allow-dirty` relaxes cleanliness for
development). The producer needs either a clean Git checkout at
`producer_hol` or a holbuild toolchain manifest next to it, which must also
name the tracing kernel. `--producer-rev`, `--converter-rev` and `--candle-rev`
override the pins.

The build directory keeps a log per stage, `commands.log` with every command
run, and `result.json` with source revisions, runtime, fixture and artifact
hashes, raw trace headers, completed stages and the failure, if any.

## What the fixtures check

`fixtures/produce.sml` builds four theories covering a persisted anonymous
theorem used by another theory, a type definition, two forms of
multi-constant definition, capture-sensitive and simultaneous substitution,
binder shadowing, nested proof marks, `GEN_ABS NONE`, and computing `2 + 3` in
`cv`. They add the `tiny` type and the constants `left`, `right`, `first` and
`second`, and no axioms or cheats. Before conversion, `fixtures/audit-raw.sml`
checks that the raw traces exercise these steps, including that the anonymous
reference points to the exported, proved conjunction. After replay,
`fixtures/check-results.sml` (HOL) and `fixtures/check-results.ml` (Candle)
check each theorem's conclusion and complete hypothesis set; the separate-file
sessions also check the original anonymous export.

Replay trusts the readers' kernels, the CakeML bootstrap, Poly/ML and the
execution environment. The converter's limits are in `pft-cli.md`.

## Tests

```sh
python3 -m unittest -v test_current
```

These check that `current.py` rejects incomplete replay output and wrong or
unverifiable source revisions.
