import asyncio
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.services.agent_runner import AgentRunner
from app.services.console_service import ConsoleService
from app.services.orchestrator import Orchestrator
from app.services.project_manager import ProjectManager
from app.services.state_store import StateStore
from app.services.process_runner import run_process
from app.services.verification import verify_workspace, detect_test_command
from app.services.workspace_inspector import WorkspaceInspector
from app.services.pipeline_contracts import build_execution_plan, parse_reviewer_verdict
from app.services.workspace_session import WorkspaceSession


@pytest.mark.asyncio
async def test_missing_runtime_never_claims_success(monkeypatch, tmp_path):
    import app.services.agent_runner as module
    monkeypatch.setattr(module, 'HAS_AGY_CLI', False)
    monkeypatch.setattr(module, 'HAS_ANTIGRAVITY', False)
    runner = AgentRunner()
    events = []
    async def emit(kind, data):
        events.append(kind)
    result = await runner.dispatch_agent_task('p', 'Architect', 'Build', str(tmp_path), event_callback=emit)
    chat = await runner.dispatch_chat_task('p', 'TechLead', 'Hello', str(tmp_path))
    assert result['status'] == chat['status'] == 'FAILED'
    assert result['backend_used'] == 'unavailable'
    assert 'AGENT_ERROR' in events
    assert not chat['code_proposals']


@pytest.mark.asyncio
async def test_cli_failure_exposes_stderr(monkeypatch, tmp_path):
    import app.services.agent_runner as module
    monkeypatch.setattr(module, 'HAS_AGY_CLI', True)
    monkeypatch.setattr(module, 'AGY_PATH', sys.executable)
    runner = AgentRunner()
    runner.has_api_key = False
    async def fake_process(*args, **kwargs):
        return {'exit_code': 7, 'stdout': '', 'stderr': 'Login expired; authenticate again'}
    monkeypatch.setattr(module, 'run_process', fake_process)
    result = await runner.dispatch_agent_task('p', 'Architect', 'Build', str(tmp_path))
    assert result['status'] == 'FAILED'
    assert result['error_code'] == 'AUTH_REQUIRED'
    assert 'เข้าสู่ระบบ' in result['error']


@pytest.mark.asyncio
async def test_cli_does_not_overwrite_files_from_summary(monkeypatch, tmp_path):
    import app.services.agent_runner as module
    monkeypatch.setattr(module, 'HAS_AGY_CLI', True)
    monkeypatch.setattr(module, 'AGY_PATH', sys.executable)
    runner = AgentRunner()
    runner.has_api_key = False
    async def fake_cli(*args, **kwargs):
        (tmp_path / 'app.py').write_text('actual implementation')
        return '```filename: app.py\ntruncated summary\n```'
    monkeypatch.setattr(runner, '_run_cli', fake_cli)
    result = await runner.dispatch_agent_task('p', 'BackendDev', 'Build', str(tmp_path))
    assert result['status'] == 'SUCCESS'
    assert (tmp_path / 'app.py').read_text() == 'actual implementation'


@pytest.mark.asyncio
async def test_proposals_reject_sibling_prefix_and_symlink(monkeypatch, tmp_path):
    workspace = tmp_path / 'app'
    sibling = tmp_path / 'app-other'
    workspace.mkdir()
    sibling.mkdir()
    (workspace / 'linked').symlink_to(sibling, target_is_directory=True)
    runner = AgentRunner()
    async def emit(*args):
        pass
    for path in ('../app-other/out.py', 'linked/out.py', '.git/config'):
        with pytest.raises(ValueError):
            await runner._write_proposals(f'```filename: good.py\ngood\n```\n```filename: {path}\nbad\n```', str(workspace), emit)
        assert not (workspace / 'good.py').exists()
        assert not (sibling / 'out.py').exists()


@pytest.mark.asyncio
async def test_process_timeout_kills_worker(tmp_path):
    pid_file = tmp_path / 'pid'
    command = [sys.executable, '-c', f'import os,time; open({str(pid_file)!r}, "w").write(str(os.getpid())); time.sleep(30)']
    with pytest.raises(TimeoutError):
        await run_process(command, str(tmp_path), timeout=0.3)
    pid = int(pid_file.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


@pytest.mark.asyncio
async def test_verification_uses_real_exit_codes(tmp_path):
    (tmp_path / 'requirements.txt').write_text('pytest')
    test_file = tmp_path / 'test_example.py'
    test_file.write_text('def test_failure():\n    assert False\n')
    result = await verify_workspace(str(tmp_path))
    assert result['status'] == 'FAILED'
    assert result['exit_code'] != 0
    assert 'assert False' in result['stdout']
    test_file.write_text('def test_ok():\n    assert 2 + 2 == 4\n')
    assert (await verify_workspace(str(tmp_path)))['status'] == 'PASSED'


@pytest.mark.asyncio
async def test_missing_tests_are_not_a_pass(tmp_path):
    assert (await verify_workspace(str(tmp_path)))['status'] == 'NOT_RUN'
    (tmp_path / 'package.json').write_text('{"scripts":{"build":"vite build"}}')
    assert detect_test_command(str(tmp_path)) is None


def setup_orchestrator(store, tmp_path, auto=True):
    pm = ProjectManager(store)
    pm.register_project('reliable', 'Reliable', str(tmp_path), auto_pilot=auto)
    runner = AgentRunner(use_mock=True)
    return Orchestrator(store, pm, runner), runner


@pytest.mark.asyncio
async def test_failed_agent_halts_downstream_and_persists_reason(isolated_db, tmp_path):
    orch, runner = setup_orchestrator(isolated_db, tmp_path)
    calls = []
    async def fail(**kwargs):
        calls.append(kwargs['role'])
        return {'status': 'FAILED', 'response': 'Provider unavailable'}
    runner.dispatch_agent_task = fail
    result = await orch.execute_pm_directive('reliable', 'Build')
    assert result['status'] == 'FAILED'
    assert calls == ['TechLead']
    assert isolated_db.get_sprints('reliable')[0].status == 'FAILED'
    assert any('Provider unavailable' in m['content'] for m in isolated_db.get_console_messages('reliable'))
    assert isolated_db.get_agent_status('reliable', 'TechLead').status == 'BLOCKED'
    assert isolated_db.get_agent_status('reliable', 'BackendDev').status == 'IDLE'
    assert isolated_db.get_agent_status('reliable', 'QATester').status == 'IDLE'


@pytest.mark.asyncio
async def test_fast_approval_not_lost_and_chat_survives_reload(isolated_db, tmp_path):
    orch, runner = setup_orchestrator(isolated_db, tmp_path, auto=False)
    async def emit(kind, data):
        if kind == 'DECISION_GATE_OPEN':
            orch.resolve_gate(data['request_id'], 'APPROVED')
    result = await asyncio.wait_for(orch.execute_pm_directive('reliable', 'Build', emit), timeout=10)
    assert result['status'] == 'COMPLETED'
    assert not isolated_db.get_pending_approvals('reliable')
    history = ConsoleService(isolated_db).get_history('reliable')
    assert any('Task Decomposition' in msg['content'] for msg in history)
    assert any('UI Implementation' in msg['content'] for msg in history)


@pytest.mark.asyncio
async def test_gate_timeout_is_rejection(isolated_db, tmp_path):
    orch, _ = setup_orchestrator(isolated_db, tmp_path)
    approval = isolated_db.create_approval_request('reliable', 'PLAN_APPROVAL', 'Plan')
    assert await orch._wait_for_approval(approval.request_id, timeout=0.01) == 'REJECTED'
    assert not isolated_db.get_pending_approvals('reliable')


@pytest.mark.asyncio
async def test_abort_cancels_running_agent_without_poisoning_next_sprint(isolated_db, tmp_path):
    orch, runner = setup_orchestrator(isolated_db, tmp_path)
    started = asyncio.Event()
    cancelled = asyncio.Event()
    original = runner.dispatch_agent_task
    async def slow(**kwargs):
        started.set()
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.set()
    runner.dispatch_agent_task = slow
    job = asyncio.create_task(orch.execute_pm_directive('reliable', 'Slow task'))
    await started.wait()
    orch.abort_pipeline('reliable')
    result = await asyncio.wait_for(job, 2)
    assert result['status'] == 'ABORTED'
    assert cancelled.is_set()
    orch.abort_pipeline('reliable')  # stopping an idle project must be harmless
    runner.dispatch_agent_task = original
    assert (await orch.execute_pm_directive('reliable', 'Next task'))['status'] == 'COMPLETED'


def test_console_context_includes_prior_session_after_new_message(isolated_db):
    old = ConsoleService(isolated_db)
    old.add_message('p', 'user', 'Use SQLite')
    new = ConsoleService(isolated_db)
    new.add_message('p', 'user', 'Continue')
    assert 'Use SQLite' in new.get_recent_context('p')
    assert len(isolated_db.get_console_messages('p', limit=1)) == 1
    assert isolated_db.get_console_messages('p', limit=0) == []


def test_blank_directive_and_invalid_gate_decision_are_rejected(isolated_db, tmp_path):
    from app.main import app
    client = TestClient(app)
    assert client.post('/api/projects/p/directive', json={'directive': '  '}).status_code == 422
    assert client.post('/api/projects/p/approvals/a', json={'decision': 'MAYBE'}).status_code == 422
    approval = isolated_db.create_approval_request('owner', 'PLAN_APPROVAL', 'Plan')
    assert client.post(f'/api/projects/other/approvals/{approval.request_id}', json={'decision': 'APPROVED'}).status_code == 404
    assert isolated_db.get_pending_approvals('owner')


def test_runtime_api_returns_unavailable_without_mock_fallback(monkeypatch):
    from app.api import routes
    from app.main import app
    import app.services.agent_runner as module
    monkeypatch.setattr(module, 'HAS_AGY_CLI', False)
    monkeypatch.setattr(module, 'HAS_ANTIGRAVITY', False)
    monkeypatch.setattr(routes, 'runner', AgentRunner())
    result = TestClient(app).get('/api/runtime').json()
    assert result['mode'] == 'unavailable'
    assert not result['available']


def test_dashboard_security_headers_are_restrictive():
    from app.main import app
    response = TestClient(app).get('/')
    assert response.status_code == 200
    policy = response.headers['content-security-policy']
    assert "default-src 'self'" in policy
    assert "'unsafe-eval'" not in policy
    assert response.headers['x-content-type-options'] == 'nosniff'


def test_temporary_workspace_allowed_and_system_symlink_rejected(tmp_path):
    inspector = WorkspaceInspector()
    assert inspector.validate_guardrails(str(tmp_path))[0]
    link = tmp_path / 'system-link'
    link.symlink_to('/dev', target_is_directory=True)
    assert not inspector.validate_guardrails(str(link))[0]


def test_restart_closes_orphaned_runtime_state(tmp_path):
    from app.models.schemas import SprintRecord
    from app.services.state_store import StateStore
    db_path = str(tmp_path / 'restart.db')
    store = StateStore(db_path)
    store.create_project('p', 'Project', str(tmp_path), True)
    store.record_sprint(SprintRecord(sprint_id='old', project_id='p', directive='Build'))
    task = store.create_task('p', 'Work', 'BackendDev', sprint_id='old')
    store.update_task_status(task.task_id, 'IN_PROGRESS')
    store.create_approval_request('p', 'PLAN_APPROVAL', 'Old plan')

    recovered = StateStore(db_path)
    sprint = recovered.get_sprint('old')
    assert sprint.status == 'INTERRUPTED'
    assert 'restarted' in sprint.release_summary.lower()
    recovered_task = next(item for item in recovered.get_tasks('p') if item.task_id == task.task_id)
    assert recovered_task.status == 'INTERRUPTED'
    assert recovered.get_pending_approvals('p') == []


def test_execution_plan_selects_scope_and_reviewer_fails_closed():
    frontend = build_execution_plan('Fix checkout button CSS', '', {'stack_type': 'React'}, [])
    assert frontend['roles'] == ['Designer', 'FrontendDev']
    backend = build_execution_plan('Repair API database migration', '', {'stack_type': 'Python'}, [])
    assert backend['roles'] == ['BackendDev']
    docs = build_execution_plan('Update README documentation', '', {}, [])
    assert docs['roles'] == ['DocWriter']
    specialists = [
        SimpleNamespace(role='Security', thought='Specialized for Python security', title='', skill_title='', skill_name='security'),
        SimpleNamespace(role='ThreeJsSpecialist', thought='Three.js WebGL rendering and shaders', title='', skill_title='', skill_name='ui-styling'),
    ]
    api_plan = build_execution_plan('Repair backend API', '', {'stack_type': 'Python'}, specialists)
    assert api_plan['roles'] == ['BackendDev']
    game_plan = build_execution_plan('Build multiplayer vehicle lobby', '', {}, specialists)
    assert 'ThreeJsSpecialist' in game_plan['roles']
    assert 'Security' not in game_plan['roles']
    echoed = (
        '<execution_plan>{"roles":["ROLE"],"acceptance_criteria":["example"]}</execution_plan>\n'
        '<execution_plan>{"roles":["BackendDev"],"acceptance_criteria":["API returns 200"]}</execution_plan>'
    )
    assert build_execution_plan('Repair API', echoed, {}, [])['acceptance_criteria'] == ['API returns 200']
    invalid = build_execution_plan(
        'Repair API', '<execution_plan>{"roles":["ROLE"],"acceptance_criteria":["example"]}</execution_plan>', {}, []
    )
    assert invalid['acceptance_criteria'][0].startswith('The requested behavior')
    assert parse_reviewer_verdict('Looks good')['verdict'] == 'BLOCKED'
    verdict = parse_reviewer_verdict(
        '<review_verdict>{"verdict":"CHANGES_REQUESTED","findings":["api.py:12"],"owners":["BackendDev"]}</review_verdict>'
    )
    assert verdict['verdict'] == 'CHANGES_REQUESTED'
    assert verdict['owners'] == ['BackendDev']


def test_workspace_session_commits_or_discards_as_one_unit(tmp_path):
    original = tmp_path / 'project'
    original.mkdir()
    (original / 'app.py').write_text('before')
    staged = WorkspaceSession(str(original))
    (staged.workspace / 'app.py').write_text('after')
    (staged.workspace / 'new.py').write_text('new')
    assert (original / 'app.py').read_text() == 'before'
    changes = staged.commit()
    staged.close()
    assert changes == {'added': ['new.py'], 'modified': ['app.py'], 'deleted': []}
    assert (original / 'app.py').read_text() == 'after'
    assert (original / 'new.py').read_text() == 'new'

    discarded = WorkspaceSession(str(original))
    (discarded.workspace / 'app.py').write_text('partial failure')
    discarded.close()
    assert (original / 'app.py').read_text() == 'after'


def test_workspace_dependencies_are_mounted_only_for_verification(tmp_path):
    original = tmp_path / 'project'
    dependency = original / 'node_modules' / 'tool'
    dependency.mkdir(parents=True)
    (dependency / 'index.js').write_text('dependency')
    session = WorkspaceSession(str(original))
    mounted = session.workspace / 'node_modules'
    assert not mounted.exists()
    session.mount_dependencies()
    assert mounted.is_symlink()
    session.unmount_dependencies()
    assert not mounted.exists()
    session.close()


@pytest.mark.asyncio
async def test_reviewer_block_discards_staged_agent_changes(tmp_path):
    store = StateStore(str(tmp_path / 'state.db'))
    pm = ProjectManager(store)
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    (workspace / 'requirements.txt').write_text('pytest')
    (workspace / 'test_ok.py').write_text('def test_ok():\n    assert True\n')
    pm.register_project('gate', 'Gate', str(workspace), auto_pilot=True)
    runner = AgentRunner(use_mock=False)

    async def fake_dispatch(**kwargs):
        role = kwargs['role']
        if role == 'BackendDev':
            Path(kwargs['workspace_path'], 'feature.py').write_text('partial = True\n')
        if role == 'Reviewer':
            response = '<review_verdict>{"verdict":"BLOCKED","findings":["feature.py lacks acceptance behavior"],"owners":["BackendDev"]}</review_verdict>'
        else:
            response = 'completed'
        return {'status': 'SUCCESS', 'role': role, 'response': response, 'tokens_used': 1, 'backend_used': 'test'}

    runner.dispatch_agent_task = fake_dispatch
    result = await Orchestrator(store, pm, runner).execute_pm_directive('gate', 'Repair backend API')
    assert result['status'] == 'FAILED'
    assert 'Reviewer BLOCKED' in result['error']
    assert not (workspace / 'feature.py').exists()


@pytest.mark.asyncio
async def test_qa_and_designer_are_read_only_cli_roles(monkeypatch, tmp_path):
    import app.services.agent_runner as module
    monkeypatch.setattr(module, 'HAS_AGY_CLI', True)
    monkeypatch.setattr(module, 'AGY_PATH', sys.executable)
    runner = AgentRunner()
    runner.has_api_key = False
    seen = []

    async def fake_cli(query, workspace, emit, chat=False):
        seen.append(chat)
        return 'inspection complete'

    monkeypatch.setattr(runner, '_run_cli', fake_cli)
    await runner.dispatch_agent_task('p', 'Designer', 'Design', str(tmp_path))
    await runner.dispatch_agent_task('p', 'QATester', 'Verify', str(tmp_path))
    assert seen == [True, True]


@pytest.mark.asyncio
async def test_documentation_only_sprint_can_pass_without_test_suite(tmp_path):
    store = StateStore(str(tmp_path / 'state.db'))
    pm = ProjectManager(store)
    workspace = tmp_path / 'docs'
    workspace.mkdir()
    (workspace / 'README.md').write_text('old\n')
    pm.register_project('docs', 'Docs', str(workspace), auto_pilot=True)
    runner = AgentRunner(use_mock=False)

    async def fake_dispatch(**kwargs):
        role = kwargs['role']
        if role == 'DocWriter':
            Path(kwargs['workspace_path'], 'README.md').write_text('updated\n')
        response = (
            '<review_verdict>{"verdict":"APPROVED","findings":[],"owners":[]}</review_verdict>'
            if role == 'Reviewer' else 'completed'
        )
        return {'status': 'SUCCESS', 'role': role, 'response': response, 'tokens_used': 1, 'backend_used': 'test'}

    runner.dispatch_agent_task = fake_dispatch
    result = await Orchestrator(store, pm, runner).execute_pm_directive('docs', 'Update README documentation')
    assert result['status'] == 'COMPLETED'
    assert result['selected_roles'] == ['DocWriter', 'QATester', 'Reviewer']
    assert (workspace / 'README.md').read_text() == 'updated\n'


@pytest.mark.asyncio
async def test_reviewer_changes_requested_gets_one_repair_pass(tmp_path):
    store = StateStore(str(tmp_path / 'state.db'))
    pm = ProjectManager(store)
    workspace = tmp_path / 'review-repair'
    workspace.mkdir()
    (workspace / 'requirements.txt').write_text('pytest')
    (workspace / 'test_ok.py').write_text('def test_ok():\n    assert True\n')
    pm.register_project('repair', 'Repair', str(workspace), auto_pilot=True)
    runner = AgentRunner(use_mock=False)
    reviews = 0

    async def fake_dispatch(**kwargs):
        nonlocal reviews
        role = kwargs['role']
        prompt = kwargs['prompt']
        if role == 'BackendDev':
            value = 'fixed = True\n' if 'Reviewer Findings' in prompt else 'fixed = False\n'
            Path(kwargs['workspace_path'], 'feature.py').write_text(value)
        if role == 'Reviewer':
            reviews += 1
            verdict = 'CHANGES_REQUESTED' if reviews == 1 else 'APPROVED'
            response = (
                f'<review_verdict>{{"verdict":"{verdict}","findings":["feature.py needs fixed=True"],'
                '"owners":["BackendDev"]}</review_verdict>'
            )
        else:
            response = 'completed'
        return {'status': 'SUCCESS', 'role': role, 'response': response, 'tokens_used': 1, 'backend_used': 'test'}

    runner.dispatch_agent_task = fake_dispatch
    result = await Orchestrator(store, pm, runner).execute_pm_directive('repair', 'Repair backend API')
    assert result['status'] == 'COMPLETED'
    assert reviews == 2
    assert (workspace / 'feature.py').read_text() == 'fixed = True\n'
