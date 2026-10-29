#!/usr/bin/env python3
"""Run every published P3 test against its hash-pinned upstream runtime."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=["all", "core", "rehearsal", "audit"], default="all")
    args, pytest_args = parser.parse_known_args()
    exported = json.loads((ROOT / "docs/PUBLIC_EXPORT_MANIFEST.json").read_text())["files"]
    pins = json.loads((ROOT / "reproduction/p3_snapshot/manifest.json").read_text())
    with tempfile.TemporaryDirectory(prefix="published-p3-") as directory:
        runtime = Path(directory)
        for rel in exported:
            if rel.startswith(("src/", "scripts/", "tests/", "docs/p3/", "worlds/")):
                target = runtime / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / rel, target)
        # Include public test harness additions that are not historical exports.
        for rel in ["pyproject.toml", "tests/conftest.py"]:
            shutil.copy2(ROOT / rel, runtime / rel)
        for rel, expected in pins.items():
            source = ROOT / "reproduction/p3_snapshot" / rel
            if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
                raise ValueError("pinned runtime hash mismatch: " + rel)
            shutil.copy2(source, runtime / rel)
        subprocess.run(["git", "init", "-q", str(runtime)], check=True)
        subprocess.run(["git", "add", "."], cwd=runtime, check=True)
        subprocess.run(["git", "-c", "user.name=Reproduction fixture", "-c", "user.email=reproduction@example.invalid",
                        "commit", "-qm", "Published P3 test fixture"], cwd=runtime, check=True)
        tests = sorted(str(p.relative_to(runtime)) for p in (runtime / "tests").glob("test_p3_*.py"))
        heavy = {"rehearsal": "tests/test_p3_transfer_rehearsal_v1.py", "audit": "tests/test_p3_transfer_batch_audit_v1.py"}
        if args.group == "core":
            tests = [p for p in tests if p not in heavy.values()]
        elif args.group in heavy:
            tests = [heavy[args.group]]
        return subprocess.run([sys.executable, "-m", "pytest", "-o", "addopts=", "-q", *tests, *pytest_args], cwd=runtime).returncode


if __name__ == "__main__":
    raise SystemExit(main())
