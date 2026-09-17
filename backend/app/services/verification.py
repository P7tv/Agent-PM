"""Run deterministic project checks and trust process exit codes, not prose."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
import shlex
import yaml
from typing import Any, Dict, List

from app.services.process_runner import run_process
from app.services.acceptance_evidence import source_revision


CONFIG_NAMES = (".agent-pm.yml", ".agent-pm.yaml")


def load_project_config(workspace: str) -> Dict[str, Any]:
    root = Path(workspace).resolve()
    for name in CONFIG_NAMES:
        path = root / name
        if path.is_file():
            try:
                data = yaml.safe_load(path.read_text()) or {}
                return data if isinstance(data, dict) else {}
            except (OSError, yaml.YAMLError):
                return {}
    return {}


def _configured_checks(root: Path, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    verification = config.get("verification", {})
    raw_checks = verification.get("checks", []) if isinstance(verification, dict) else []
    checks = []
    for index, raw in enumerate(raw_checks if isinstance(raw_checks, list) else []):
        if not isinstance(raw, dict):
            continue
        command = raw.get("command")
        if isinstance(command, str):
            try:
                args = shlex.split(command)
            except ValueError:
                continue
        elif isinstance(command, list) and all(isinstance(item, str) for item in command):
            args = command
        else:
            continue
        if not args or any(token in {"|", "&&", "||", ";", ">", ">>"} for token in args):
            continue
        cwd = (root / str(raw.get("cwd", "."))).resolve()
        try:
            cwd.relative_to(root)
        except ValueError:
            continue
        if not cwd.is_dir():
            continue
        checks.append({
            "name": str(raw.get("name") or f"configured check {index + 1}"),
            "args": args,
            "cwd": str(cwd),
            "kind": str(raw.get("kind") or "test"),
            "required": bool(raw.get("required", True)),
            "timeout_seconds": float(raw.get("timeout_seconds") or verification.get("timeout_seconds") or 120),
        })
    return checks


def _package_files(root: Path) -> list[Path]:
    files = []
    direct = root / "package.json"
    if direct.is_file():
        files.append(direct)
    for child in root.iterdir() if root.is_dir() else []:
        candidate = child / "package.json"
        if child.is_dir() and child.name not in {"node_modules", ".git", "dist", "build"} and candidate.is_file():
            files.append(candidate)
    return files


def _npm_args(script_name: str, script: str) -> list[str]:
    args = [shutil.which("npm") or "npm", "run", script_name]
    if script_name == "test":
        if "vitest" in script and "run" not in script.split():
            args += ["--", "--run"]
        elif "jest" in script:
            args += ["--", "--watchAll=false"]
    return args


def _is_read_only_script(script: str) -> bool:
    """Reject common watch/fix modes that mutate files or never terminate."""
    try:
        tokens = {token.lower() for token in shlex.split(script)}
    except ValueError:
        return False
    blocked = {"--watch", "--watchall", "--fix", "--write", "-w", "dev", "serve", "start"}
    return not (tokens & blocked) and not any(token.startswith("--watch=") for token in tokens)


def detect_verification_commands(workspace: str, trusted_config=None) -> List[Dict[str, Any]]:
    root = Path(workspace).resolve()
    configured = _configured_checks(root, load_project_config(str(root)) if trusted_config is None else trusted_config)
    if configured:
        return configured
    checks: List[Dict[str, Any]] = []
    for package_file in _package_files(root):
        try:
            package = json.loads(package_file.read_text())
        except (OSError, ValueError):
            continue
        scripts = package.get("scripts", {})
        if not isinstance(scripts, dict):
            continue
        relative_cwd = package_file.parent.relative_to(root).as_posix()
        for name in ("test", "typecheck", "check", "lint", "build"):
            script = scripts.get(name)
            if script and _is_read_only_script(str(script)):
                checks.append({
                    "name": f"npm {name}" + (f" ({relative_cwd})" if relative_cwd != "." else ""),
                    "args": _npm_args(name, str(script)), "cwd": str(package_file.parent),
                    "kind": "test" if name == "test" else name, "required": True,
                })

    python_markers = ("pytest.ini", "pyproject.toml", "setup.py", "requirements.txt", "tests")
    python_roots = []
    if any((root / name).exists() for name in python_markers):
        python_roots.append(root)
    if not python_roots:
        for child in root.iterdir() if root.is_dir() else []:
            if child.is_dir() and child.name not in {"node_modules", ".git", "dist", "build"}:
                if any((child / name).exists() for name in python_markers):
                    python_roots.append(child)
    for python_root in dict.fromkeys(python_roots):
        rel = python_root.relative_to(root).as_posix()
        checks.append({
            "name": "pytest" + (f" ({rel})" if rel != "." else ""),
            "args": [sys.executable, "-m", "pytest", "-q"], "cwd": str(python_root), "kind": "test",
            "required": True,
        })

    if (root / "go.mod").is_file():
        checks.extend([
            {"name": "go test", "args": [shutil.which("go") or "go", "test", "./..."], "cwd": str(root), "kind": "test", "required": True},
            {"name": "go vet", "args": [shutil.which("go") or "go", "vet", "./..."], "cwd": str(root), "kind": "lint", "required": True},
        ])
    if (root / "Cargo.toml").is_file():
        checks.extend([
            {"name": "cargo test", "args": [shutil.which("cargo") or "cargo", "test"], "cwd": str(root), "kind": "test", "required": True},
            {"name": "cargo check", "args": [shutil.which("cargo") or "cargo", "check"], "cwd": str(root), "kind": "build", "required": True},
        ])
    order = {"test": 0, "typecheck": 1, "check": 1, "lint": 2, "build": 3}
    checks.sort(key=lambda item: (order.get(item["kind"], 9), item["name"]))
    return checks


def detect_test_command(workspace: str):
    """Backward-compatible helper returning the first actual test command."""
    check = next((item for item in detect_verification_commands(workspace) if item["kind"] == "test"), None)
    return check["args"] if check else None


async def verify_workspace(workspace: str, trusted_config=None) -> Dict[str, Any]:
    revision = source_revision(workspace)
    checks = detect_verification_commands(workspace, trusted_config)
    if not checks:
        return {
            "status": "NOT_RUN", "exit_code": None, "command": "", "stdout": "",
            "stderr": "No supported test, lint, typecheck, or build command found.", "checks": [],
        }

    timeout = float(os.environ.get("TEST_TIMEOUT_SECONDS", "120"))
    results = []
    for check in checks:
        command = " ".join(check["args"])
        try:
            result = await run_process(check["args"], check["cwd"], check.get("timeout_seconds", timeout))
            status = "PASSED" if result["exit_code"] == 0 else "FAILED" if check.get("required", True) else "WARNING"
            results.append({
                "name": check["name"], "kind": check["kind"], "status": status,
                "required": check.get("required", True),
                "exit_code": result["exit_code"], "command": command,
                "stdout": result.get("stdout", "")[-12000:], "stderr": result.get("stderr", "")[-4000:],
            })
        except Exception as exc:
            results.append({
                "name": check["name"], "kind": check["kind"], "status": "ERROR",
                "required": check.get("required", True),
                "exit_code": None, "command": command, "stdout": "", "stderr": str(exc),
            })
        if results[-1]["status"] in {"FAILED", "ERROR"} and results[-1]["required"]:
            break

    failed = next((item for item in results if item["status"] in {"FAILED", "ERROR"} and item["required"]), None)
    representative = failed or results[-1]
    status = "PASSED" if len(results) == len(checks) and not failed else representative["status"]
    summary = "\n\n".join(
        f"[{item['status']}] {item['name']}\n{item['stdout']}\n{item['stderr']}".strip() for item in results
    )
    return {
        "status": status, "exit_code": representative["exit_code"], "command": representative["command"],
        "stdout": summary[-20000:], "stderr": representative["stderr"], "checks": results,
        "source_revision": revision, "source_unchanged": source_revision(workspace) == revision,
    }
