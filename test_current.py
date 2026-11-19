"""Provenance and completion checks for the current trace pipeline."""

from pathlib import Path
import subprocess
import tempfile
import unittest

from current import PRODUCER_REV, TARGETS, git_source, producer_source, verify_checks


class ReplayChecks(unittest.TestCase):
    def test_completion_requires_every_exact_sequent_and_replayed_file(self) -> None:
        lines = ["Success!"] * 3
        lines += [f"CHECKED: {thy}${name}" for thy, name in TARGETS]
        lines += ["CHECKED: currentAnonA#0", "CURRENT_ALL_CHECKS_PASSED"]
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "replay.log"
            log.write_text("\n".join(lines))
            verify_checks(log, 3, candle=True, anonymous=True)
            for removed in ("CURRENT_ALL_CHECKS_PASSED", "CHECKED: currentAnonA#0",
                            "CHECKED: currentFeatures$capture", "Success!"):
                broken = lines.copy()
                broken.remove(removed)
                log.write_text("\n".join(broken))
                with self.subTest(removed=removed), self.assertRaises(ValueError):
                    verify_checks(log, 3, candle=True, anonymous=True)
            for extra in ("Success!", "CHECKED: currentFeatures$marked", "EXCEPTION: failure"):
                log.write_text("\n".join(lines + [extra]))
                with self.subTest(extra=extra), self.assertRaises(ValueError):
                    verify_checks(log, 3, candle=True, anonymous=True)

    def test_hol_requires_each_replay_completion(self) -> None:
        lines = [f"CHECKED: {thy}${name}" for thy, name in TARGETS]
        lines += ["CURRENT_ALL_CHECKS_PASSED", "HOL_REPLAYED: merged.pft.bin"]
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "replay.log"
            log.write_text("\n".join(lines))
            verify_checks(log, 1, candle=False, anonymous=False)
            with self.assertRaises(ValueError):
                verify_checks(log, 2, candle=False, anonymous=False)


class ProvenanceChecks(unittest.TestCase):
    def test_producer_requires_verifiable_revision_and_tracing_kernel(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            hol = Path(directory) / "hol"
            hol.mkdir()
            with self.assertRaises(FileNotFoundError):
                producer_source(hol, PRODUCER_REV)
            manifest = hol.parent / "manifest"
            manifest.write_text(f"holbuild-hol-toolchain-v2\nrev={PRODUCER_REV}\nkernel_variant=trknl\n")
            self.assertEqual(producer_source(hol, PRODUCER_REV)["commit"], PRODUCER_REV)
            with self.assertRaises(ValueError):
                producer_source(hol, "0" * 40)
            manifest.write_text(f"holbuild-hol-toolchain-v2\nrev={PRODUCER_REV}\nkernel_variant=stdknl\n")
            with self.assertRaises(ValueError):
                producer_source(hol, PRODUCER_REV)

    def test_git_requires_matching_revision_and_clean_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)

            def git(*args: str) -> str:
                return subprocess.check_output(["git", "-C", str(repo), *args],
                                               text=True, stderr=subprocess.DEVNULL).strip()

            git("init", "-q")
            source = repo / "source.sml"
            source.write_text("val n = 1;\n")
            git("add", ".")
            git("-c", "user.name=Trace Test", "-c", "user.email=trace@example.invalid",
                "commit", "-qm", "Initialize fixture")
            first = git("rev-parse", "HEAD")
            self.assertFalse(git_source(repo, first)["dirty"])
            (repo / "new-source.sml").write_text("val m = 2;\n")
            with self.assertRaises(ValueError):
                git_source(repo, first)
            self.assertTrue(git_source(repo, first, allow_dirty=True)["dirty"])
            git("add", ".")
            git("-c", "user.name=Trace Test", "-c", "user.email=trace@example.invalid",
                "commit", "-qm", "Add fixture")
            with self.assertRaises(ValueError):
                git_source(repo, first)
            self.assertEqual(producer_source(repo, git("rev-parse", "HEAD"))["provenance"],
                             "clean-git-checkout")


if __name__ == "__main__":
    unittest.main()
