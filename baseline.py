#!/usr/bin/env python3
"""Prepare pinned historical sources; this does not certify a proof replay."""

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys


@dataclass(frozen=True)
class Pins:
    polyml: str
    polyml_archive_sha256: str
    hol: str
    candle: str
    cakeml_bootstrap: str
    hol_bootstrap: str
    bootstrap_job: int
    bootstrap_archive_sha256: str
    holbuild: str
    holbuild_version: str


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class Preparation:
    """Keep commands, failures and artifact hashes in one build directory."""

    def __init__(self, pins: Pins, directory: Path) -> None:
        self.pins = pins
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.commands = self.directory / "commands.log"
        self.log = self.directory / "prepare.log"

    def run(
        self, command: list[str], *, cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        location = cwd or self.directory
        with self.commands.open("a") as log:
            log.write(f"cd {shlex.quote(str(location))}\n")
            if env:
                log.write(" ".join(f"{k}={shlex.quote(v)}" for k, v in env.items()))
                log.write(" ")
            log.write(shlex.join(command) + "\n")
        with self.log.open("ab") as log:
            subprocess.run(
                command, cwd=location, env=os.environ | (env or {}),
                stdout=log, stderr=subprocess.STDOUT, check=True,
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
        """Attempt the pinned producer build through holbuild."""
        version = subprocess.check_output(["holbuild", "--version"], text=True).strip()
        expected = f"holbuild {self.pins.holbuild_version}"
        if version != expected:
            raise ValueError(f"{version}; expected {expected}")
        poly = self.directory / "polyml/bin/poly"
        if not poly.is_file():
            raise FileNotFoundError(f"build Poly/ML first: {poly}")
        project = self.directory / "producer"
        project.mkdir(exist_ok=True)
        (project / "holproject.toml").write_text(
            '[project]\nname = "candle-historical-producer"\n\n'
            '[build]\nroots = []\n\n'
            '[dependencies.hol]\n'
            'git = "https://github.com/HOL-Theorem-Prover/HOL.git"\n'
            f'rev = "{self.pins.hol}"\n'
        )
        self.run(
            ["holbuild", "--source-dir", str(project), "-j8", "buildhol", "--trknl"],
            env={
                "HOLBUILD_POLY": str(poly),
                "HOLBUILD_POLYC": str(poly.with_name("polyc")),
                "HOLBUILD_CACHE": str(self.directory / "holbuild-cache"),
            },
        )

    def prepare(self, stages: list[str]) -> None:
        report = self.directory / "preparation.json"
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
                    ("polyml.tar.gz", "cake-x64-64.tar.gz", "export-probe.tr")
                    if (self.directory / name).is_file()
                ]
                report.write_text(json.dumps({
                    "pins": asdict(self.pins), "completed": completed,
                    "last_stage": stage, "last_stage_status": status,
                    "failure": str(sys.exception()) if sys.exception() else None,
                    "sha256": {p.name: sha256(p) for p in artifacts},
                    "replayed_targets": [],
                    "replay_verified": False,
                }, indent=2) + "\n")
        print("Preparation completed; no proof replay has been verified.")


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["prepare", "bootstrap", "poly", "hol"])
    parser.add_argument("--build-dir", type=Path, default=root / "build")
    args = parser.parse_args()
    pins = Pins(**json.loads((root / "pins.json").read_text()))
    stages = ["bootstrap", "poly", "hol"] if args.stage == "prepare" else [args.stage]
    Preparation(pins, args.build_dir).prepare(stages)


if __name__ == "__main__":
    main()
