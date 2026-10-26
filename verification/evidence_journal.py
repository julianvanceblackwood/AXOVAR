"""Self-contained local evidence journal for synthetic AXOVAR audit receipts.

A tamper-evident append-only file under a cooperative-host threat model.
NOT tamper-proof, signed, remotely anchored or suited to regulated custody.
"""
from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path

from verification.decision_reference import verify

ZERO = "0" * 64
MAX_BYTES = 8_000_000
MAX_ENTRIES = 128


class JournalError(ValueError):
    pass


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _unique_pairs(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise JournalError("duplicate JSON field")
        out[k] = v
    return out


def _decode(text):
    return json.loads(text, object_pairs_hook=_unique_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(JournalError("invalid constant")))


def _scan(data: bytes) -> dict:
    if len(data) > MAX_BYTES:
        raise JournalError("journal size limit exceeded")
    if data and not data.endswith(b"\n"):
        raise JournalError("truncated journal record")
    head, count = ZERO, 0
    for line in data.splitlines():
        count += 1
        if count > MAX_ENTRIES or len(line) > 160_000:
            raise JournalError("record count or length limit exceeded")
        try:
            record = _decode(line.decode("ascii"))
            if type(record) is not dict or set(record) != {
                "sequence", "previous_sha256", "fixture_b64",
                "envelope", "record_sha256"
            }:
                raise JournalError("invalid record schema")
            if type(record["sequence"]) is not int or record["sequence"] != count:
                raise JournalError("broken record sequence")
            if record["previous_sha256"] != head:
                raise JournalError("broken previous-record link")
            recorded_hash = record["record_sha256"]
            payload = {k:v for k,v in record.items() if k != "record_sha256"}
            expected_hash = hashlib.sha256(canonical(payload)).hexdigest()
            if recorded_hash != expected_hash:
                raise JournalError("record checksum mismatch")
            fixture = base64.b64decode(record["fixture_b64"], validate=True)
            if len(fixture) > 100_000 or not verify(record["envelope"], fixture)["valid"]:
                raise JournalError("embedded receipt disagrees with fixture")
            head = expected_hash
        except (UnicodeError, ValueError, TypeError, KeyError, OverflowError) as exc:
            raise JournalError(f"invalid journal entry {count}: {type(exc).__name__}") from exc
    return {"valid": True, "entries": count, "head_sha256": head,
            "signed": False, "independently_anchored": False}


def verify_journal(path: Path) -> dict:
    if not path.exists():
        raise JournalError("journal does not exist")
    if path.is_symlink():
        raise JournalError("symlink journal is not supported")
    return _scan(path.read_bytes())


def append(path: Path, envelope: dict, fixture: bytes) -> dict:
    if not verify(envelope, fixture)["valid"]:
        raise JournalError("cannot journal an invalid receipt")
    if len(fixture) > 100_000:
        raise JournalError("fixture too large")
    # O_NOFOLLOW prevents a supplied path from redirecting writes via a symlink.
    flags = os.O_RDWR | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "r+b", buffering=0) as file:
            fcntl.flock(file.fileno(), fcntl.LOCK_EX)
            try:
                file.seek(0)
                state = _scan(file.read())
                if state["entries"] >= MAX_ENTRIES:
                    raise JournalError("journal full")
                payload = {
                    "sequence": state["entries"] + 1,
                    "previous_sha256": state["head_sha256"],
                    "fixture_b64": base64.b64encode(fixture).decode("ascii"),
                    "envelope": envelope,
                }
                payload["record_sha256"] = hashlib.sha256(canonical(payload)).hexdigest()
                encoded = canonical(payload) + b"\n"
                if file.tell() + len(encoded) > MAX_BYTES:
                    raise JournalError("journal size limit exceeded")
                file.seek(0, os.SEEK_END)
                file.write(encoded)
                os.fsync(file.fileno())
                return _scan_from_head(payload)
            finally:
                fcntl.flock(file.fileno(), fcntl.LOCK_UN)
    except BaseException:
        # fdopen owns the descriptor and closes it when exiting its context.
        raise


def _scan_from_head(payload):
    return {"valid": True, "entries": payload["sequence"],
            "head_sha256": payload["record_sha256"], "signed": False,
            "independently_anchored": False}


def main() -> int:
    cli=argparse.ArgumentParser(description="Record or verify local synthetic evidence")
    sub=cli.add_subparsers(dest="command", required=True)
    ap=sub.add_parser("append")
    ap.add_argument("--journal", required=True, type=Path)
    ap.add_argument("--receipt", required=True, type=Path)
    ap.add_argument("--fixture", required=True, type=Path)
    vp=sub.add_parser("verify")
    vp.add_argument("--journal", required=True, type=Path)
    args=cli.parse_args()
    try:
        result = (append(args.journal, _decode(args.receipt.read_text()), args.fixture.read_bytes())
                  if args.command=="append" else verify_journal(args.journal))
        print(json.dumps(result, sort_keys=True))
        return 0
    except (JournalError, OSError, UnicodeError, ValueError, TypeError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)},sort_keys=True))
        return 1


if __name__=="__main__":
    raise SystemExit(main())
