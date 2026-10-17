# Historical proof-trace baseline

The HOL producer, portable-trace converter and Candle reader must agree on two
formats. Moving branches no longer do. This preparation milestone selects an
older format combination, pins its inputs, and records where execution stops.
It does **not** establish a known-compatible replay combination yet.

## Revisions

The complete commits and archive SHA-256 values are in [`pins.json`](../pins.json).

| Component | Pin | Role |
| --- | --- | --- |
| Poly/ML | [`5612ede0`](https://github.com/digama0/polyml/commit/5612ede0c13a4efd64293576b037c20b86a26a30) | `exportSmallToFD` producer runtime; reports version 5.9.2 |
| HOL | [`57389544`](https://github.com/HOL-Theorem-Prover/HOL/commit/57389544efc00ac56e7b52a8a28fb435b4eb7244) | Both tracing producer and PFT converter, May 1 historical candidate |
| Candle | [`51781e5a`](https://github.com/CakeML/candle/commit/51781e5ad891f5792bcf34ac1ea18c1ffd1b6425) | April 30 `pft` reader candidate |
| CakeML bootstrap | [`4e312c0f`](https://github.com/CakeML/cakeml/commit/4e312c0f7e18b9c5789c8ac4e0af257bff895cf5) | Source of pre-generated compiler assembly |
| Bootstrap's HOL | [`63f2eb9c`](https://github.com/HOL-Theorem-Prover/HOL/commit/63f2eb9c146352dfd0bab8c5604a096d1e554d03) | HOL revision used by that CakeML bootstrap |
| holbuild | [`2dc92077`](https://github.com/HOL-Theorem-Prover/holbuild/commit/2dc92077b2b0927ab1cab5e1cb542797bb7b2ecc) / 0.11.4 | Build driver used to reproduce the historical HOL build blocker |

[Regression job 3286](https://cakeml.org/regression.cgi/job/3286) records both
bootstrap source revisions. The pinned Candle
[build script](https://github.com/CakeML/candle/blob/51781e5ad891f5792bcf34ac1ea18c1ffd1b6425/build-instructions.sh)
uses that job's `cake-x64-64.tar.gz`. Its checksum is pinned here so a changed
artifact cannot silently substitute for it. Fetching this pre-generated assembly
avoids a large CakeML proof build; it does not reproduce or verify the bootstrap.
The source pins are provenance, not a proof that the downloaded assembly has
been rebuilt from those sources.

## Preparation

Requires Python 3.11+, Bash, curl, tar, Git, GNU make, a C/C++ toolchain, and
holbuild 0.11.4 on PATH. Work in a clean checkout or worktree:

```sh
python3 baseline.py prepare --build-dir "$PWD/build/historical"
```

This downloads and checks the bootstrap archive, builds the pinned Poly/ML with
at most eight make jobs, checks its exporter, then attempts the tracing HOL build
through holbuild. It stops on the first failed command or checksum. Use a fresh
build directory for a new full attempt: an existing Poly/ML source directory is
rejected so a dirty source tree cannot silently become the baseline.

Individual steps remain available:

```sh
python3 baseline.py bootstrap --build-dir "$PWD/build/historical"
./build-poly.sh --build-dir "$PWD/build/historical"
./build-trknl.sh --build-dir "$PWD/build/historical"
```

The build directory contains `commands.log` (commands and explicit overrides),
`prepare.log` (tool output), and `preparation.json` (pins, completed stages,
last-stage status and artifact hashes). The report describes the latest
invocation; the logs append. `replay_verified` remains false and
`replayed_targets` remains empty. Even successful preparation is not replay.
The version check identifies the selected holbuild release; it does not attest
the provenance of an arbitrary locally modified executable with that version.

The Poly/ML probe exports the immediate integer 17. Its complete raw dump must
be the eight bytes `23 00 00 00 00 00 00 00`, checking the exporter API, word
width and endianness. This is a runtime-format check, not a HOL proof.

## Formats

| Boundary | Historical candidate contract |
| --- | --- |
| HOL raw dump | `*Theory.tr.gz`, gzip-compressed Poly/ML heap dump; little-endian 64-bit words, object headers/payloads followed by the root tagged pointer; no TR32 recoding |
| Portable proof trace (PFT) | `PFT\0`, unsigned LEB128 integer version **1**, length-prefixed ruleset `candle` |
| Namespaces/footer | Four counts: types, terms, theorems, compute initializations; footer length stored in the final two bytes |
| Compute | Explicit `COMPUTE_INIT` objects and `COMPUTE` referencing them |

The [raw format](https://github.com/HOL-Theorem-Prover/HOL/blob/57389544efc00ac56e7b52a8a28fb435b4eb7244/src/postkernel/prooftrace/tr-format.md),
[PFT writer](https://github.com/HOL-Theorem-Prover/HOL/blob/57389544efc00ac56e7b52a8a28fb435b4eb7244/src/postkernel/prooftrace/PFTWriter.sml)
and [Candle reader](https://github.com/CakeML/candle/blob/51781e5ad891f5792bcf34ac1ea18c1ffd1b6425/candle/pft/replay.ml)
are the source of this inventory. Matching these fields is necessary but does
not establish constructor, theorem or compute compatibility.

HOL's later converter changes
[`2a497b6e`](https://github.com/HOL-Theorem-Prover/HOL/commit/2a497b6e5)
and [`92963861`](https://github.com/HOL-Theorem-Prover/HOL/commit/92963861a)
introduce a semantic-version string and remove compute initialization objects.
Those changes do not match this Candle reader. This baseline deliberately avoids
them; adapting current HOL dumps and current projects is separate work.

## Blockers

The pinned HOL does not contain `tools/sequences/upto-hol`. holbuild 0.11.4
falls back to a full build but still passes `--no-helpdocs`, which the historical
[build option parser](https://github.com/HOL-Theorem-Prover/HOL/blob/57389544efc00ac56e7b52a8a28fb435b4eb7244/tools/build/buildcline.sml)
does not recognize. The producer build therefore fails before producing traces.
A compatible holbuild route must also select a suitably small build sequence;
simply removing the option would invoke a full HOL build. No direct-build
fallback or source patch is applied by this preparation command.

The historical Candle bootstrap needs Linux x86-64 for its EVAL-based REPL.
Job 3286 also publishes an ARM64 archive, but that archive lacks
`config_enc_str.txt` and `candle_boot.ml`; its Makefile explicitly disables EVAL.
It cannot replace the x86-64 artifact for this reader. Native ARM64 support or
an explicitly checked x86-64 execution environment is still needed on ARM64.

## Validation and remaining work

Run the preparation failure tests with:

```sh
python3 -m unittest -v test_baseline
```

These exercise nonzero subprocess status, missing/corrupt downloads, stopping
at each failed stage, and refusing to treat preparation success as replay.
They do not exercise HOL conversion or Candle replay. The repository has no
existing CI workflow; the command above is available for automation. A replay
check in CI remains pending the working baseline.

To complete the baseline:

1. Provide a holbuild version compatible with the historical producer and pin
   it after a successful build. Preserve the observed failing release separately.
2. Generate `bool` and `marker` traces, the Candle preamble, and a small compute
   trace with all its dependencies. Enable converter `EXPECT` checks. Compute
   also requires the arithmetic/`cv` dependency closure and its compute preamble;
   `bool` and `marker` alone are insufficient.
3. Build the pinned reader using the checked bootstrap artifact. Replace its
   hardcoded merged-file invocation with the explicit ordered fixture list.
   Check target hypotheses and conclusions in two fresh reader sessions, record
   output hashes, and reject a missing or changed result even if the REPL exits 0.

Initial target statements to check are `candle$TRUTH` and `bool$TRUTH` with
empty hypotheses and conclusion `T`, and `marker$stmarker_def` with empty
hypotheses and conclusion `stmarker (x:'a) = x`. A compute fixture should check
`cv_add (Num 2) (Num 3) = Num 5` with empty hypotheses, including the converter's
Candle type/constant translation. These are proposed assertions, **not observed
replay results**. No new logical definition, axiom, cheat or changed theorem
statement is introduced by this preparation milestone.
