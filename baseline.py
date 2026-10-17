#!/usr/bin/env python3
"""Reproduce a pinned historical HOL-to-Candle proof-trace baseline."""

import argparse
from contextlib import ExitStack
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys


@dataclass(frozen=True)
class Pins:
    polyml: str
    polyml_archive_sha256: str
    hol: str
    hol_archive_sha256: str
    candle: str
    candle_archive_sha256: str
    cakeml_bootstrap: str
    hol_bootstrap: str
    bootstrap_job: int
    bootstrap_archive_sha256: str


TARGETS = {
    "candle$TRUTH": "T",
    "bool$TRUTH": "T",
    "marker$stmarker_def": "!x:'a. marker$stmarker x = x",
    "smallCompute$add": (
        "Cexp_add (Cexp_num (NUMERAL (BIT2 _0))) "
        "(Cexp_num (NUMERAL (BIT1 (BIT1 _0)))) = "
        "Cexp_num (NUMERAL (BIT1 (BIT2 _0)))"
    ),
}


def check_replay_output(text: str, trace_count: int) -> None:
    """Reject a REPL run that did not finish every replay and sequent assertion."""
    lines = text.splitlines()
    required = [f"CHECKED: {name}" for name in TARGETS] + ["ALL_CHECKS_PASSED"]
    if any(lines.count(line) != 1 for line in required):
        raise ValueError("Candle did not report all expected target checks exactly once")
    if lines.count("Success!") != trace_count:
        raise ValueError(f"Candle did not replay all {trace_count} traces")
    if "EXCEPTION:" in text or "ERROR:" in text:
        raise ValueError("Candle reported a REPL error despite its process exit status")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class Preparation:
    """Keep commands, failures and artifact hashes in one build directory."""

    def __init__(self, pins: Pins, directory: Path,
                 cc: list[str] | None = None, runner: list[str] | None = None) -> None:
        self.pins = pins
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.commands = self.directory / "commands.log"
        self.log = self.directory / "prepare.log"
        self.cc = cc if cc is not None else ["cc"]
        self.runner = runner if runner is not None else []
        self.replay_verified = False
        self.driver_sha256 = sha256(Path(__file__).resolve())

    def run(
        self, command: list[str], *, cwd: Path | None = None,
        env: dict[str, str] | None = None,
        stdin: Path | None = None, output: Path | None = None,
    ) -> None:
        location = cwd or self.directory
        with self.commands.open("a") as log:
            log.write(f"cd {shlex.quote(str(location))}\n")
            if env:
                log.write(" ".join(f"{k}={shlex.quote(v)}" for k, v in env.items()))
                log.write(" ")
            log.write(shlex.join(command))
            if stdin:
                log.write(f" < {shlex.quote(str(stdin))}")
            if output:
                log.write(f" > {shlex.quote(str(output))} 2>&1")
            log.write("\n")
        with ExitStack() as stack:
            log = stack.enter_context((output or self.log).open("ab" if not output else "wb"))
            input_stream = stack.enter_context(stdin.open("rb")) if stdin else subprocess.DEVNULL
            subprocess.run(
                command, cwd=location, env=os.environ | (env or {}),
                stdin=input_stream, stdout=log, stderr=subprocess.STDOUT, check=True,
            )

    def download(self, url: str, filename: str, expected: str) -> Path:
        archive = self.directory / filename
        self.run(["curl", "--fail", "--location", "--output", str(archive), url])
        actual = sha256(archive)
        if actual != expected:
            raise ValueError(f"{filename}: SHA-256 {actual}; expected {expected}")
        return archive

    def bootstrap(self) -> None:
        """Fetch the exact x86-64 artifact used by the pinned Candle setup."""
        archive = self.download(
            f"https://cakeml.org/regression/artefacts/{self.pins.bootstrap_job}/"
            "cake-x64-64.tar.gz", "cake-x64-64.tar.gz",
            self.pins.bootstrap_archive_sha256,
        )
        self.run(["tar", "tzf", str(archive)])

    def poly(self) -> None:
        """Build the export-capable runtime and check its 64-bit dump layout."""
        source = self.directory / f"polyml-{self.pins.polyml}"
        if source.exists():
            raise FileExistsError(f"use a clean build directory: {source} exists")
        archive = self.download(
            f"https://codeload.github.com/digama0/polyml/tar.gz/{self.pins.polyml}",
            "polyml.tar.gz", self.pins.polyml_archive_sha256,
        )
        self.run(["tar", "xzf", str(archive)])
        prefix = self.directory / "polyml"
        self.run(["./configure", f"--prefix={prefix}"], cwd=source)
        self.run(["make", "-j8"], cwd=source)
        self.run(["make", "install"], cwd=source)
        self.run([str(prefix / "bin/poly"), "-v"])
        probe = self.directory / "export-probe.sml"
        probe.write_text(
            'val fd = Posix.FileSys.creat ("export-probe.tr",\n'
            '  Posix.FileSys.S.flags [Posix.FileSys.S.irusr, Posix.FileSys.S.iwusr]);\n'
            'val () = PolyML.exportSmallToFD (fd, 17);\n'
            'val () = Posix.IO.close fd;\n'
        )
        self.run([str(prefix / "bin/poly"), "--script", str(probe)])
        actual = (self.directory / "export-probe.tr").read_bytes()
        expected = (2 * 17 + 1).to_bytes(8, "little")
        if actual != expected:
            raise ValueError(f"64-bit export probe: {actual.hex()}; expected {expected.hex()}")

    def hol(self) -> None:
        """Build the historical tracing kernel using its native build driver."""
        poly = self.directory / "polyml/bin/poly"
        if not poly.is_file():
            raise FileNotFoundError(f"build Poly/ML first: {poly}")
        source = self.directory / f"HOL-{self.pins.hol}"
        if source.exists():
            raise FileExistsError(f"use a clean build directory: {source} exists")
        archive = self.download(
            f"https://codeload.github.com/HOL-Theorem-Prover/HOL/tar.gz/{self.pins.hol}",
            "HOL.tar.gz", self.pins.hol_archive_sha256,
        )
        self.run(["tar", "xzf", str(archive)])
        self.run([str(poly), "--script", "tools/smart-configure.sml"], cwd=source)
        self.run(
            ["bin/build", "--trknl", "--nograph", "-j8",
             "--seq=tools/sequences/upto-parallel"], cwd=source,
        )

    def convert(self) -> None:
        """Produce a compute theorem and convert its complete trace ancestry."""
        source = self.directory / f"HOL-{self.pins.hol}"
        fixtures = Path(__file__).resolve().parent / "fixtures"
        output = self.directory / "traces"
        output.mkdir(exist_ok=True)
        (output / ".hol/objs").mkdir(parents=True, exist_ok=True)
        hol = [str(source / "bin/hol"), "run", "--bare",
               f"--holstate={source / 'bin/hol.state0'}"]
        produce_log = self.directory / "produce.log"
        self.run(hol + [str(fixtures / "produce.sml")], cwd=output, output=produce_log)
        if produce_log.read_text().splitlines().count("PINNED_COMPUTE_PRODUCED") != 1:
            raise ValueError("producer did not finish the compute theorem")
        raw = sorted(source.glob("src/**/.hol/objs/*Theory.tr.gz"))
        raw.append(output / ".hol/objs/smallComputeTheory.tr.gz")
        entries = ",\n".join(
            f"({json.dumps(p.name[:-12])}, {json.dumps(str(p))})" for p in raw
        )
        (output / "raw-manifest.sml").write_text(f"val traces = [{entries}];\n")
        convert_log = self.directory / "convert.log"
        self.run(hol + [str(fixtures / "convert.sml")], cwd=output, output=convert_log)
        if convert_log.read_text().splitlines().count("PINNED_CONVERSION_COMPLETE") != 1:
            raise ValueError("converter did not finish the trace closure")
        names = (output / "replay-order.txt").read_text().splitlines()
        for name in names:
            if (output / name).read_bytes()[:12] != b"PFT\x00\x01\x06candle":
                raise ValueError(f"unexpected PFT header: {name}")
        raw_output = output / "raw"
        raw_output.mkdir(exist_ok=True)
        for name in names[1:]:
            theory = name.removesuffix(".candle.pft.bin")
            path = next(p for p in raw if p.name == f"{theory}Theory.tr.gz")
            shutil.copyfile(path, raw_output / path.name)

    def reader(self) -> None:
        """Build the pinned x86-64 Candle runtime from checked bootstrap assembly."""
        if platform.machine() not in ("x86_64", "AMD64") and not self.runner:
            raise ValueError("the bootstrap is x86-64; supply --runner and a cross --cc")
        source = self.directory / f"candle-{self.pins.candle}"
        if source.exists():
            raise FileExistsError(f"use a clean build directory: {source} exists")
        archive = self.download(
            f"https://codeload.github.com/CakeML/candle/tar.gz/{self.pins.candle}",
            "candle.tar.gz", self.pins.candle_archive_sha256,
        )
        bootstrap = self.directory / "cake-x64-64.tar.gz"
        if sha256(bootstrap) != self.pins.bootstrap_archive_sha256:
            raise ValueError("bootstrap archive changed since download")
        self.run(["tar", "xzf", str(archive)])
        build = source / "candle/build"
        build.mkdir()
        self.run(["tar", "xzf", str(bootstrap), "--strip-components=1"], cwd=build)
        self.run(["patch", "cake.S", "../cake.S.patch"], cwd=build)
        self.run(["patch", "basis_ffi.c", "../basis_ffi.c.patch"], cwd=build)
        self.run(self.cc + ["-O2", "-DEVAL", "-c", "cake.S", "-o", "cake.o"], cwd=build)
        self.run(self.cc + ["-O2", "-DEVAL", "-include", "sys/time.h", "-c",
                           "basis_ffi.c", "-o", "basis_ffi.o"], cwd=build)
        self.run(self.cc + ["cake.o", "basis_ffi.o", "-o", "cake", "-lm"], cwd=build)
        self.run(self.runner + ["./cake", "--types"], cwd=build, output=build / "types.txt")
        self.run([sys.executable, "../insulate.py", "types.txt", "insulate.ml"], cwd=build)
        with (build / "candle_boot.ml").open("a") as boot:
            boot.write((source / "candle/chdir_to_root.ml").read_text())

    def replay(self) -> None:
        """Check four sequents twice in fresh Candle processes and test rejection."""
        source = self.directory / f"candle-{self.pins.candle}"
        pft = source / "candle/pft"
        build = source / "candle/build"
        traces = self.directory / "traces"
        names = (traces / "replay-order.txt").read_text().splitlines()
        for name in names:
            shutil.copyfile(traces / name, pft / name)
        reader = (pft / "replay.ml").read_text()
        invocation = 'let _ = replay_all ["merged.candle.pft.bin"];;'
        if reader.count(invocation) != 1:
            raise ValueError("pinned reader entry point changed")
        library = reader.replace(invocation, "")
        checks = (Path(__file__).resolve().parent / "fixtures/check-results.ml").read_text()
        paths = "; ".join(json.dumps(name) for name in names)
        positive = library + checks + f"\nlet _ = replay_all [{paths}]; check_results ();;\n"
        driver = pft / "replay-baseline.ml"
        request = self.directory / "replay-input.ml"
        request.write_text('#use "candle/pft/replay-baseline.ml";;\n')
        driver.write_text(positive)
        for index in (1, 2):
            log = self.directory / f"replay-{index}.log"
            self.run(self.runner + ["./cake", "--candle"], cwd=build,
                     env={"CML_HEAP_SIZE": "8000"}, stdin=request, output=log)
            check_replay_output(log.read_text(), len(names))

        corrupt = bytearray((traces / names[0]).read_bytes())
        corrupt[0] = ord("X")
        (pft / "corrupt.pft.bin").write_bytes(corrupt)
        # All three errors occur before the compute target, so its ancestry is
        # unnecessary for rejection checks.
        short_paths = "; ".join(json.dumps(name) for name in names[:3])
        negative_base = library + checks + f"\nlet _ = replay_all [{short_paths}]; check_results ();;\n"
        negatives = {
            "header": negative_base.replace(json.dumps(names[0]), '"corrupt.pft.bin"'),
            "missing-target": negative_base.replace('check_saved "bool$TRUTH"',
                                                'check_saved "missing$target"'),
            "wrong-conclusion": negative_base.replace('("T", bool_ty)', '("F", bool_ty)'),
        }
        failures = {
            "header": 'EXCEPTION: Failure "expect_char: unexpected P"',
            "missing-target": 'EXCEPTION: Failure "find"',
            "wrong-conclusion": 'EXCEPTION: Failure "CHECK_FAILED: conclusion: candle$TRUTH"',
        }
        for name, program in negatives.items():
            if program == negative_base:
                raise ValueError(f"negative fixture did not change the input: {name}")
            driver.write_text(program)
            log = self.directory / f"reject-{name}.log"
            try:
                self.run(self.runner + ["./cake", "--candle"], cwd=build,
                         env={"CML_HEAP_SIZE": "8000"}, stdin=request, output=log)
            except subprocess.CalledProcessError:
                pass
            text = log.read_text()
            if failures[name] not in text.splitlines() or "ALL_CHECKS_PASSED" in text.splitlines():
                raise ValueError(f"negative replay did not fail as expected: {name}")
            try:
                check_replay_output(text, len(names))
            except ValueError:
                continue
            raise ValueError(f"negative replay was accepted: {name}")
        driver.write_text(positive)
        self.replay_verified = True

    def prepare(self, stages: list[str]) -> None:
        report = self.directory / "result.json"
        completed: list[str] = []
        for stage in stages:
            print(f"Preparing {stage}; log: {self.log}", flush=True)
            status = "failed"
            try:
                getattr(self, stage)()
                completed.append(stage)
                status = "completed"
            finally:
                artifacts = [
                    self.directory / name for name in
                    ("polyml.tar.gz", "HOL.tar.gz", "candle.tar.gz",
                     "cake-x64-64.tar.gz", "export-probe.tr")
                    if (self.directory / name).is_file()
                ]
                artifacts += sorted((self.directory / "traces").glob("*.pft.bin"))
                artifacts += sorted((self.directory / "traces/raw").glob("*.tr.gz"))
                artifacts += [p for p in (self.directory / "produce.log",
                                         self.directory / "convert.log") if p.is_file()]
                artifacts += sorted(self.directory.glob("replay-*.log"))
                artifacts += sorted(self.directory.glob("reject-*.log"))
                artifacts += [p for p in (
                    self.directory / "polyml/bin/poly",
                    self.directory / f"candle-{self.pins.candle}/candle/build/cake",
                ) if p.is_file()]
                report.write_text(json.dumps({
                    "pins": asdict(self.pins), "completed": completed,
                    "driver_sha256": self.driver_sha256,
                    "fixture_sha256": {
                        p.name: sha256(p) for p in sorted(
                            (Path(__file__).resolve().parent / "fixtures").iterdir()
                        ) if p.is_file()
                    },
                    "cc": self.cc, "runner": self.runner,
                    "last_stage": stage, "last_stage_status": status,
                    "failure": str(sys.exception()) if sys.exception() else None,
                    "sha256": {str(p.relative_to(self.directory)): sha256(p)
                               for p in artifacts},
                    "replayed_targets": [
                        {"name": name, "hypotheses": [], "conclusion": statement}
                        for name, statement in TARGETS.items()
                    ] if self.replay_verified else [],
                    "replay_verified": self.replay_verified,
                }, indent=2) + "\n")
        print("Verified four target sequents in two fresh Candle sessions."
              if self.replay_verified else "Stages completed; no proof replay has been verified.")


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["reproduce", "bootstrap", "poly", "hol", "convert", "reader", "replay"])
    parser.add_argument("--build-dir", type=Path, default=root / "build")
    parser.add_argument("--cc", default="cc", help="C compiler command, including cross flags")
    parser.add_argument("--runner", default="", help="x86-64 runner command; empty for native execution")
    args = parser.parse_args()
    pins = Pins(**json.loads((root / "pins.json").read_text()))
    stages = (["bootstrap", "poly", "hol", "convert", "reader", "replay"]
              if args.stage == "reproduce" else [args.stage])
    Preparation(pins, args.build_dir, shlex.split(args.cc), shlex.split(args.runner)).prepare(stages)


if __name__ == "__main__":
    main()
