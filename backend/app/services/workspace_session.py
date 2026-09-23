"""Stage sprint edits outside the registered workspace and commit them atomically."""
from __future__ import annotations

import hashlib
import json
import difflib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Dict, Iterable


IGNORED_NAMES = {
    ".git", ".hg", ".svn", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".next", ".cache", "__pycache__", "node_modules", "dist", "build",
    "coverage", ".coverage", ".DS_Store",
}
DEPENDENCY_DIRS = {"node_modules", ".venv", "venv"}


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def snapshot_workspace(root: str | Path) -> Dict[str, str]:
    """Return a stable content map while excluding generated/dependency trees."""
    base = Path(root).resolve()
    result: Dict[str, str] = {}
    for current, dirs, files in os.walk(base, followlinks=False):
        current_path = Path(current)
        dirs[:] = [name for name in dirs if name not in IGNORED_NAMES and not (current_path / name).is_symlink()]
        for name in files:
            if name in IGNORED_NAMES:
                continue
            path = current_path / name
            rel = path.relative_to(base).as_posix()
            try:
                if path.is_symlink():
                    result[rel] = "link:" + os.readlink(path)
                elif path.is_file():
                    digest = hashlib.sha256()
                    with path.open("rb") as handle:
                        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                            digest.update(chunk)
                    result[rel] = "file:" + digest.hexdigest()
            except (OSError, PermissionError):
                continue
    return result


def changed_paths(before: Dict[str, str], after: Dict[str, str]) -> Dict[str, list[str]]:
    added = sorted(set(after) - set(before))
    deleted = sorted(set(before) - set(after))
    modified = sorted(path for path in set(before) & set(after) if before[path] != after[path])
    return {"added": added, "modified": modified, "deleted": deleted}


def flatten_changes(changes: Dict[str, Iterable[str]]) -> list[str]:
    return sorted({path for values in changes.values() for path in values})


class WorkspaceSession:
    """A staged source copy with conflict detection and optional durable checkpoints."""

    def __init__(
        self,
        original: str,
        storage_root: str | None = None,
        session_id: str | None = None,
        reuse_path: str | None = None,
        expected_manifest_hash: str | None = None,
    ):
        self.original = Path(original).resolve()
        self._dependency_sources: Dict[str, Path] = {}
        self._mounted_dependencies: Dict[str, str] = {}
        if reuse_path:
            self.workspace = Path(reuse_path).resolve()
            if not self.workspace.is_dir():
                raise ValueError("Sprint checkpoint does not exist")
            self.temp_root = self.workspace.parent
            manifest = self.load_checkpoint_manifest(self.workspace, expected_manifest_hash)
            if manifest["original"] != str(self.original):
                raise ValueError("Checkpoint belongs to a different project workspace")
            self.original_baseline = manifest["original_baseline"]
            self.staged_baseline = manifest["staged_baseline"]
            self._discover_dependencies()
        else:
            if storage_root:
                root = Path(storage_root).resolve()
                root.mkdir(parents=True, exist_ok=True)
                self.temp_root = root / (session_id or next(tempfile._get_candidate_names()))
                self.temp_root.mkdir()
            else:
                self.temp_root = Path(tempfile.mkdtemp(prefix="pm-sprint-"))
            self.workspace = self.temp_root / "workspace"
            self.original_baseline = snapshot_workspace(self.original)
            self._copy_source()
            self.staged_baseline = snapshot_workspace(self.workspace)
            # Keep the initial comparison outside source files. Resuming must
            # never silently replace this with the current original workspace.
            manifest_path = self.temp_root / "checkpoint.json"
            manifest_path.write_text(json.dumps({
                "version": 1, "original": str(self.original),
                "original_baseline": self.original_baseline,
                "staged_baseline": self.staged_baseline,
            }, sort_keys=True), encoding="utf-8")
        self.manifest_hash = hashlib.sha256((self.temp_root / "checkpoint.json").read_bytes()).hexdigest()

    @staticmethod
    def load_checkpoint_manifest(workspace, expected_hash=None):
        path = Path(workspace).resolve().parent / "checkpoint.json"
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 10 * 1024 * 1024:
                raise ValueError("Missing or unsafe checkpoint manifest")
            raw = path.read_bytes()
            if expected_hash and hashlib.sha256(raw).hexdigest() != expected_hash:
                raise ValueError("Checkpoint manifest was changed")
            manifest = json.loads(raw)
            if not isinstance(manifest, dict) or manifest.get("version") != 1 or not isinstance(manifest.get("original"), str):
                raise ValueError("Invalid checkpoint manifest")
            for key in ("original_baseline", "staged_baseline"):
                values = manifest.get(key)
                if not isinstance(values, dict):
                    raise ValueError("Invalid checkpoint baseline")
                for relative, digest in values.items():
                    parts = Path(relative).parts if isinstance(relative, str) else ()
                    if not parts or Path(relative).is_absolute() or ".." in parts or not isinstance(digest, str):
                        raise ValueError("Unsafe checkpoint baseline entry")
            return manifest
        except (OSError, ValueError) as error:
            raise ValueError("Checkpoint has no trusted initial baseline; inspect or recover its files instead of automatic Resume") from error

    def _ignore(self, directory: str, names: list[str]) -> set[str]:
        parent = Path(directory)
        ignored = {name for name in names if name in IGNORED_NAMES or name in DEPENDENCY_DIRS}
        for name in names:
            path = parent / name
            if path.is_symlink() and not _inside(path, self.original):
                ignored.add(name)
        return ignored

    def _copy_source(self) -> None:
        shutil.copytree(self.original, self.workspace, symlinks=True, ignore=self._ignore)
        # Internal absolute links must point at the staged copy, never back at
        # real project files that a writer could mutate through the alias.
        for current, dirs, files in os.walk(self.workspace, followlinks=False):
            for name in dirs + files:
                staged = Path(current) / name
                if not staged.is_symlink():
                    continue
                original_link = self.original / staged.relative_to(self.workspace)
                target = original_link.resolve()
                if not _inside(target, self.original):
                    raise ValueError('Source symlink escapes project workspace')
                staged_target = self.workspace / target.relative_to(self.original)
                staged.unlink()
                staged.symlink_to(os.path.relpath(staged_target, staged.parent))
        # Record dependency trees but do not expose them to implementation
        # agents. They are mounted only while deterministic checks run.
        for current, dirs, _files in os.walk(self.original, followlinks=False):
            current_path = Path(current)
            for name in list(dirs):
                if name in DEPENDENCY_DIRS:
                    source = current_path / name
                    relative = source.relative_to(self.original)
                    self._dependency_sources[relative.as_posix()] = source
                    dirs.remove(name)

    def _discover_dependencies(self) -> None:
        for current, dirs, _files in os.walk(self.original, followlinks=False):
            current_path = Path(current)
            for name in list(dirs):
                if name in DEPENDENCY_DIRS:
                    source = current_path / name
                    self._dependency_sources[source.relative_to(self.original).as_posix()] = source
                    dirs.remove(name)
                elif name in IGNORED_NAMES or (current_path / name).is_symlink():
                    dirs.remove(name)

    def changes(self) -> Dict[str, list[str]]:
        return changed_paths(self.staged_baseline, snapshot_workspace(self.workspace))

    def mount_dependencies(self) -> None:
        for relative, source in self._dependency_sources.items():
            target = self.workspace / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() and not target.is_symlink():
                try:
                    target.symlink_to(source, target_is_directory=True)
                    self._mounted_dependencies[relative] = "symlink"
                except OSError:
                    if os.name != "nt":
                        raise
                    # Directory junctions do not require Windows Developer
                    # Mode/admin rights and are suitable for node_modules and
                    # virtual environments mounted only during verification.
                    result = subprocess.run(
                        ["cmd.exe", "/c", "mklink", "/J", str(target), str(source)],
                        capture_output=True, text=True, timeout=15,
                    )
                    if result.returncode != 0 or not target.exists():
                        raise OSError(
                            f"Unable to mount dependency {relative}: "
                            f"{result.stderr.strip() or result.stdout.strip()}"
                        )
                    self._mounted_dependencies[relative] = "junction"

    def unmount_dependencies(self) -> None:
        for relative, mount_type in list(self._mounted_dependencies.items()):
            target = self.workspace / relative
            if mount_type == "symlink" and target.is_symlink():
                try:
                    source = self._dependency_sources[relative]
                    if target.resolve() == source.resolve():
                        target.unlink()
                except OSError:
                    target.unlink(missing_ok=True)
            elif mount_type == "junction" and target.exists():
                # os.rmdir removes the junction itself, never its target.
                os.rmdir(target)
            self._mounted_dependencies.pop(relative, None)

    def review_diff(self, max_chars: int = 30000) -> str:
        """Create a bounded unified diff for the read-only reviewer."""
        chunks = []
        for rel in flatten_changes(self.changes()):
            before_path = self.original / rel
            after_path = self.workspace / rel

            def read_text(path: Path) -> list[str]:
                if not path.is_file() or path.is_symlink():
                    return []
                try:
                    raw = path.read_bytes()
                    if b"\x00" in raw:
                        return ["<binary file>\n"]
                    return raw.decode("utf-8", errors="replace").splitlines(keepends=True)
                except OSError:
                    return []

            before = read_text(before_path)
            after = read_text(after_path)
            diff = "".join(difflib.unified_diff(
                before, after, fromfile=f"a/{rel}", tofile=f"b/{rel}", n=3,
            ))
            chunks.append(diff or f"Changed binary/symlink: {rel}\n")
            if sum(len(chunk) for chunk in chunks) >= max_chars:
                chunks.append("\n... diff truncated ...\n")
                break
        return "".join(chunks)[:max_chars]

    def commit(self, expected_revision=None) -> Dict[str, list[str]]:
        if expected_revision:
            actual_revision = hashlib.sha256(json.dumps(snapshot_workspace(self.workspace), sort_keys=True).encode()).hexdigest()
            if actual_revision != expected_revision:
                raise RuntimeError('Staged source changed after verification; re-run checks before delivery')
        changes = self.changes()
        paths = flatten_changes(changes)
        current = snapshot_workspace(self.original)
        for rel in paths:
            destination = self.original / rel
            if not _inside(destination, self.original) or any(
                parent.is_symlink() for parent in destination.parents if parent != self.original and _inside(parent, self.original)
            ):
                raise RuntimeError('Unsafe delivery path: ' + rel)
            if rel not in changes['deleted'] and not _inside(self.workspace / rel, self.workspace):
                raise RuntimeError('Staged source path escapes workspace: ' + rel)
        conflicts = [path for path in paths if current.get(path) != self.original_baseline.get(path)]
        if conflicts:
            raise RuntimeError("Workspace changed during sprint: " + ", ".join(conflicts[:20]))

        backup = self.temp_root / "backup"
        shutil.rmtree(backup, ignore_errors=True)
        backup.mkdir()
        existed: set[str] = set()
        try:
            for rel in paths:
                destination = self.original / rel
                if destination.exists() or destination.is_symlink():
                    existed.add(rel)
                    saved = backup / rel
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    if destination.is_symlink():
                        saved.symlink_to(os.readlink(destination))
                    else:
                        shutil.copy2(destination, saved)

            for rel in changes["deleted"]:
                destination = self.original / rel
                if destination.is_file() or destination.is_symlink():
                    destination.unlink()
            for rel in changes["added"] + changes["modified"]:
                source = self.workspace / rel
                destination = self.original / rel
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists() or destination.is_symlink():
                    destination.unlink()
                if source.is_symlink():
                    original_target = self.original / source.resolve().relative_to(self.workspace)
                    destination.symlink_to(os.path.relpath(original_target, destination.parent))
                else:
                    shutil.copy2(source, destination)
        except Exception:
            for rel in paths:
                destination = self.original / rel
                if destination.exists() or destination.is_symlink():
                    destination.unlink()
                if rel in existed:
                    saved = backup / rel
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if saved.is_symlink():
                        destination.symlink_to(os.readlink(saved))
                    else:
                        shutil.copy2(saved, destination)
            raise
        return changes

    def close(self, delete: bool = True) -> None:
        self.unmount_dependencies()
        if delete:
            shutil.rmtree(self.temp_root, ignore_errors=True)
