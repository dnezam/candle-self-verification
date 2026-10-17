# Historical proof-trace baseline

This harness reproduces a historical HOL-to-Candle pipeline using fixed source
revisions and checked download hashes. It produces proof traces, converts their
dependency closure, and checks four named theorem values in two fresh Candle
processes. It is a small compatibility baseline, not Candle self-verification
or a claim that current HOL projects can use this converter unchanged.

## Revisions

Complete commits and download SHA-256 values are in [`pins.json`](../pins.json).

| Component | Revision | Role |
| --- | --- | --- |
| Poly/ML | [`5612ede0`](https://github.com/digama0/polyml/commit/5612ede0c13a4efd64293576b037c20b86a26a30) | `exportSmallToFD` runtime, reporting version 5.9.2 |
| HOL | [`57389544`](https://github.com/HOL-Theorem-Prover/HOL/commit/57389544efc00ac56e7b52a8a28fb435b4eb7244) | Both tracing producer and converter |
| Candle | [`51781e5a`](https://github.com/CakeML/candle/commit/51781e5ad891f5792bcf34ac1ea18c1ffd1b6425) | Historical `pft` reader |
| CakeML bootstrap | [`4e312c0f`](https://github.com/CakeML/cakeml/commit/4e312c0f7e18b9c5789c8ac4e0af257bff895cf5) | Source associated with pre-generated compiler assembly |
| Bootstrap's HOL | [`63f2eb9c`](https://github.com/HOL-Theorem-Prover/HOL/commit/63f2eb9c146352dfd0bab8c5604a096d1e554d03) | HOL used for that CakeML bootstrap |

[Regression job 3286](https://cakeml.org/regression.cgi/job/3286) records the
bootstrap revisions. The pinned Candle
[build script](https://github.com/CakeML/candle/blob/51781e5ad891f5792bcf34ac1ea18c1ffd1b6425/build-instructions.sh)
uses that job's `cake-x64-64.tar.gz`. We verify the archive checksum, apply the
two patches from that Candle revision, and compile its assembly and C FFI.
This avoids the large CakeML proof build. The source revisions are provenance;
this harness does not rebuild or verify the bootstrap proof.

## Running

Requires Python 3.11+, Bash, curl, tar, patch, GNU make and a C/C++ toolchain.
Use a clean worktree and a new build directory:

```sh
python3 baseline.py reproduce --build-dir "$PWD/build/baseline"
```

This default command targets Linux x86-64. Builds use at most eight make jobs.
The native historical HOL build is explicit:

```sh
poly --script tools/smart-configure.sml
bin/build --trknl --nograph -j8 --seq=tools/sequences/upto-parallel
```

The harness supplies the pinned `poly` executable. holbuild 0.11.4 and 0.11.5
both pass `--no-helpdocs` to this older HOL, whose option parser rejects it.
Their fallback also selects a full HOL build. This historical baseline therefore
uses HOL's own driver; a later supported toolchain can return to holbuild.

For an ARM64 host, use an explicit x86-64 cross compiler and user-mode emulator.
The checked route uses Zig 0.17.0 targeting static musl and QEMU 8.2.2:

```sh
python3 baseline.py reproduce --build-dir "$PWD/build/baseline" \
  --cc 'python-zig cc -target x86_64-linux-musl -static' \
  --runner /absolute/path/to/qemu-x86_64-static
```

Install Zig without root with `uv tool install ziglang==0.17.0`. An ARM64 QEMU
binary can be extracted with `dpkg-deb -x` from Ubuntu's
[`qemu-user-static_8.2.2+ds-0ubuntu1.18_arm64.deb`](https://ports.ubuntu.com/ubuntu-ports/pool/universe/q/qemu/qemu-user-static_8.2.2+ds-0ubuntu1.18_arm64.deb),
whose SHA-256 is `0565144632acc09b92da93e5ef9a2f44fa092797c5b0949744351b184ad948a8`.
The runner is `usr/bin/qemu-x86_64-static` inside the extraction directory.
The historical ARM64 CakeML archive is not a substitute: it lacks the Candle
boot/configuration files and disables EVAL. No emulator is needed on x86-64.

The C compilation uses `-DEVAL` for Candle's dynamic execution and explicitly
includes `sys/time.h` for the legacy FFI's `struct timeval`. Replay processes
use `CML_HEAP_SIZE=8000` (MiB). These are execution settings, not proof changes.

Individual stages are `bootstrap`, `poly`, `hol`, `convert`, `reader`, and
`replay`; each accepts the same options. The original `build-poly.sh` and
`build-trknl.sh` now call the corresponding pinned stages. Full reruns require a
new build directory; existing extracted source directories are rejected.

## Results and artifacts

The build directory contains:

- `commands.log`: exact commands, input files and explicit environment overrides.
- `prepare.log`, `produce.log`, `convert.log`: build, producer and converter output.
- `traces/raw/`: raw proof dumps for the selected dependency closure.
- `traces/*.pft.bin` and `traces/replay-order.txt`: portable traces and their order.
- `replay-1.log`, `replay-2.log`: fresh reader sessions.
- `reject-*.log`: deliberately invalid replay cases.
- `result.json`: pins, completed stages, last-stage status, artifact hashes and
  the exact successfully checked target sequents and fixture hashes.

The report describes the latest invocation; the command/build logs append.
Failed commands and hash mismatches stop immediately. A zero Candle exit status
is insufficient: the harness requires every file's replay completion, all four
sequent-check markers, and the final success marker, and rejects REPL errors.

The checks require empty hypothesis sets and alpha-equivalent conclusions:

| Saved value | Expected conclusion |
| --- | --- |
| `candle$TRUTH` | `T` |
| `bool$TRUTH` | `T` |
| `marker$stmarker_def` | `!x:'a. marker$stmarker x = x` |
| `smallCompute$add` | `cv_add (Num 2) (Num 3) = Num 5`, with the converter's Candle names and HOL4 numeral encoding |

[`fixtures/check-results.ml`](../fixtures/check-results.ml) constructs the
expected Candle terms directly; it does not obtain them from the replayed
conclusions. The compute check uses `Cexp_add`/`Cexp_num`, with 2 encoded as
`NUMERAL (BIT2 _0)`, 3 as `NUMERAL (BIT1 (BIT1 _0))`, and 5 as
`NUMERAL (BIT1 (BIT2 _0))`. The fixture adds one saved theorem by evaluating
existing constants. It introduces no definition, axiom, cheat or changed
existing theorem statement.

The portable baseline contains 19 files, including the preamble, `bool`,
`marker`, and the arithmetic/`cv` ancestry needed by the compute result.
Converter `EXPECT` commands check intermediate sequents during replay.

## Formats

| Boundary | Pinned contract |
| --- | --- |
| Raw dump | Gzip-compressed Poly/ML heap dump; little-endian 64-bit object headers/payloads followed by the root tagged pointer; no TR32 recoding |
| PFT header | `PFT\0`, unsigned LEB128 integer version **1**, length-prefixed ruleset `candle` |
| Namespaces/footer | Types, terms, theorems, compute initializations; four footer counts and a two-byte footer length |
| Compute | Explicit `COMPUTE_INIT` objects referenced by `COMPUTE` |

See the pinned [raw format](https://github.com/HOL-Theorem-Prover/HOL/blob/57389544efc00ac56e7b52a8a28fb435b4eb7244/src/postkernel/prooftrace/tr-format.md),
[writer](https://github.com/HOL-Theorem-Prover/HOL/blob/57389544efc00ac56e7b52a8a28fb435b4eb7244/src/postkernel/prooftrace/PFTWriter.sml)
and [reader](https://github.com/CakeML/candle/blob/51781e5ad891f5792bcf34ac1ea18c1ffd1b6425/candle/pft/replay.ml).
The runtime probe exports integer 17 and checks all eight raw bytes:
`23 00 00 00 00 00 00 00`. That probe is not a HOL proof.

Later converter changes introduce a semantic-version string and remove compute
initialization objects. Newer HOL also changes raw layouts and defaults to
TR32. Porting those producers/converters/readers together remains separate work.

## Validation and limits

The full command passed from a clean worktree and new build directory using
the ARM64/QEMU route above. Both fresh sessions replayed 19 files and checked
all four sequents; the three rejection cases failed for their intended reasons.
All 19 PFT files were byte-identical across two independent producer builds.
[`reference-results.json`](reference-results.json) records the tested driver
revision, fixture hashes, pins, PFT hashes and checked sequents. These are
observed reference outputs; replay assertions remain the acceptance check.
The native x86-64 route remains untested.

Run the lightweight failure-handling tests with:

```sh
python3 -m unittest -v test_baseline
```

The end-to-end command also tests a corrupt PFT header, a missing target and a
wrong expected conclusion in fresh reader sessions. Those must fail without a
success marker. The repository has no existing CI workflow; these two commands
are the automation entry points.

Replay still trusts the downloaded bootstrap artifact, execution environment,
and the pinned reader/kernel implementation. This is not a strict policy for
allowed axioms or arbitrary untrusted certificates: the reader supports AXIOM
commands and ignores deletion commands. Neither full Candle self-verification
nor large-project export is attempted here.
