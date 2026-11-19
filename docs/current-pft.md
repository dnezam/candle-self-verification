# Current HOL proof-trace integration

This harness checks a pinned current HOL producer through binary PFT conversion,
target selection, and two readers. Eleven independently constructed sequents
must agree with replay in four fresh processes: separate-file and merged HOL
replay, and separate-file and merged Candle replay. Both harnesses use the
Poly/ML runtime pinned in [`pins.json`](../pins.json). The historical baseline
retains its own HOL and Candle revisions.

## Revisions and contract

| Component | Revision |
| --- | --- |
| HOL producer, converter and reader | [`179b872513`](https://github.com/HOL-Theorem-Prover/HOL/commit/179b872513cbdb51b8d922b3177e115a997cfb1b) |
| Candle reader | [`a9aeaa1d`](https://github.com/CakeML/candle/commit/a9aeaa1dffd50f7cfeed811db6ee61f98e2234da) |
| Poly/ML | [`95414c58`](https://github.com/digama0/polyml/commit/95414c58c36f2cce2c1838bc4ec0716ddfe6c540) (`exportSmall-5.9.2`) |
| CakeML bootstrap for current Candle | [Job 3682, x86-64](https://cakeml.org/regression/artefacts/3682/cake-x64.tar.gz), SHA-256 `3b3c0d82f607261336e47f12b1719eedb6c312fba9d0975e9e7f508e2f8e95a1` |

The producer writes TR32 traces with a six-field root carrying export-time
signature metadata. The converter uses that metadata to give retired local
identities private names. Its input contract requires distinct substitution
redexes. The raw audit checks the anonymous dependency, nested proof marks,
definitions and computation before conversion.

The portable binary header contains `PFT\0`, the version string `0.1.0`, and
the ruleset (`hol4` or `candle`). The footer gives bounds for three ID spaces:
types, terms and theorems. `COMPUTE_INIT` installs the computation state for
subsequent `COMPUTE` steps, including steps in later files. For Candle, the
driver inserts a shared compute preamble after the converted `cv` theory.
See the [format specification](https://github.com/HOL-Theorem-Prover/HOL/blob/179b872513cbdb51b8d922b3177e115a997cfb1b/src/postkernel/prooftrace/pft-format.md).

## Candle invocation

The harness follows the historical driver's invocation-file approach. It copies
`replay.ml` into a generated driver, substituting the trace list in its final
`replay_all` call. Traces are linked under temporary numbered names inside
`candle/pft/`, so master's shell command receives safe relative paths even when
the build directory contains spaces. The temporary links and footers are removed
after replay.
The checkout's reader files stay unchanged, including the `extract_footer`
shell script used by master. No reader patch is needed.

## Prerequisites

Use clean checkouts at the revisions above. The harness accepts separate paths
for the built producer, converter sources, and built Candle reader checkout.
It checks their revisions; dirty converter/reader sources require an explicit
`--allow-dirty` development option. The producer needs a matching holbuild
manifest or a clean Git checkout; a declared revision alone is insufficient.

Set `PREREQUISITES` to an absolute build directory and `PRODUCER_HOL` to a
clean HOL checkout at the revision above. Build tracing HOL with the pinned
Poly/ML. The fixture theories depend on `cv`, which the `upto-hol` sequence builds.

```sh
python3 baseline.py poly --build-dir "$PREREQUISITES"
(
  cd "$PRODUCER_HOL"
  export PATH="$PREREQUISITES/polyml/bin:$PATH"
  poly < tools/smart-configure.sml
  bin/build --trknl --seq=tools/sequences/upto-hol
)
CONVERTER_HOL="$PRODUCER_HOL"
```

Build Candle in the clean checkout at `CANDLE_CHECKOUT`. On native x86-64,
run its [build instructions](https://github.com/CakeML/candle/blob/a9aeaa1dffd50f7cfeed811db6ee61f98e2234da/build-instructions.sh).
The historical runtime uses an older CakeML word-shift interface and cannot load
this version of Candle. On ARM64, the following commands build the current
runtime with Zig and QEMU (see [tool installation](historical-baseline.md#running)).
Set `QEMU` to the absolute path of `qemu-x86_64-static`.

```sh
(
  set -e
  cd "$CANDLE_CHECKOUT"
  mkdir -p candle/build
  cd candle/build
  curl -fLO https://cakeml.org/regression/artefacts/3682/cake-x64.tar.gz
  echo '3b3c0d82f607261336e47f12b1719eedb6c312fba9d0975e9e7f508e2f8e95a1  cake-x64.tar.gz' | sha256sum -c -
  tar xzf cake-x64.tar.gz --strip-components=1
  patch cake.S ../cake.S.patch
  patch basis_ffi.c ../basis_ffi.c.patch
  cc_x64() { python-zig cc -target x86_64-linux-musl -static "$@"; }
  cc_x64 -O2 -DEVAL -c cake.S -o cake.o
  cc_x64 -O2 -DEVAL -include sys/time.h -c basis_ffi.c -o basis_ffi.o
  cc_x64 cake.o basis_ffi.o -o cake -lm
  "$QEMU" ./cake --types </dev/null >types.txt 2>&1
  python3 ../insulate.py types.txt insulate.ml
  cat ../chdir_to_root.ml >> candle_boot.ml
)
```

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

To use the HOL CLI independently, build its modules in the converter checkout first:

```sh
cd "$CONVERTER_HOL"
bin/Holmake --poly_not_hol -C src/postkernel/prooftrace PFTCLI.uo
src/postkernel/prooftrace/pft.sh emit --ruleset candle \
  --trace inputTheory.tr.gz --output input.pft.bin
src/postkernel/prooftrace/pft.sh merge --ruleset candle \
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
The exact-sequent checks include the type-definition result.

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

Run the four replay sessions with `current.py` as above. The focused Python
tests check the driver’s provenance and completion checks:

```sh
python3 -m unittest -v test_baseline test_current
```

The merger reuses output IDs after their final use. Input-ID reuse after deletion,
side-file `Exported` proofs and deleted proofs/tracing gaps remain unsupported.
Retired imported identities and noncanonical logical roles are also rejected;
see the pinned converter's `pft-cli.md` for its limits. Strict certificate
manifests and large-project export remain outside this integration's checks.

The final run used clean converter and reader commits with `--allow-dirty`
disabled and a tracing producer built from the same HOL revision. It replayed
29 HOL files and 31 Candle files, then each merged file, and passed all eleven
exact checks in every session. The separate-file sessions also checked the
original anonymous export. All 16 Python tests passed. The build directory
contained spaces and a semicolon to check path handling.

[Reference hashes](current-reference-results.json) record the tested sources,
fixtures and portable outputs without build paths.
