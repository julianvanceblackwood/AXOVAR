"""Compare exact C++ replay output bytes from two independent compiler builds."""
from __future__ import annotations
import hashlib
import json
import subprocess
import sys
from pathlib import Path

def compare(first: Path, second: Path, root: Path) -> dict:
    evaluated=0
    for name in ("NORMAL-001", "DEGRADED-001"):
        fixture=root / "scenarios" / (name + ".csv")
        count=len([row for row in fixture.read_text(encoding="utf-8").splitlines()[1:] if row])
        for step in range(count + 1):
            argv=["--scenario", str(fixture), str(step)]
            out_a=subprocess.check_output([str(first), *argv], timeout=5)
            out_b=subprocess.check_output([str(second), *argv], timeout=5)
            if out_a != out_b:
                raise AssertionError(f"compiler output differs: scenario={name} step={step}")
            data=json.loads(out_a)
            if data.get("step") != step or data.get("total") != count:
                raise AssertionError("unexpected replay boundary")
            evaluated+=1
    return {"compared_replays": evaluated, "byte_identical": True,
            "operating_system": "Linux CI only",
            "architecture_independent": False}


if __name__=="__main__":
    a, b, root = map(Path,sys.argv[1:4])
    print(json.dumps(compare(a.resolve(), b.resolve(), root.resolve()),sort_keys=True))
