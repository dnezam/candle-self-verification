#!/usr/bin/env python3
"""Check current HOL raw traces through separate and merged HOL/Candle replay."""

import argparse
from contextlib import ExitStack
import gzip
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

PRODUCER_REV = "beb36f502e21deb268984503442acf7f331a3cbb"
CONVERTER_REV = "f87d9f59bffede4115663219a9120441e43c0a23"
CANDLE_REV = "646e3a2afbf20a8fcfdb15cf7562ee321b74791c"
TARGETS = [
    ("currentAnonB", "original"),
    ("currentAnonB", "cross_anon"),
    ("currentFeatures", "tiny_type"),
    ("currentFeatures", "pair_spec"),
    ("currentFeatures", "pair_def"),
    ("currentFeatures", "capture"),
    ("currentFeatures", "shadow"),
    ("currentFeatures", "gen_abs_none"),
    ("currentFeatures", "simultaneous"),
    ("currentFeatures", "marked"),
    ("currentCompute", "add"),
]
MODULES = ["PFTOpcodes", "PFTReader", "PFTReplay"]


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def git_source(path: Path, expected: str, *, allow_dirty: bool = False) -> dict[str, str | bool]:
    """Verify the exact source commit and require committed inputs by default."""
    actual = subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True,
    ).strip()
    wanted = subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", expected + "^{commit}"], text=True,
    ).strip()
    if actual != wanted:
        raise ValueError(f"{path}: HEAD {actual}; expected {wanted}")
    status = subprocess.check_output(
        ["git", "-C", str(path), "status", "--porcelain", "--untracked-files=normal"], text=True,
    )
    if status and not allow_dirty:
        raise ValueError(f"{path}: dirty source checkout; commit changes or use --allow-dirty for development")
    diff = subprocess.check_output(["git", "-C", str(path), "diff", "HEAD", "--binary"])
    return {"commit": actual, "tracked_diff_sha256": hashlib.sha256(diff).hexdigest(),
            "dirty": bool(status)}


def producer_source(hol: Path, expected: str) -> dict[str, object]:
    """Verify producer provenance from its build manifest or a clean source checkout."""
    manifest = hol.parent / "manifest"
    if manifest.is_file():
        lines = manifest.read_text().splitlines()
        if not lines or not lines[0].startswith("holbuild-hol-toolchain-v"):
            raise ValueError("HOL producer manifest is not a holbuild toolchain manifest")
        entries = dict(line.split("=", 1) for line in lines if "=" in line)
        if entries.get("rev") != expected:
            raise ValueError("HOL toolchain manifest revision differs from --producer-rev")
        if entries.get("kernel_variant") != "trknl":
            raise ValueError("HOL producer requires the tracing kernel (--trknl)")
        return {"commit": entries["rev"], "provenance": "holbuild-manifest",
                "manifest": entries, "manifest_sha256": sha256(manifest)}
    if (hol / ".git").exists():
        return git_source(hol, expected) | {"provenance": "clean-git-checkout"}
    raise FileNotFoundError("HOL producer requires a holbuild manifest or a clean Git checkout")


def sml_strings(values: list[str]) -> str:
    return "[" + ", ".join(json.dumps(value) for value in values) + "]"


def verify_checks(log: Path, count: int, *, candle: bool, anonymous: bool) -> None:
    """Require every independently checked sequent and every replay to finish."""
    output = log.read_text()
    lines = output.splitlines()
    names = [f"{thy}${name}" for thy, name in TARGETS]
    if anonymous:
        names.append("currentAnonA#0")
    required = ["CHECKED: " + name for name in names] + ["CURRENT_ALL_CHECKS_PASSED"]
    if any(lines.count(line) != 1 for line in required):
        raise ValueError(f"{log}: missing or duplicated exact sequent checks")
    if candle:
        complete = lines.count("Success!")
    else:
        complete = sum(line.startswith("HOL_REPLAYED: ") for line in lines)
    if complete != count:
        raise ValueError(f"{log}: completed {complete} replays; expected {count}")
    if "EXCEPTION:" in output or "ERROR:" in output:
        raise ValueError(f"{log}: replay reported an error")


class CurrentRun:
    """Run explicit local prerequisites and retain each command and artifact hash."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.root = Path(__file__).resolve().parent
        self.fixtures = self.root / "fixtures/current"
        self.build = args.build_dir.resolve()
        self.build.mkdir(parents=True, exist_ok=True)
        self.hol = args.hol.resolve()
        self.converter = args.converter.resolve()
        self.candle = args.candle.resolve()
        self.runner = shlex.split(args.runner)
        self.report: dict[str, object] = {"replay_verified": False, "completed": []}

    def run(self, command: list[str], *, cwd: Path, output: Path,
            stdin: Path | None = None, env: dict[str, str] | None = None) -> None:
        with (self.build / "commands.log").open("a") as stream:
            stream.write(f"cd {shlex.quote(str(cwd))}\n")
            if env:
                stream.write(" ".join(f"{key}={shlex.quote(value)}" for key, value in env.items()) + " ")
            if env:
                stream.write(shlex.join([f"{key}={value}" for key, value in env.items()]) + " ")
            stream.write(shlex.join(command))
            if stdin:
                stream.write(" < " + shlex.quote(str(stdin)))
            stream.write(" > " + shlex.quote(str(output)) + " 2>&1\n")
        with ExitStack() as stack:
            destination = stack.enter_context(output.open("wb"))
            source = stack.enter_context(stdin.open("rb")) if stdin else subprocess.DEVNULL
            subprocess.run(command, cwd=cwd, stdin=source, stdout=destination,
                           stderr=subprocess.STDOUT, env=os.environ | (env or {}), check=True)

    def hol_run(self, script: Path, log: str, *, minimal: bool = False,
                cwd: Path | None = None) -> None:
        state = "hol.state.min" if minimal else "hol.state0"
        self.run([str(self.hol / "bin/hol"), "run",
                  "--holstate=" + str(self.hol / "bin" / state), str(script)],
                 cwd=cwd or self.build, output=self.build / log)

    def prerequisites(self) -> None:
        for path in [self.hol / "bin/hol", self.hol / "bin/hol.state0",
                     self.hol / "bin/hol.state.min", self.candle / "candle/build/cake"]:
            if not path.is_file():
                raise FileNotFoundError(f"required prebuilt prerequisite: {path}")
        self.report["sources"] = {
            "producer": producer_source(self.hol, self.args.producer_rev),
            "converter": git_source(self.converter, self.args.converter_rev,
                                    allow_dirty=self.args.allow_dirty),
            "candle": git_source(self.candle, self.args.candle_rev,
                                 allow_dirty=self.args.allow_dirty),
        }
        self.report["development_allow_dirty"] = self.args.allow_dirty
        self.report["runtime_sha256"] = {
            "hol": sha256(self.hol / "bin/hol"),
            "candle": sha256(self.candle / "candle/build/cake"),
        }
        self.report["fixture_sha256"] = {
            path.name: sha256(path) for path in sorted(self.fixtures.iterdir()) if path.is_file()
        }
        self.report["driver_sha256"] = sha256(Path(__file__).resolve())
        self.report["converter_source_sha256"] = {
            str(path.relative_to(self.converter)): sha256(path)
            for path in sorted((self.converter / "src/postkernel/prooftrace").iterdir())
            if path.suffix in (".sml", ".sig")
        }
        self.report["candle_source_sha256"] = {
            name: sha256(self.candle / name)
            for name in ("candle/pft/pft.ml", "candle/pft/replay.ml", "candle/pft/misc.ml",
                         "candle/pft/extract_footer", "candle/build/cake")
        }
        self.report["producer_tool_sha256"] = {
            name: sha256(self.hol / "bin" / name)
            for name in ("hol", "hol.state0", "hol.state.min")
        }

    def produce(self) -> None:
        raw = self.build / "traces/raw"
        (raw / ".hol/objs").mkdir(parents=True, exist_ok=True)
        script = self.build / "produce.sml"
        script.write_text(
            'val _ = print ("PRODUCER_KERNEL: " ^ Thm.kernelid ^ "\\n");\n'
            'val _ = print ("PRODUCER_POLYML_VERSION: " ^\n'
            '  Int.toString PolyML.Compiler.compilerVersionNumber ^ "\\n");\n'
            f'val _ = use {json.dumps(str(self.fixtures / "produce.sml"))};\n'
        )
        self.hol_run(script, "produce.log", cwd=raw)
        lines = (self.build / "produce.log").read_text().splitlines()
        if lines.count("CURRENT_FIXTURES_PRODUCED") != 1:
            raise ValueError("producer did not finish all current fixtures")
        self.report["producer_runtime"] = [line for line in lines if line.startswith("PRODUCER_")]

    def convert(self) -> None:
        traces: dict[str, Path] = {}
        for path in sorted((self.hol / "src").rglob("*Theory.tr.gz")) + sorted(
                (self.build / "traces/raw/.hol/objs").glob("*Theory.tr.gz")):
            name = path.name.removesuffix("Theory.tr.gz")
            if name in traces:
                raise ValueError(f"duplicate raw theory {name}: {traces[name]}, {path}")
            traces[name] = path
        for directory in ("hol4", "candle"):
            (self.build / directory).mkdir(exist_ok=True)
        script = self.build / "convert.sml"
        script.write_text(
            f'val pipeline_converter = {json.dumps(str(self.converter))};\n'
            f'val pipeline_fixtures = {json.dumps(str(self.fixtures))};\n'
            f'val pipeline_build = {json.dumps(str(self.build))};\n'
            'val pipeline_traces = [' + ",\n".join(
                f'({json.dumps(name)}, {json.dumps(str(path))})' for name, path in traces.items()
            ) + '];\nval pipeline_targets = [' + ",\n".join(
                f'({json.dumps(thy)}, {json.dumps(name)})' for thy, name in TARGETS
            ) + '];\n'
            f'val _ = use {json.dumps(str(self.fixtures / "run-pipeline.sml"))};\n'
        )
        self.hol_run(script, "convert.log")
        output = (self.build / "convert.log").read_text().splitlines()
        for marker in ("CURRENT_RAW_AUDIT_PASSED", "CURRENT_CONVERSION_AND_MERGE_PASSED"):
            if output.count(marker) != 1:
                raise ValueError("conversion did not finish: " + marker)
        raw_metadata = []
        for line in (self.build / "raw-order.txt").read_text().splitlines():
            name, filename = line.split("\t", 1)
            path = Path(filename)
            with gzip.open(path, "rb") as stream:
                header = stream.read(8)
            if header != b"TR32\x00\x00\x00\xff":
                raise ValueError(f"{path}: expected current TR32 raw trace; got {header.hex()}")
            raw_metadata.append({"theory": name, "sha256": sha256(path),
                                 "header": header.hex()})
        self.report["raw_traces"] = raw_metadata
        inventories = {}
        for path in sorted(self.build.glob("*/*.pft.bin.inventory")):
            entry: dict[str, object] = {"commands": {}, "axioms": []}
            for line in path.read_text().splitlines():
                fields = line.split("\t")
                if fields[0] == "RULESET":
                    entry["ruleset"] = fields[1]
                elif fields[0] == "COMMAND":
                    entry["commands"][fields[1]] = int(fields[2])
                elif fields[0] == "AXIOM":
                    entry["axioms"].append(fields[2] if fields[1] == "NAMED" else None)
            inventories[str(path.relative_to(self.build)).removesuffix(".inventory")] = entry
        self.report["trace_inventory"] = inventories

    def replay_hol(self, mode: str, paths: list[Path]) -> None:
        pft = self.converter / "src/postkernel/prooftrace"
        script = self.build / f"replay-hol4-{mode}.sml"
        script.write_text(
            'val _ = app load ["DArray", "PIntMap"];\n' + "".join(
                f'val _ = use {json.dumps(str(pft / (name + suffix)))};\n'
                for name in MODULES for suffix in (".sig", ".sml")
            ) + 'fun replay_one (path, db) = let\n'
            '  val result = PFTReplay.replay db path\n'
            'in print ("HOL_REPLAYED: " ^ path ^ "\\n"); result end;\n'
            f'val db = List.foldl replay_one PFTReplay.empty_trDB {sml_strings([str(p) for p in paths])};\n'
            f'val _ = use {json.dumps(str(self.fixtures / "check-results.sml"))};\n' +
            ('val _ = check_current_anonymous db;\n' if mode == "multi" else "") +
            'val _ = check_current_results db;\n'
        )
        self.hol_run(script, f"replay-hol4-{mode}.log", minimal=True)
        verify_checks(self.build / f"replay-hol4-{mode}.log", len(paths),
                      candle=False, anonymous=mode == "multi")

    def replay_candle(self, mode: str, paths: list[Path]) -> None:
        reader = (self.candle / "candle/pft/replay.ml").read_text()
        checks = (self.fixtures / "check-results.ml").read_text()
        invocation = 'let _ = replay_all ["merged.candle.pft.bin"];;'
        if reader.count(invocation) != 1:
            raise ValueError("pinned reader entry point changed")
        names = "; ".join(json.dumps(os.path.relpath(path, self.candle / "candle/pft"))
                          for path in paths)
        program = reader.replace(invocation, f"let _ = replay_all [{names}];;")
        program += "\n" + checks + "\nlet _ = "
        if mode == "multi":
            program += "check_current_anonymous (); "
        program += "check_current_results ();;\n"
        driver = self.build / f"replay-candle-{mode}.ml"
        driver.write_text(program)
        request = self.build / f"replay-candle-{mode}-input.ml"
        request.write_text(f'#use {json.dumps(str(driver))};;\n')
        log = self.build / f"replay-candle-{mode}.log"
        self.run(self.runner + [str(self.candle / "candle/build/cake"), "--candle"],
                 cwd=self.candle / "candle/build", output=log, stdin=request,
                 env={"CML_HEAP_SIZE": "8000"})
        verify_checks(log, len(paths), candle=True, anonymous=mode == "multi")

    def execute(self) -> None:
        try:
            for name in ("prerequisites", "produce", "convert"):
                print(f"Current pipeline: {name}; logs in {self.build}", flush=True)
                getattr(self, name)()
                self.report["completed"].append(name)
            for ruleset in ("hol4", "candle"):
                directory = self.build / ruleset
                multi = [Path(line) for line in (directory / "order.txt").read_text().splitlines()]
                for mode, paths in (("multi", multi), ("merged", [directory / "merged.pft.bin"])):
                    print(f"Current pipeline: replay {ruleset} {mode}", flush=True)
                    if ruleset == "hol4":
                        self.replay_hol(mode, paths)
                    else:
                        self.replay_candle(mode, paths)
                    self.report["completed"].append(f"replay-{ruleset}-{mode}")
            self.report["replay_verified"] = True
            self.report["checked_targets"] = [f"{thy}${name}" for thy, name in TARGETS]
            print("Verified eleven exact sequents in separate and merged HOL/Candle sessions.")
        finally:
            self.report["failure"] = str(sys.exception()) if sys.exception() else None
            self.report["artifacts_sha256"] = {
                str(path.relative_to(self.build)): sha256(path)
                for path in sorted(self.build.rglob("*"))
                if path.is_file() and (path.suffix == ".log" or path.name.endswith(".pft.bin"))
            }
            (self.build / "result.json").write_text(json.dumps(self.report, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hol", type=Path, required=True, help="prebuilt tracing HOL toolchain")
    parser.add_argument("--converter", type=Path, required=True, help="HOL checkout with the ported converter")
    parser.add_argument("--candle", type=Path, required=True, help="Candle checkout with the pinned reader and built runtime")
    parser.add_argument("--build-dir", type=Path, default=Path(__file__).resolve().parent / "build/current")
    parser.add_argument("--runner", default="", help="optional runner command, e.g. qemu-x86_64-static")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="development only: allow uncommitted converter/reader source")
    parser.add_argument("--producer-rev", default=PRODUCER_REV)
    parser.add_argument("--converter-rev", default=CONVERTER_REV)
    parser.add_argument("--candle-rev", default=CANDLE_REV)
    CurrentRun(parser.parse_args()).execute()


if __name__ == "__main__":
    main()
