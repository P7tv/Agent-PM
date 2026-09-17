"""Reproduce Resume conflict behavior using only disposable temporary files.

Run: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend python docs/research/checkpoint_conflict_probe.py
This is a diagnostic probe, not a passing correctness test or a production fix.
"""
import json
import tempfile
from pathlib import Path

from app.services.workspace_session import WorkspaceSession


def main():
    with tempfile.TemporaryDirectory(prefix="agentpm-resume-probe-") as directory:
        root = Path(directory)
        original = root / "original"
        original.mkdir()
        target = original / "app.txt"
        target.write_text("initial\n", encoding="utf-8")
        first = WorkspaceSession(str(original), str(root / "runs"), "first")
        (first.workspace / "app.txt").write_text("agent edit\n", encoding="utf-8")
        checkpoint = str(first.workspace)
        first.close(delete=False)
        target.write_text("human edit while paused\n", encoding="utf-8")
        resumed = WorkspaceSession(str(original), str(root / "runs"), "resumed", checkpoint)
        blocked = False
        try:
            resumed.commit()
        except RuntimeError:
            blocked = True
        finally:
            resumed.close(delete=True)
        result = target.read_text(encoding="utf-8").strip()
        print(json.dumps({
            "conflict_blocked": blocked,
            "human_edit_preserved": result == "human edit while paused",
            "actual_content": result,
        }, indent=2))


if __name__ == "__main__":
    main()
