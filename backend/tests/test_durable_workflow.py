import asyncio
import json
import sys
from pathlib import Path

import pytest

from app.services.acceptance_evidence import acceptance_ledger, source_revision
from app.services.event_journal import EventJournal
from app.services.process_runner import run_process
from app.services.runtime_events import AntigravityStream


@pytest.mark.asyncio
async def test_stream_reports_tool_before_process_finishes_and_bounds_both_pipes(tmp_path):
    observed = asyncio.Event()
    lines = []
    async def line(value):
        lines.append(value)
        observed.set()
    process = asyncio.create_task(run_process([sys.executable, '-u', '-c',
        "import sys,time; print('tool started',flush=True); time.sleep(.3); "
        "sys.stderr.write('x'*200000); print('done')"], str(tmp_path), stdout_line=line,
        max_output_bytes=1024))
    await asyncio.wait_for(observed.wait(), 2)
    assert not process.done()
    result = await process
    assert result['exit_code'] == 0
    assert len(result['stderr']) == 1024
    assert lines == ['tool started', 'done']


@pytest.mark.asyncio
async def test_provider_stream_requires_final_result_and_hides_raw_tool_data():
    events = []
    async def emit(kind, data):
        events.append((kind, data))
    stream = AntigravityStream(emit)
    await stream.feed(json.dumps({'event': 'step_update', 'step_update': {
        'conversation_id': 'exact-session', 'step_type': 'tool', 'state': 'ACTIVE',
        'tool_info': {'name': 'write_file', 'parameters': {'api_key': 'sensitive'}, 'output': 'private'}}}))
    assert stream.conversation_id == 'exact-session'
    assert 'sensitive' not in json.dumps(events) and 'private' not in json.dumps(events)
    incomplete = stream.final_result({'stdout': 'partial stream', 'stderr': '', 'exit_code': 0})
    assert json.loads(incomplete['stdout'])['status'] == 'ERROR'
    await stream.feed(json.dumps({'event': 'result', 'result': {'status': 'SUCCESS', 'response': 'Done'}}))
    assert json.loads(stream.final_result(incomplete)['stdout'])['response'] == 'Done'


def test_journal_survives_reopen_orders_replay_and_scopes_projects(tmp_path):
    journal = EventJournal(str(tmp_path / 'events.db'))
    first = journal.append('START', {'project_id': 'a', 'api_key': 'sensitive'})
    second = journal.append('TOOL', {'project_id': 'b'})
    third = journal.append('DONE', {'project_id': 'a', 'message': 'Bearer private-token'})
    reopened = EventJournal(journal.db_path)
    replay = reopened.replay(first['sequence'], 'a')
    assert [event['sequence'] for event in replay] == [third['sequence']]
    assert reopened.replay(first['sequence'])[0]['sequence'] == second['sequence']
    assert 'sensitive' not in json.dumps(reopened.replay())
    assert 'private-token' not in json.dumps(replay)


@pytest.mark.parametrize('revision,unchanged,check_status,expected', [
    ('current', True, 'PASSED', 'VERIFIED_BY_CHECK'),
    ('old', True, 'PASSED', 'STALE_EVIDENCE'),
    ('current', False, 'PASSED', 'STALE_EVIDENCE'),
    ('current', True, 'FAILED', 'FAILED'),
    ('current', True, 'NOT_RUN', 'FAILED'),
])
def test_acceptance_cannot_pass_with_stale_or_failing_evidence(revision, unchanged, check_status, expected):
    config = {'verification': {'acceptance': [{'description': 'Rollback keeps data atomic', 'checks': ['fault injection']}]}}
    report = {'source_revision': revision, 'source_unchanged': unchanged,
              'checks': [{'name': 'fault injection', 'status': check_status,
                          'exit_code': 0 if check_status == 'PASSED' else 1, 'command': 'test atomicity'}]}
    assert acceptance_ledger(['Rollback keeps data atomic'], report, config, 'current')[0]['status'] == expected
    assert acceptance_ledger(['Unmapped behavior'], report, config, 'current')[0]['status'] == 'NOT_INDEPENDENTLY_VERIFIED'


@pytest.mark.asyncio
async def test_pause_during_implementation_resumes_files_and_skips_completed_writer(tmp_path, isolated_db, monkeypatch):
    from app.services.agent_runner import AgentRunner
    from app.services.orchestrator import Orchestrator
    from app.services.project_manager import ProjectManager
    import app.services.orchestrator as module
    isolated_db.create_project('p', 'Project', str(tmp_path), True)
    runner = AgentRunner(use_mock=False)
    orchestrator = Orchestrator(isolated_db, ProjectManager(isolated_db), runner)
    calls = []
    pause_once = True
    async def dispatch(**kwargs):
        nonlocal pause_once
        role = kwargs['role']
        calls.append(role)
        if role == 'Architect':
            response = '<execution_plan>{"roles":["BackendDev","FrontendDev"],"acceptance_criteria":["Works"]}</execution_plan>'
        elif role == 'BackendDev':
            (Path(kwargs['workspace_path']) / 'api.py').write_text('ready = True')
            response = 'Changed api.py'
            if pause_once:
                pause_once = False
                orchestrator.pause_pipeline('p')
        elif role == 'FrontendDev':
            assert (Path(kwargs['workspace_path']) / 'api.py').exists()
            (Path(kwargs['workspace_path']) / 'ui.js').write_text('export const ready = true;')
            response = 'Changed ui.js'
        elif role == 'Reviewer':
            response = '<review_verdict>{"verdict":"APPROVED","findings":[],"owners":[]}</review_verdict>'
        else:
            response = 'Analysis'
        return {'status': 'SUCCESS', 'response': response, 'backend_used': 'fixture', 'tokens_used': 0}
    async def verify(workspace, trusted_config=None):
        return {'status': 'PASSED', 'exit_code': 0, 'command': 'fixture', 'stdout': '', 'stderr': '',
                'source_revision': source_revision(workspace), 'source_unchanged': True,
                'checks': [{'name': 'fixture', 'kind': 'test', 'status': 'PASSED', 'exit_code': 0}]}
    monkeypatch.setattr(runner, 'dispatch_agent_task', dispatch)
    monkeypatch.setattr(module, 'verify_workspace', verify)
    paused = await orchestrator.execute_pm_directive('p', 'Build frontend and backend')
    assert paused['status'] == 'PAUSED'
    source = isolated_db.get_sprint(paused['sprint_id'])
    assert source.execution_plan['checkpoint_stage'] == 'IMPLEMENTATION'
    assert not (tmp_path / 'api.py').exists()
    assert next(task for task in isolated_db.get_sprint_tasks(source.sprint_id) if task.assigned_to == 'BackendDev').status == 'DONE'
    resumed = await orchestrator.execute_pm_directive('p', source.directive, source_sprint_id=source.sprint_id, resume_from='IMPLEMENTATION')
    assert resumed['status'] == 'COMPLETED'
    assert calls.count('BackendDev') == 1
    assert calls.count('FrontendDev') == 1
    assert (tmp_path / 'api.py').exists() and (tmp_path / 'ui.js').exists()


def test_source_changed_after_checks_cannot_be_delivered(tmp_path):
    from app.services.workspace_session import WorkspaceSession
    original = tmp_path / 'original'
    original.mkdir()
    (original / 'app.py').write_text('original')
    session = WorkspaceSession(str(original))
    try:
        (session.workspace / 'app.py').write_text('checked')
        checked = source_revision(session.workspace)
        (session.workspace / 'app.py').write_text('unchecked')
        with pytest.raises(RuntimeError, match='after verification'):
            session.commit(checked)
        assert (original / 'app.py').read_text() == 'original'
    finally:
        session.close()


def test_brief_preserves_user_request_and_questions_are_explicit():
    from app.services.product_brief import build_product_brief
    brief = build_product_brief('ทำ local prototype', '<product_brief>{"outcome":"บันทึกบิลได้",'
                               '"constraints":["ใช้ local"],"questions":[{"question":"ข้อมูลอะไร?","blocking":true}]}</product_brief>', ['บันทึกได้'])
    assert brief['request'] == 'ทำ local prototype'
    assert brief['constraints'] == ['ใช้ local']
    assert brief['questions'][0]['status'] == 'OPEN'
    assert brief['requirements'][0]['verification_status'] == 'NOT_RUN'
    assert build_product_brief('ทำ local prototype', 'Not structured', ['บันทึกได้'])['outcome'] == 'ทำ local prototype'


def test_blocking_user_question_cannot_be_approved_without_answer(tmp_path, isolated_db):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.models.schemas import SprintRecord
    isolated_db.create_project('p', 'Project', str(tmp_path), True)
    isolated_db.record_sprint(SprintRecord(project_id='p', directive='Build', execution_plan={
        'product_brief': {'questions': [{'question': 'Which data?', 'blocking': True, 'status': 'OPEN'}]}}))
    approval = isolated_db.create_approval_request('p', 'PLAN_APPROVAL', 'Question')
    client = TestClient(app)
    rejected = client.post(f'/api/projects/p/approvals/{approval.request_id}', json={'decision': 'APPROVED'})
    assert rejected.status_code == 409
    assert isolated_db.get_pending_approvals('p')
    accepted = client.post(f'/api/projects/p/approvals/{approval.request_id}', json={'decision': 'APPROVED', 'feedback': 'Use sample data'})
    assert accepted.status_code == 200


@pytest.mark.asyncio
async def test_explicit_cli_resume_uses_exact_id_and_requests_sandbox(monkeypatch, tmp_path):
    from app.services.agent_runner import AgentRunner
    import app.services.agent_runner as module
    calls = []
    async def fake_process(args, workspace, timeout, progress, stdout_line):
        calls.append(args)
        await stdout_line(json.dumps({'event': 'result', 'result': {'status': 'SUCCESS', 'response': 'Reconciled', 'conversation_id': 'exact-id'}}))
        return {'stdout': '', 'stderr': '', 'exit_code': 0}
    monkeypatch.setattr(module, 'run_process', fake_process)
    result = await AgentRunner()._run_cli('Reconcile partial files', str(tmp_path), conversation_id='exact-id')
    assert result.conversation_id == 'exact-id'
    assert calls[0][calls[0].index('--conversation') + 1] == 'exact-id'
    assert '--continue' not in calls[0]
    assert '--sandbox' in calls[0] and '--dangerously-skip-permissions' not in calls[0]


@pytest.mark.parametrize('mutation', ['cycle', 'escape', 'missing_ac', 'duplicate'])
def test_feature_graph_rejects_invalid_dependencies_ownership_and_coverage(mutation):
    from app.services.feature_scheduler import parse_feature_tasks
    tasks = [{'id': 'api', 'title': 'Save a bill', 'role': 'BackendDev', 'owned_paths': ['api.py'],
              'depends_on': [], 'requirements': ['AC-1']}]
    if mutation == 'cycle': tasks[0]['depends_on'] = ['api']
    if mutation == 'escape': tasks[0]['owned_paths'] = ['../private.py']
    if mutation == 'missing_ac': tasks[0]['requirements'] = ['AC-2']
    if mutation == 'duplicate': tasks.append(dict(tasks[0]))
    with pytest.raises(ValueError):
        parse_feature_tasks('', ['BackendDev'], ['Saves bill'], tasks)


@pytest.mark.asyncio
@pytest.mark.parametrize('violate_ownership', [False, True])
async def test_feature_tasks_execute_dependencies_and_gate_outside_edits(tmp_path, isolated_db, monkeypatch, violate_ownership):
    from app.services.agent_runner import AgentRunner
    from app.services.orchestrator import Orchestrator
    from app.services.project_manager import ProjectManager
    import app.services.orchestrator as module
    (tmp_path / '.agent-pm.yml').write_text('workflow:\n  feature_tasks: true\n')
    isolated_db.create_project('p', 'Project', str(tmp_path), True)
    runner = AgentRunner(use_mock=False)
    orchestrator = Orchestrator(isolated_db, ProjectManager(isolated_db), runner)
    features = [{'id': 'api', 'title': 'Save bill', 'role': 'BackendDev', 'owned_paths': ['api.py'],
                 'depends_on': [], 'requirements': ['AC-1']},
                {'id': 'ui', 'title': 'Show saved bill', 'role': 'FrontendDev', 'owned_paths': ['ui.js'],
                 'depends_on': ['api'], 'requirements': ['AC-1']}]
    sequence = []
    async def dispatch(**kwargs):
        role = kwargs['role']
        if role == 'Architect':
            response = '<execution_plan>{"roles":["BackendDev","FrontendDev"],"acceptance_criteria":["Works"]}</execution_plan>' + '<feature_tasks>' + json.dumps(features) + '</feature_tasks>'
        elif role == 'BackendDev':
            sequence.append('api')
            (Path(kwargs['workspace_path']) / ('unowned.py' if violate_ownership else 'api.py')).write_text('ready = True')
            response = 'Changed implementation'
        elif role == 'FrontendDev':
            assert (Path(kwargs['workspace_path']) / 'api.py').exists()
            sequence.append('ui')
            (Path(kwargs['workspace_path']) / 'ui.js').write_text('export const ready = true;')
            response = 'Changed UI'
        elif role == 'Reviewer':
            response = '<review_verdict>{"verdict":"APPROVED","findings":[],"owners":[]}</review_verdict>'
        else:
            response = 'Analysis'
        return {'status': 'SUCCESS', 'response': response, 'backend_used': 'fixture', 'tokens_used': 0}
    async def verify(workspace, trusted_config=None):
        return {'status': 'PASSED', 'exit_code': 0, 'command': 'fixture', 'stdout': '', 'stderr': '',
                'source_revision': source_revision(workspace), 'source_unchanged': True,
                'checks': [{'name': 'fixture', 'kind': 'test', 'status': 'PASSED', 'exit_code': 0}]}
    monkeypatch.setattr(runner, 'dispatch_agent_task', dispatch)
    monkeypatch.setattr(module, 'verify_workspace', verify)
    result = await orchestrator.execute_pm_directive('p', 'Build app')
    sprint = isolated_db.get_sprint(result['sprint_id'])
    if violate_ownership:
        assert result['status'] == 'FAILED'
        assert sprint.execution_plan['ownership_violation']['paths'] == ['unowned.py']
        assert not (tmp_path / 'unowned.py').exists()
    else:
        assert result['status'] == 'COMPLETED'
        assert sequence == ['api', 'ui']
        tasks = isolated_db.get_sprint_tasks(sprint.sprint_id)
        assert {task.title for task in tasks} >= {'Save bill', 'Show saved bill'}
        graph = sprint.execution_plan['task_graph']
        assert graph[1]['depends_on'] == [graph[0]['id']]


@pytest.mark.asyncio
async def test_staged_config_cannot_replace_host_verification_command(tmp_path):
    from app.services.verification import verify_workspace
    (tmp_path / '.agent-pm.yml').write_text('verification:\n  checks:\n    - name: trusted\n      command: ["' + sys.executable + '", "-c", "print(\\\"pretend pass\\\")"]\n')
    trusted = {'verification': {'checks': [{'name': 'trusted', 'command': [sys.executable, '-c', 'raise SystemExit(7)']}]}}
    result = await verify_workspace(str(tmp_path), trusted_config=trusted)
    assert result['status'] == 'FAILED'
    assert result['exit_code'] == 7


def test_context_assembler_retains_contract_and_required_criteria():
    from app.services.context_assembler import assemble_task_context
    contract = '<api_contract>{"path":"/orders","atomic":true}</api_contract>'
    prose = 'supporting context ' * 4000 + contract
    criteria = 'Failure must roll back stock and bill'
    prompt, context = assemble_task_context('User task\n' + prose + '\n' + criteria,
                                           {'architect_plan': prose, 'acceptance_criteria': criteria})
    assert len(prompt) < 5000
    assert contract in prompt and criteria in prompt
    assert context['acceptance_criteria'] == criteria
    assert 'truncated' in prompt


def test_checkpoint_preview_uses_staged_workspace_and_preserves_original(tmp_path, isolated_db):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.models.schemas import SprintRecord
    from app.services.workspace_session import WorkspaceSession
    from app.api import routes
    original = tmp_path / 'original'
    original.mkdir()
    (original / 'app.py').write_text('original')
    preview_command = json.dumps([sys.executable, '-c', 'import time; time.sleep(30)'])
    (original / '.agent-pm.yml').write_text(
        f'preview:\n  command: {preview_command}\n  url: http://127.0.0.1:9999\n',
        encoding='utf-8',
    )
    isolated_db.create_project('p', 'Project', str(original), True)
    session = WorkspaceSession(str(original), str(Path(isolated_db.db_path).parent / '.agentpm-runs'), 'paused')
    (session.workspace / 'app.py').write_text('partial')
    isolated_db.record_sprint(SprintRecord(sprint_id='paused', project_id='p', directive='Build', status='PAUSED',
        checkpoint_path=str(session.workspace), execution_plan={'checkpoint_manifest_hash': session.manifest_hash}))
    client = TestClient(app)
    # The test fixture replaces StateStore but routes.db_path must use the same
    # managed checkpoint root for this explicitly isolated API test.
    previous_path = routes.db_path
    routes.db_path = isolated_db.db_path
    try:
        started = client.post('/api/projects/p/preview?sprint_id=paused')
        assert started.status_code == 200, started.text
        assert started.json()['scope'] == 'CHECKPOINT'
        assert started.json()['workspace'] == str(session.workspace)
        assert client.get('/api/projects/p/preview').json()['sprint_id'] == 'paused'
        assert (original / 'app.py').read_text() == 'original'
    finally:
        client.delete('/api/projects/p/preview')
        routes.db_path = previous_path
        session.close()


def test_concurrent_resume_enqueues_share_one_active_queue_item(tmp_path, isolated_db):
    from concurrent.futures import ThreadPoolExecutor
    isolated_db.create_project('p', 'Project', str(tmp_path), True)
    def enqueue():
        return isolated_db.enqueue_directive('p', 'Continue', source_sprint_id='paused')
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: enqueue(), range(2)))
    assert results[0].queue_id == results[1].queue_id
    assert len(isolated_db.get_queue('p')) == 1
    assert isolated_db.claim_queue_item(results[0].queue_id)
    assert enqueue().queue_id == results[0].queue_id


@pytest.mark.asyncio
async def test_resume_enqueued_during_pause_broadcast_is_not_stranded(tmp_path, isolated_db):
    from app.services.sprint_queue import SprintQueue
    isolated_db.create_project('p', 'Project', str(tmp_path), True)
    completed = asyncio.Event()
    calls = []
    class FakeOrchestrator:
        async def execute_pm_directive(self, **kwargs):
            calls.append(kwargs['source_sprint_id'])
            if not kwargs['source_sprint_id']:
                return {'status': 'PAUSED', 'sprint_id': 'paused'}
            completed.set()
            return {'status': 'COMPLETED', 'sprint_id': 'resumed'}
    async def broadcast(kind, data):
        if kind == 'QUEUE_ITEM_FINISHED' and data['status'] == 'PAUSED':
            queue.enqueue('p', 'Continue', priority='URGENT', source_sprint_id='paused')
    queue = SprintQueue(isolated_db, FakeOrchestrator(), broadcast)
    queue.enqueue('p', 'Start')
    await asyncio.wait_for(completed.wait(), 2)
    worker = queue._workers.get('p')
    if worker:
        await worker
    assert calls == [None, 'paused']
    assert not isolated_db.get_all_queue_items()


@pytest.mark.asyncio
async def test_model_effort_variant_uses_matching_default_and_rejects_explicit_conflict(tmp_path, monkeypatch):
    from app.services.agent_runner import AgentRunner
    import app.services.agent_runner as module
    calls = []
    async def fake_process(args, workspace, timeout, progress, stdout_line):
        calls.append(args)
        await stdout_line(json.dumps({'event': 'result', 'result': {'status': 'SUCCESS', 'response': 'Ready'}}))
        return {'exit_code': 0, 'stdout': '', 'stderr': ''}
    monkeypatch.setenv('AGENT_MODEL', 'gemini-3.8-flash-medium')
    monkeypatch.delenv('AGENT_EFFORT', raising=False)
    monkeypatch.setattr(module, 'run_process', fake_process)
    assert await AgentRunner()._run_cli('Implement', str(tmp_path)) == 'Ready'
    assert calls[0][calls[0].index('--effort') + 1] == 'medium'
    requested_prompt = calls[0][calls[0].index('-p') + 1]
    assert 'direct file editing tools' in requested_prompt
    assert 'The host runs configured checks' in requested_prompt
    monkeypatch.setenv('AGENT_EFFORT', 'high')
    with pytest.raises(ValueError, match='conflicts'):
        await AgentRunner()._run_cli('Implement', str(tmp_path))
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_permission_failure_preserves_session_and_names_blocked_tool(tmp_path, monkeypatch):
    from app.services.agent_runner import AgentRunner, CLIExecutionError
    import app.services.agent_runner as module
    async def denied(args, workspace, timeout, progress, stdout_line):
        await stdout_line(json.dumps({'event': 'step_update', 'step_update': {
            'conversation_id': 'exact-failed-session', 'step_index': 2,
            'step_type': 'tool', 'tool_name': 'run_command', 'state': 'ERROR'}}))
        await stdout_line(json.dumps({'event': 'result', 'result': {
            'status': 'ERROR', 'error': 'permission denied'}}))
        return {'exit_code': 1, 'stdout': '', 'stderr': ''}
    monkeypatch.setattr(module, 'run_process', denied)
    monkeypatch.delenv('AGENT_MODEL', raising=False)
    monkeypatch.delenv('AGENT_EFFORT', raising=False)
    with pytest.raises(CLIExecutionError, match='run_command') as failure:
        await AgentRunner()._run_cli('Implement', str(tmp_path))
    assert failure.value.code == 'PERMISSION_REQUIRED'
    assert failure.value.conversation_id == 'exact-failed-session'


@pytest.mark.asyncio
async def test_concurrent_preview_starts_create_only_one_process(tmp_path, isolated_db, monkeypatch):
    import sys
    from app.api import routes
    isolated_db.create_project('p', 'Project', str(tmp_path), True)
    (tmp_path / '.agent-pm.yml').write_text(json.dumps({'preview': {
        'command': [sys.executable, '-c', 'import time; time.sleep(10)'],
        'url': 'http://127.0.0.1:5173'}}))
    launches = []
    actual_popen = routes.subprocess.Popen
    def track(*args, **kwargs):
        process = actual_popen(*args, **kwargs)
        launches.append(process)
        return process
    monkeypatch.setattr(routes.subprocess, 'Popen', track)
    try:
        results = await asyncio.gather(routes.start_preview('p'), routes.start_preview('p'))
        assert all(result['running'] for result in results)
        assert len(launches) == 1
    finally:
        await routes._stop_preview('p')
    assert launches[0].poll() is not None
    assert 'p' not in routes.preview_processes
