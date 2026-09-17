"""Apply explicit JSON file proposals only against an unchanged workspace."""
import json
import os
from pathlib import Path
import tempfile

from app.services.workspace_session import snapshot_workspace


def proposal_context(workspace, baseline, prompt, max_chars=18000):
    root = Path(workspace).resolve()
    paths = list(baseline)
    paths = [path for path in paths if not any(part.startswith('.') for part in Path(path).parts)
             and Path(path).suffix.lower() not in {'.pem', '.key', '.p12', '.pfx'}
             and not any(word in Path(path).name.lower() for word in ('credentials', 'secrets', 'token'))]
    paths.sort(key=lambda path: (path not in prompt, path.count('/'), path))
    included = {}
    remaining = max_chars
    for path in paths:
        target = root / path
        if target.is_symlink() or root not in target.resolve().parents or not target.is_file():
            continue
        if target.stat().st_size > remaining:
            continue
        try:
            content = target.read_text(encoding='utf-8')
        except (UnicodeError, OSError):
            continue
        if '\x00' in content or len(content) + len(path) + 80 > remaining:
            continue
        included[path] = content
        remaining -= len(content) + len(path) + 80
    return json.dumps({'available_paths': paths[:200], 'complete_files': included}, ensure_ascii=False), set(included)


def apply_file_proposals(text, workspace, baseline, observed_paths=None):
    root = Path(workspace).resolve()
    payload = json.loads(text)
    files = payload.get('files') if isinstance(payload, dict) else None
    if not isinstance(files, list) or not 1 <= len(files) <= 40:
        raise ValueError('Host proposal must contain 1–40 files')
    if snapshot_workspace(root) != baseline:
        raise ValueError('Workspace changed while proposals were prepared; reconcile before writing')
    validated = []
    seen = set()
    total = 0
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get('path'), str) or not isinstance(item.get('content'), str):
            raise ValueError('Each proposal requires path and full content strings')
        relative = Path(item['path'])
        if relative.is_absolute() or '..' in relative.parts or '.git' in relative.parts or '\\' in item['path']:
            raise ValueError('Unsafe proposal path')
        target = root / relative
        if root not in target.resolve().parents or target in seen:
            raise ValueError('Unsafe or duplicate proposal path')
        if any(parent.is_symlink() for parent in (target, *target.parents) if parent != root):
            raise ValueError('Proposal paths cannot traverse symlinks')
        if target.exists() and not target.is_file():
            raise ValueError('Proposal target must be a regular file')
        if target.exists() and observed_paths is not None and str(relative) not in observed_paths:
            raise ValueError('Cannot replace an existing file omitted from the supplied context')
        encoded = item['content'].encode('utf-8')
        total += len(encoded)
        if total > 2_000_000:
            raise ValueError('Proposal batch exceeds 2 MB')
        seen.add(target)
        validated.append((target, encoded))
    backups = {target: (target.read_bytes(), target.stat().st_mode & 0o777) if target.exists() else None
               for target, _ in validated}
    written = []
    def replace(target, content, mode=None):
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=target.parent, prefix='.agentpm-write-')
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(content)
            os.chmod(temporary, mode if mode is not None else 0o644)
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
    try:
        for target, content in validated:
            backup = backups[target]
            replace(target, content, backup[1] if backup else None)
            written.append(target)
    except Exception:
        for target in reversed(written):
            backup = backups[target]
            if backup is None:
                target.unlink(missing_ok=True)
            else:
                replace(target, *backup)
        raise
    return [str(target.relative_to(root)) for target in written]
