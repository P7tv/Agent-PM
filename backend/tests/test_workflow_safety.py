import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import SprintRecord
from app.services.workspace_session import WorkspaceSession


def symlink_or_skip(link, target, target_is_directory=False):
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as error:
        pytest.skip(f"Symlinks are unavailable in this Windows session: {error}")


def checkpoint(tmp_path):
    original = tmp_path / 'original'
    original.mkdir()
    (original / 'app.txt').write_text('initial')
    session = WorkspaceSession(str(original), str(tmp_path / 'runs'), 'first')
    (session.workspace / 'app.txt').write_text('agent edit')
    return original, session


def test_resume_preserves_human_edits_and_reports_conflict(tmp_path):
    original, first = checkpoint(tmp_path)
    first.close(delete=False)
    (original / 'app.txt').write_text('human edit')
    resumed = WorkspaceSession(str(original), reuse_path=str(first.workspace), expected_manifest_hash=first.manifest_hash)
    with pytest.raises(RuntimeError, match='Workspace changed'):
        resumed.commit()
    assert (original / 'app.txt').read_text() == 'human edit'


def test_resume_keeps_new_human_file_and_original_baseline(tmp_path):
    original, first = checkpoint(tmp_path)
    first.close(delete=False)
    (original / 'human.txt').write_text('human addition')
    resumed = WorkspaceSession(str(original), reuse_path=str(first.workspace), expected_manifest_hash=first.manifest_hash)
    assert resumed.changes() == {'added': [], 'modified': ['app.txt'], 'deleted': []}
    resumed.commit()
    assert (original / 'human.txt').read_text() == 'human addition'
    assert (original / 'app.txt').read_text() == 'agent edit'


def test_resume_rejects_missing_or_tampered_manifest(tmp_path):
    original, first = checkpoint(tmp_path)
    manifest = first.temp_root / 'checkpoint.json'
    value = json.loads(manifest.read_text())
    value['original_baseline'] = {}
    manifest.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='initial baseline'):
        WorkspaceSession(str(original), reuse_path=str(first.workspace), expected_manifest_hash=first.manifest_hash)
    manifest.unlink()
    with pytest.raises(ValueError, match='initial baseline'):
        WorkspaceSession(str(original), reuse_path=str(first.workspace))


def test_resume_rejects_different_project(tmp_path):
    original, first = checkpoint(tmp_path)
    other = tmp_path / 'other'
    other.mkdir()
    with pytest.raises(ValueError, match='different project'):
        WorkspaceSession(str(other), reuse_path=str(first.workspace), expected_manifest_hash=first.manifest_hash)


def test_internal_source_link_cannot_write_original_from_staging(tmp_path):
    original = tmp_path / 'original'
    original.mkdir()
    (original / 'real.txt').write_text('original')
    symlink_or_skip(original / 'alias.txt', original / 'real.txt')
    session = WorkspaceSession(str(original), str(tmp_path / 'runs'), 'links')
    (session.workspace / 'alias.txt').write_text('staged edit')
    assert (original / 'real.txt').read_text() == 'original'
    session.commit()
    assert (original / 'real.txt').read_text() == 'staged edit'


def test_delivery_rejects_parent_link_added_while_paused(tmp_path):
    original, first = checkpoint(tmp_path)
    (first.workspace / 'new').mkdir()
    (first.workspace / 'new' / 'feature.txt').write_text('agent file')
    outside = tmp_path / 'outside'
    outside.mkdir()
    symlink_or_skip(original / 'new', outside, target_is_directory=True)
    resumed = WorkspaceSession(str(original), reuse_path=str(first.workspace), expected_manifest_hash=first.manifest_hash)
    with pytest.raises(RuntimeError, match='Unsafe delivery path'):
        resumed.commit()
    assert list(outside.iterdir()) == []


def active_sprint(store, tmp_path):
    store.create_project('project', 'Project', str(tmp_path), True)
    store.set_agent_status('project', 'BackendDev', 'WORKING', thought='existing work')
    store.record_sprint(SprintRecord(
        sprint_id='active', project_id='project', directive='Build', status='RUNNING',
        execution_plan={'roles': ['BackendDev'], 'quality_roles': ['QATester', 'Reviewer'], 'checkpoint_stage': 'QA'},
    ))


def test_whisper_is_persistent_inbox_without_dispatch_or_status_change(tmp_path, isolated_db, monkeypatch):
    import app.api.routes as routes
    active_sprint(isolated_db, tmp_path)
    async def forbidden(**kwargs):
        pytest.fail('Whisper must not launch a separate writer')
    monkeypatch.setattr(routes.runner, 'dispatch_agent_task', forbidden)
    response = TestClient(app).post('/api/projects/project/whisper', json={'role': 'BackendDev', 'message': 'Keep data local'})
    assert response.status_code == 200
    assert response.json()['status'] == 'INSTRUCTION_QUEUED'
    messages = isolated_db.get_sprint_instructions('active')
    assert messages[0]['message'] == 'Keep data local'
    assert messages[0]['status'] == 'PENDING'
    assert isolated_db.get_agent_status('project', 'BackendDev').status == 'WORKING'
    assert list(tmp_path.iterdir()) == []
    isolated_db.inherit_sprint_instructions('active', 'resumed')
    copied = isolated_db.get_sprint_instructions('resumed')[0]
    assert copied['parent_id'] == messages[0]['instruction_id']
    isolated_db.mark_sprint_instructions_applied([copied['instruction_id']])
    assert isolated_db.get_sprint_instructions('resumed')[0]['status'] == 'APPLIED'
    assert isolated_db.get_sprint_instructions('active')[0]['status'] == 'PENDING'


def test_whisper_rejects_idle_unscheduled_and_final_delivery(tmp_path, isolated_db):
    active_sprint(isolated_db, tmp_path)
    client = TestClient(app)
    isolated_db.set_agent_status('project', 'DevOps', 'IDLE')
    assert client.post('/api/projects/project/whisper', json={'role': 'DevOps', 'message': 'Deploy'}).status_code == 409
    isolated_db.update_sprint('active', execution_plan={'checkpoint_stage': 'FINAL'})
    assert client.post('/api/projects/project/whisper', json={'role': 'BackendDev', 'message': 'Change'}).status_code == 409
    isolated_db.update_sprint('active', status='FAILED')
    assert client.post('/api/projects/project/whisper', json={'role': 'BackendDev', 'message': 'Change'}).status_code == 409
    assert isolated_db.get_sprint_instructions('active') == []


def test_retry_rejects_legacy_checkpoint_before_enqueuing(tmp_path, isolated_db):
    active_sprint(isolated_db, tmp_path)
    isolated_db.update_sprint('active', status='FAILED', checkpoint_path=str(tmp_path))
    response = TestClient(app).post('/api/projects/project/sprints/active/retry', json={'stage': 'QA'})
    assert response.status_code == 409
    assert 'Legacy checkpoint' in response.json()['detail']
    assert isolated_db.get_queue('project') == []


@pytest.mark.asyncio
async def test_mid_task_instruction_applied_in_staging_and_done_tasks_survive_stop(tmp_path, isolated_db, monkeypatch):
    from app.services.agent_runner import AgentRunner
    from app.services.orchestrator import Orchestrator
    from app.services.project_manager import ProjectManager

    isolated_db.create_project('project', 'Project', str(tmp_path), True)
    runner = AgentRunner(use_mock=False)
    orchestrator = Orchestrator(isolated_db, ProjectManager(isolated_db), runner)
    calls = []
    async def dispatch(**kwargs):
        role = kwargs['role']
        calls.append((role, kwargs['prompt']))
        if role == 'Architect':
            text = '<execution_plan>{"roles":["BackendDev"],"acceptance_criteria":["Works"]}</execution_plan>'
        elif role == 'BackendDev':
            target = Path(kwargs['workspace_path']) / 'app.py'
            if not target.exists():
                target.write_text('initial agent edit')
                active = next(s for s in isolated_db.get_sprints('project') if s.status == 'RUNNING')
                isolated_db.add_sprint_instruction('project', active.sprint_id, role, 'Use Thai labels')
            else:
                assert 'Use Thai labels' in kwargs['prompt']
                target.write_text('updated per instruction')
            text = 'Changed app.py'
        elif role == 'QATester':
            orchestrator.abort_pipeline('project')
            text = 'Stopping after implementation'
        else:
            text = 'Plan'
        return {'status': 'SUCCESS', 'response': text, 'backend_used': 'test', 'tokens_used': 0}
    monkeypatch.setattr(runner, 'dispatch_agent_task', dispatch)
    result = await orchestrator.execute_pm_directive('project', 'Build an API')
    assert result['status'] == 'ABORTED'
    sprint = isolated_db.get_sprints('project')[0]
    assert isolated_db.get_sprint_instructions(sprint.sprint_id)[0]['status'] == 'APPLIED'
    task = next(t for t in isolated_db.get_sprint_tasks(sprint.sprint_id) if t.assigned_to == 'BackendDev')
    assert task.status == 'DONE'
    assert not (tmp_path / 'app.py').exists()
    assert (Path(sprint.checkpoint_path) / 'app.py').read_text() == 'updated per instruction'


@pytest.mark.asyncio
@pytest.mark.parametrize('late_instruction,check_kind,expected_error', [
    (True, 'test', 'instructions remain pending'),
    (False, 'build', 'No successful test command'),
    (False, 'test', None),
])
async def test_delivery_gate_and_verification_scope(tmp_path, isolated_db, monkeypatch, late_instruction, check_kind, expected_error):
    from app.services.agent_runner import AgentRunner
    from app.services.orchestrator import Orchestrator
    from app.services.project_manager import ProjectManager
    import app.services.orchestrator as module

    isolated_db.create_project('project', 'Project', str(tmp_path), True)
    runner = AgentRunner(use_mock=False)
    orchestrator = Orchestrator(isolated_db, ProjectManager(isolated_db), runner)
    async def dispatch(**kwargs):
        role = kwargs['role']
        if role == 'Architect':
            text = '<execution_plan>{"roles":["BackendDev"],"acceptance_criteria":["Works"]}</execution_plan>'
        elif role == 'BackendDev':
            (Path(kwargs['workspace_path']) / 'app.py').write_text('feature = True')
            text = 'Changed app.py'
        elif role == 'Reviewer':
            if late_instruction:
                active = next(s for s in isolated_db.get_sprints('project') if s.status == 'RUNNING')
                isolated_db.add_sprint_instruction('project', active.sprint_id, 'BackendDev', 'Extra constraint')
            text = '<review_verdict>{"verdict":"APPROVED","findings":[],"owners":[]}</review_verdict>'
        else:
            text = 'Analysis'
        return {'status': 'SUCCESS', 'response': text, 'backend_used': 'test', 'tokens_used': 0}
    async def verify(workspace, trusted_config=None):
        return {'status': 'PASSED', 'exit_code': 0, 'command': 'fixture', 'stdout': '', 'stderr': '',
                'checks': [{'name': 'fixture', 'kind': check_kind, 'status': 'PASSED', 'exit_code': 0}]}
    monkeypatch.setattr(runner, 'dispatch_agent_task', dispatch)
    monkeypatch.setattr(module, 'verify_workspace', verify)
    result = await orchestrator.execute_pm_directive('project', 'Build an API')
    sprint = isolated_db.get_sprints('project')[0]
    if expected_error:
        assert result['status'] == 'FAILED'
        assert expected_error in result['error']
        assert not (tmp_path / 'app.py').exists()
        assert next(t for t in isolated_db.get_sprint_tasks(sprint.sprint_id) if t.assigned_to == 'BackendDev').status == 'DONE'
    else:
        assert result['status'] == 'COMPLETED'
        assert (tmp_path / 'app.py').exists()
        assert sprint.verification_report['readiness'] == 'AUTOMATED_CHECKS_ONLY'
        assert sprint.verification_report['acceptance_coverage'][0]['status'] == 'NOT_INDEPENDENTLY_VERIFIED'
        assert 'ยังไม่ใช่หลักฐาน' in sprint.release_summary
