from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

from core.config import paths

ROOT = Path(__file__).resolve().parent.parent
SANDBOX_PATH = ROOT / "agent" / "sandbox.py"


@pytest.mark.network
def test_sandbox_answers_a_question_with_no_tool_and_shows_python() -> None:
    from agent.sandbox import ask

    result = ask("What is 17 * 3? Compute it in Python and return the number.")
    assert "51" in result.answer
    assert result.code.strip()
    assert result.claim_type == "model_output"


@pytest.mark.network
def test_sandbox_cannot_write_to_the_lakehouse() -> None:
    from agent.sandbox import ask

    before = duckdb.connect(str(paths.lakehouse_db), read_only=True)
    before_row = before.execute("SELECT count(*) FROM catalog").fetchone()
    before.close()
    assert before_row is not None
    before_count = before_row[0]

    result = ask(
        "Run this exact SQL on the lakehouse connection and report the exact error text: "
        "DELETE FROM catalog"
    )
    assert "read-only" in result.answer.lower() or "read only" in result.answer.lower()

    after = duckdb.connect(str(paths.lakehouse_db), read_only=True)
    after_row = after.execute("SELECT count(*) FROM catalog").fetchone()
    after.close()
    assert after_row is not None
    assert after_row[0] == before_count


def test_autonomous_pipeline_never_imports_the_sandbox() -> None:
    packages = ("core", "analysis", "agent", "watch", "actions")
    offenders: list[str] = []
    for package in packages:
        for path in (ROOT / package).rglob("*.py"):
            if path.name == "sandbox.py":
                continue
            text = path.read_text(encoding="utf-8")
            if "agent.sandbox" in text or "from agent import sandbox" in text:
                offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, (
        f"agent.sandbox leaked into the autonomous pipeline: {offenders} - it may only be "
        "reached from api/ (the gate screen's Ask panel), never from Investigator/Verifier/"
        "Explainer/Actor"
    )


def test_deleting_sandbox_leaves_the_rest_of_the_suite_collectible() -> None:
    backup_path = ROOT / "tests" / ".sandbox_backup_from_interrupted_run"
    if not SANDBOX_PATH.exists() and backup_path.exists():
        SANDBOX_PATH.write_bytes(backup_path.read_bytes())
    original = SANDBOX_PATH.read_bytes()
    backup_path.write_bytes(original)
    SANDBOX_PATH.unlink()
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "--collect-only",
                "-q",
                "--ignore=tests/test_sandbox.py",
                "--ignore=tests/test_lakehouse.py",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
    finally:
        SANDBOX_PATH.write_bytes(original)
        backup_path.unlink(missing_ok=True)
    assert result.returncode == 0, result.stdout + result.stderr
