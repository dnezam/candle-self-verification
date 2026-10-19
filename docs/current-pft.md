# Current HOL proof-trace integration

This harness checks a pinned current HOL producer through binary PFT conversion,
target selection, and two readers. Eleven independently constructed sequents
must agree with replay in four fresh processes: separate-file and merged HOL
replay, and separate-file and merged Candle replay. The historical harness and
`pins.json` remain unchanged as a regression reference.

## Revisions and contract

| Component | Revision |
| --- | --- |
| HOL producer | `beb36f502e21deb268984503442acf7f331a3cbb` |
| HOL converter and reader | `f87d9f59bffede4115663219a9120441e43c0a23` |
| Candle reader | `5cfb92ad87be5eecc9f07502ed80b27cdb4dc317` |
| Poly/ML and CakeML bootstrap | Unchanged checksum-verified pins in [`pins.json`](../pins.json) |

The converter is a focused port of the HOL `replay` branch
`427496c4b6d9796b0d02167715ac7412f5f83a44`, retaining the version-1 writer and
explicit compute contexts from `57389544efc00ac56e7b52a8a28fb435b4eb7244`.
The coordinated Candle reader is based on its `pft` branch `51781e5a`.

The supported interchange is `PFT\0`, unsigned LEB128 integer version **1**,
then ruleset `hol4` or `candle`. Four namespaces (`ty`, `tm`, `th`, `ci`) have
independent IDs and four footer bounds. `COMPUTE_INIT` creates a context object;
`COMPUTE` names that object. A standalone Candle compute preamble exports the
helper equations, and each consuming theory creates its own context.

The experimental `0.1.0` string header and three-namespace ambient-compute format
are rejected. JSON Lines is writer-only diagnostic output. HOL replay requires
`hol4`; Candle replay requires `candle`; merge rejects mixed rulesets before
opening its output.

The raw producer emits TR32. Its current immutable `{name, epoch}` kernel
identifiers differ from the historical baseline's reference layout. The parser
also decodes current `Mark` constructors and the tagged `NONE` in `GEN_ABS`.
Historical raw identifiers are explicitly rejected. Binary PFT v1 remains
compatible with the historical reference outputs.

## Candle reader patch

The coordinated reader change is supplied as
[`patches/candle-pft-v1.patch`](../patches/candle-pft-v1.patch) pending upstream
publication. Apply it on the pinned `pft` base:

```sh
git -C "$CANDLE_CHECKOUT" switch -c pft-current 51781e5ad891f5792bcf34ac1ea18c1ffd1b6425
git -C "$CANDLE_CHECKOUT" am /path/to/candle-self-verification/patches/candle-pft-v1.patch
```

`git am` preserves the source change but gives the local commit a new committer
date. Pass `--candle-rev "$(git -C "$CANDLE_CHECKOUT" rev-parse HEAD)"` to the
harness when using that commit. The reference validation used `5cfb92a` above.

## Prerequisites

Use clean checkouts at the revisions above. The harness accepts separate paths
for the built producer, converter sources, and built Candle reader checkout.
It checks their revisions; dirty converter/reader sources require an explicit
`--allow-dirty` development option. The producer needs a matching holbuild
manifest or a clean Git checkout; a declared revision alone is insufficient.

Build the current producer with holbuild 0.11.5 or later and the pinned tracing
Poly/ML. The historical helper can prepare the checksum-verified prerequisites:

```sh
python3 baseline.py bootstrap --build-dir "$PWD/build/prerequisites"
python3 baseline.py poly --build-dir "$PWD/build/prerequisites"
HOLBUILD_POLY="$PWD/build/prerequisites/polyml/bin/poly" \
HOLBUILD_POLYC="$PWD/build/prerequisites/polyml/bin/polyc" \
  holbuild --source-dir fixtures/current buildhol --trknl
```

The last command prints the producer HOL directory. Its standard `upto-hol`
build includes the `cv` dependencies needed by the fixtures.

The reader source is loaded at runtime, so the same pinned Candle bootstrap
can be reused with the coordinated reader. Build it using the checked helper:

```sh
python3 baseline.py reader --build-dir "$PWD/build/prerequisites"
cp -a build/prerequisites/candle-51781e5ad891f5792bcf34ac1ea18c1ffd1b6425/candle/build \
  "$CANDLE_CHECKOUT/candle/build"
```

The destination must not already exist. On ARM64, add the cross-compiler and
QEMU arguments from [the historical baseline](historical-baseline.md#running)
to the `reader` command. That helper verifies the bootstrap archive before
building; copying the runtime does not copy or replace the reader source.

## Running

With those prerequisites, one command produces, converts, merges and checks:

```sh
python3 current.py \
  --hol "$PRODUCER_HOL" \
  --converter "$CONVERTER_HOL" \
  --candle "$CANDLE_CHECKOUT" \
  --build-dir "$PWD/build/current"
```

For the tested ARM64 host route, add `--runner /path/to/qemu-x86_64-static`.
Each Candle process uses `CML_HEAP_SIZE=8000`. Native x86-64 execution has not
been tested here. Override revisions explicitly with `--producer-rev`,
`--converter-rev`, and `--candle-rev` when checking another port.

The HOL CLI also works independently of these fixed regression fixtures:

```sh
/path/to/HOL/src/postkernel/prooftrace/pft emit --ruleset candle \
  --trace inputTheory.tr.gz --output input.pft.bin
/path/to/HOL/src/postkernel/prooftrace/pft merge --ruleset candle \
  --order dependency-order.txt --target 'input$THEOREM' --output selected.pft.bin
```

See the HOL port's `src/postkernel/prooftrace/pft-cli.md` for building the CLI,
preambles, ordered input lists and multiple targets. The theory name comes from
the raw metadata rather than the input filename.

## Checks and assumptions

The fixtures cover a persisted anonymous theorem used by another theory,
a type definition, two forms of multi-constant definition, capture-sensitive
and simultaneous substitution, binder shadowing, nested proof marks,
`GEN_ABS NONE`, and verified computation of `2 + 3` in `cv`. Both readers check
the exact conclusions and the complete hypothesis sets, including nonempty
sets; their expectations are constructed independently of replayed conclusions.
Candle reader tests also check both results of its type-definition command.

The fixtures introduce the `tiny` type and the four constants `left`, `right`,
`first`, `second`. They introduce no axioms or cheats and change no existing
theorem statement. The anonymous fixture uses the same disk-reference operation
as persistent theory data; a raw audit checks its reference points to the
exported, proved anonymous conjunction.

Merged command inventories record eleven SAVEs and no unresolved LOADs. The
HOL trace contains named axioms `BOOL_CASES_AX`, `SELECT_AX`, `ETA_AX`, and
`INFINITY_AX`; Candle contains `SELECT_AX`, `ETA_AX`, and `INFINITY_AX`.
No unnamed axioms occurred. This is an observed inventory, not a general
allowed-axiom policy or a strict certificate manifest. Replay trusts the kernel,
reader, bootstrap, Poly/ML and execution environment.

`result.json` records source/runtime/fixture hashes, raw TR32 headers, portable
artifact hashes, inventories, completion markers and failures. `commands.log`
records commands; each stage has its own log. A zero REPL exit status alone
never passes the driver.

## Validation

Run the integration checks above and the focused suites:

```sh
python3 -m unittest -v test_baseline test_current
HOLSELFTESTLEVEL=1 "$CONVERTER_HOL/bin/Holmake" \
  -C "$CONVERTER_HOL/src/postkernel/prooftrace"
python3 "$CANDLE_CHECKOUT/candle/pft/test_replay.py" --runner /path/to/qemu-x86_64-static
```

The HOL/Candle suites cover unsupported versions/rulesets before kernel effects,
footer mismatch, named/anonymous dependencies, two-result type definitions and
explicit context preservation. The new Candle reader also passed the historical
19-file reference with its four exact target checks.

The producer toolchain builds with `holbuild buildhol --trknl`. Clean full
standard and experimental kernel builds with selftests passed. The native
tracing run, `bin/build --no-cache --trknl -j4 -t
--seq=tools/sequences/upto-parallel`, stops in three unmodified `src/parse`
precedence-cache tests (`rebuilt`). The same three failures reproduce on clean
producer revision `beb36f502` with the same pinned Poly/ML. The fifteen PFT tests
pass under the standard, experimental, tracing and Moscow ML builds. Full matrix
results are tracked in [HOL #2091](https://github.com/HOL-Theorem-Prover/HOL/pull/2091).
Candle's CRIU regression suite was not run.

Side-file `Exported` proofs, deleted proofs/tracing gaps, and merger input-ID
reuse are explicitly unsupported. Live-ID compaction, Candle deletion-based
memory release, strict certificate manifests and large-project export remain
outside this integration.

The final run used clean converter and reader commits with `--allow-dirty`
disabled. It replayed 29 HOL files and 31 Candle files, then each merged file,
and passed all eleven exact checks in every session. The separate-file sessions
also checked the original anonymous export. All 62 PFT artifacts were
byte-identical to the previous converter pin, and the 16 Python tests passed.
Earlier validation checked CLI output against the integration driver's bytes
and passed 18 focused Candle reader cases; the reader is unchanged.
[Reference hashes](current-reference-results.json) record the tested sources,
fixtures and portable outputs without build paths.
