"""Failure propagation checks; these do not substitute for proof replay."""

from contextlib import ExitStack
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from baseline import Pins, Preparation, TARGETS, check_replay_output, sha256


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
        stages = ["bootstrap", "poly", "hol", "convert", "reader", "replay"]
        for index, stage in enumerate(stages):
            with self.subTest(stage=stage):
                with ExitStack() as stack:
                    calls = [stack.enter_context(patch.object(self.preparation, name))
                             for name in stages]
                    calls[index].side_effect = subprocess.CalledProcessError(19, stage)
                    with self.assertRaises(subprocess.CalledProcessError):
                        self.preparation.prepare(stages)
                    for later in calls[index + 1:]:
                        later.assert_not_called()
                    report = json.loads(
                        (self.preparation.directory / "result.json").read_text()
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
            (self.preparation.directory / "result.json").read_text()
        )
        self.assertEqual(report["last_stage_status"], "completed")
        self.assertFalse(report["replay_verified"])


class ReplayOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.output = "\n".join(
            ["Success!"] * 19 + [f"CHECKED: {name}" for name in TARGETS]
            + ["ALL_CHECKS_PASSED"]
        )

    def test_complete_replay_is_accepted(self) -> None:
        check_replay_output(self.output, 19)

    def test_process_success_without_sequent_checks_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            check_replay_output("Success!\n" * 19, 19)

    def test_repl_error_cannot_be_hidden_by_later_success(self) -> None:
        with self.assertRaises(ValueError):
            check_replay_output("EXCEPTION: Failure unexpected\n" + self.output, 19)

    def test_missing_target_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            check_replay_output(self.output.replace("CHECKED: smallCompute$add", ""), 19)

    def test_duplicate_marker_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            check_replay_output(self.output + "\nALL_CHECKS_PASSED", 19)

    def test_incomplete_trace_list_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            check_replay_output(self.output, 20)


if __name__ == "__main__":
    unittest.main()
