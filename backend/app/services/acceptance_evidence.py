"""Bind configured acceptance checks to the source actually checked.

The mapping is captured from the original project before agents run. A passing
command is executable evidence for its configured criterion, not proof that an
agent-authored test is independent or that the app is production ready.
"""
import hashlib
import json
from app.services.workspace_session import snapshot_workspace


def source_revision(workspace):
    manifest = snapshot_workspace(workspace)
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()


def acceptance_ledger(criteria, report, config, revision):
    verification = config.get('verification') or {}
    mappings = verification.get('acceptance') or []
    if not isinstance(mappings, list):
        mappings = []
    checks = {item.get('name'): item for item in report.get('checks', [])}
    coverage = []
    for index, description in enumerate(criteria):
        requirement_id = f'AC-{index + 1}'
        spec = next((item for item in mappings if isinstance(item, dict)
                     and item.get('description') == description), {})
        names = spec.get('checks', [])
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            names = []
        evidence = [checks[name] for name in names if name in checks]
        same_revision = report.get('source_revision') == revision and report.get('source_unchanged') is True
        status = 'NOT_INDEPENDENTLY_VERIFIED'
        if names and same_revision:
            if len(evidence) != len(names):
                status = 'NOT_RUN'
            elif any(item.get('status') != 'PASSED' or item.get('exit_code') != 0 for item in evidence):
                status = 'FAILED'
            else:
                status = 'VERIFIED_BY_CHECK'
        elif names:
            status = 'STALE_EVIDENCE'
        coverage.append({'id': requirement_id, 'description': description, 'status': status,
                         'requirement_revision': hashlib.sha256(description.encode()).hexdigest(),
                         'source_revision': revision, 'checks': names,
                         'evidence': [{'name': item['name'], 'command': item.get('command'),
                                       'exit_code': item.get('exit_code'), 'status': item.get('status')}
                                      for item in evidence]})
    return coverage
