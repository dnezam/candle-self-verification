"""Failure propagation checks; these do not substitute for proof replay."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from baseline import Pins, Preparation, sha256


class PreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        pins = Pins(**json.loads(Path("pins.json").read_text()))
        self.preparation = Preparation(pins, self.directory / "build")

    def test_process_failure_preserves_status_and_log(self) -> None:
        with self.assertRaises(subprocess.CalledProcessError) as failure:
            self.preparation.run(["sh", "-c", "echo stage-failed; exit 23"])
        self.assertEqual(failure.exception.returncode, 23)
        self.assertIn("stage-failed", self.preparation.log.read_text())
        self.assertIn("exit 23", self.preparation.commands.read_text())

    def test_corrupt_download_is_rejected(self) -> None:
        source = self.directory / "source.tar.gz"
        source.write_bytes(b"changed archive")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.preparation.download(source.as_uri(), "copy.tar.gz", "0" * 64)

    def test_download_failure_is_not_a_digest_success(self) -> None:
        missing = self.directory / "absent.tar.gz"
        with self.assertRaises(subprocess.CalledProcessError):
            self.preparation.download(missing.as_uri(), "copy.tar.gz", "0" * 64)

    def test_valid_download_preserves_hash(self) -> None:
        source = self.directory / "source.tar.gz"
        source.write_bytes(b"pinned archive")
        downloaded = self.preparation.download(
            source.as_uri(), "copy.tar.gz", sha256(source),
        )
        self.assertEqual(downloaded.read_bytes(), source.read_bytes())

    def test_each_failed_stage_stops_later_stages(self) -> None:
        stages = ["bootstrap", "poly", "hol"]
        for index, stage in enumerate(stages):
            with self.subTest(stage=stage):
                with patch.object(self.preparation, "bootstrap") as bootstrap, \
                     patch.object(self.preparation, "poly") as poly, \
                     patch.object(self.preparation, "hol") as hol:
                    calls = [bootstrap, poly, hol]
                    calls[index].side_effect = subprocess.CalledProcessError(19, stage)
                    with self.assertRaises(subprocess.CalledProcessError):
                        self.preparation.prepare(stages)
                    for later in calls[index + 1:]:
                        later.assert_not_called()
                    report = json.loads(
                        (self.preparation.directory / "preparation.json").read_text()
                    )
                    self.assertEqual(report["completed"], stages[:index])
                    self.assertEqual(report["last_stage_status"], "failed")
                    self.assertEqual(report["last_stage"], stage)
                    self.assertFalse(report["replay_verified"])
                    self.assertEqual(report["replayed_targets"], [])

    def test_preparation_success_does_not_claim_replay(self) -> None:
        with patch.object(self.preparation, "bootstrap"):
            self.preparation.prepare(["bootstrap"])
        report = json.loads(
            (self.preparation.directory / "preparation.json").read_text()
        )
        self.assertEqual(report["last_stage_status"], "completed")
        self.assertFalse(report["replay_verified"])


if __name__ == "__main__":
    unittest.main()
