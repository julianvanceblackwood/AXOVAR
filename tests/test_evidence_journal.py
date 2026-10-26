"""Local evidence journal append, replay, and corruption checks."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BINARY = Path(sys.argv[1]).resolve()
ROOT = Path(sys.argv[2]).resolve()
sys.argv = [sys.argv[0]]
sys.path.insert(0, str(ROOT))

from server.audit import build_receipt
from verification.evidence_journal import JournalError, append, verify_journal


def evidence():
    fixture = (ROOT / "scenarios" / "NORMAL-001.csv").read_bytes()
    state = json.loads(subprocess.check_output(
        [str(BINARY), "--scenario",
         str(ROOT / "scenarios" / "NORMAL-001.csv"), "9"], text=True, timeout=5))
    return fixture, build_receipt(state, fixture)


class JournalTests(unittest.TestCase):
    def test_append_and_verify_replay(self):
        fixture, envelope = evidence()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "evidence.jsonl"
            a = append(path, envelope, fixture)
            self.assertEqual(a["entries"], 1)
            b = append(path, envelope, fixture)
            self.assertEqual(b["entries"], 2)
            self.assertNotEqual(a["head_sha256"], b["head_sha256"])
            self.assertEqual(verify_journal(path), b)
            self.assertFalse(b["signed"])
            self.assertFalse(b["independently_anchored"])

    def test_modified_or_truncated_file_rejected_without_repair(self):
        fixture, envelope = evidence()
        for variant in ("truncation", "tampering"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "journal.jsonl"
                append(path, envelope, fixture)
                raw = path.read_bytes()
                if variant == "truncation":
                    raw = raw[:-1]
                else:
                    raw = raw.replace(b'"sequence":1', b'"sequence":2', 1)
                path.write_bytes(raw)
                with self.assertRaises(JournalError):
                    verify_journal(path)
                with self.assertRaises(JournalError):
                    append(path, envelope, fixture)
                self.assertEqual(path.read_bytes(), raw)

    def test_invalid_receipt_not_appended(self):
        fixture, envelope = evidence()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "journal.jsonl"
            envelope["receipt"]["policy"]["result"] = "DENY_SIMULATION"
            with self.assertRaises(JournalError):
                append(path, envelope, fixture)
            self.assertFalse(path.exists())

    def test_symlink_not_writable(self):
        fixture, envelope = evidence()
        with tempfile.TemporaryDirectory() as folder:
            actual = Path(folder) / "actual.jsonl"
            actual.write_bytes(b"")
            symlink = Path(folder) / "link.jsonl"
            symlink.symlink_to(actual)
            with self.assertRaises(OSError):
                append(symlink, envelope, fixture)
            self.assertEqual(actual.read_bytes(), b"")

    def test_cli_checks_saved_fixture(self):
        fixture, envelope = evidence()
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder)
            source=directory / "fixture.csv"
            receipt=directory / "receipt.json"
            journal=directory / "journal.jsonl"
            source.write_bytes(fixture)
            receipt.write_text(json.dumps(envelope), encoding="utf-8")
            command=[sys.executable,"-m","verification.evidence_journal"]
            a=subprocess.run([*command,"append","--journal",str(journal),
                              "--receipt",str(receipt),"--fixture",str(source)],
                              cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(a.returncode,0,a.stdout+a.stderr)
            b=subprocess.run([*command,"verify","--journal",str(journal)],
                              cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(b.returncode,0,b.stdout+b.stderr)
            self.assertEqual(json.loads(b.stdout)["entries"],1)


if __name__=="__main__":
    unittest.main(verbosity=2)
