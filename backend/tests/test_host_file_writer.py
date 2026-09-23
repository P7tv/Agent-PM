import json
import os
import pytest
from app.services.host_file_writer import apply_file_proposals
from app.services.workspace_session import snapshot_workspace


def symlink_or_skip(link, target):
    try:
        link.symlink_to(target)
    except OSError as error:
        pytest.skip(f"Symlinks are unavailable in this Windows session: {error}")


def test_batch_validation_prevents_partial_write_and_rejects_changed_baseline(tmp_path):
    target = tmp_path / 'app.py'
    target.write_text('original')
    baseline = snapshot_workspace(tmp_path)
    invalid = {'files': [{'path': 'app.py', 'content': 'replacement'},
                         {'path': '../escaped.py', 'content': 'bad'}]}
    with pytest.raises(ValueError, match='Unsafe'):
        apply_file_proposals(json.dumps(invalid), tmp_path, baseline)
    assert target.read_text() == 'original'
    target.write_text('human edit')
    with pytest.raises(ValueError, match='Workspace changed'):
        apply_file_proposals(json.dumps({'files': invalid['files'][:1]}), tmp_path, baseline)
    assert target.read_text() == 'human edit'


@pytest.mark.asyncio
async def test_default_cli_host_writer_saves_proposals_and_reports_paths(tmp_path, monkeypatch):
    from app.services.agent_runner import AgentRunner, CLIResponse
    import app.services.agent_runner as module
    (tmp_path / 'sales.py').write_text('old')
    monkeypatch.delenv('AGENT_CLI_FILE_MODE', raising=False)
    monkeypatch.setenv('AGENT_RUNTIME', 'cli')
    monkeypatch.setattr(module, 'HAS_AGY_CLI', True)
    monkeypatch.setattr(module, 'AGY_PATH', __file__)
    async def proposals(self, prompt, workspace, emit=None, **kwargs):
        assert kwargs['chat'] is True
        assert 'Do not call any tools' in prompt and 'old' in prompt
        await emit('RUNTIME_STEP', {'step_type': 'agent_response', 'message': 'RAW_FILE_CONTENT'})
        return CLIResponse(json.dumps({'files': [{'path': 'sales.py', 'content': 'new'}],
                                       'summary': 'Updated sales; checks unrun',
                                       'handoff': {'summary': 'Updated sales', 'changed_files': ['invented.py'],
                                           'contracts': {'checkout': {'result': 'sale_id'}},
                                           'checks': [], 'risks': ['Browser NOT_RUN'], 'next_owner': 'QATester'}}), 100)
    monkeypatch.setattr(AgentRunner, '_run_cli', proposals)
    events = []
    async def record(event, data):
        events.append((event, data))
    result = await AgentRunner().dispatch_agent_task('p', 'BackendDev', 'Fix sales.py', str(tmp_path), event_callback=record)
    assert result['status'] == 'SUCCESS', result
    assert (tmp_path / 'sales.py').read_text() == 'new'
    assert 'Files: sales.py' in result['response'] and '"content"' not in result['response']
    assert result['tokens_used'] == 100 and result['usage_source'] == 'provider'
    from app.services.prompt_builder import handoff_text
    handoff = json.loads(handoff_text(result))
    assert handoff['contracts']['checkout']['result'] == 'sale_id'
    assert handoff['changed_files'] == ['sales.py']
    assert 'agent-reported' in handoff['checks_provenance']
    assert 'RAW_FILE_CONTENT' not in json.dumps(events)
    assert any(event == 'TOOL_EXECUTION_FINISH' and data['tool'] == 'host_write_file' for event, data in events)


@pytest.mark.asyncio
async def test_invalid_host_proposal_fails_without_writing_and_retains_session(tmp_path, monkeypatch):
    from app.services.agent_runner import AgentRunner, CLIResponse
    import app.services.agent_runner as module
    (tmp_path / 'app.py').write_text('original')
    monkeypatch.setenv('AGENT_CLI_FILE_MODE', 'host-proposals')
    monkeypatch.setenv('AGENT_RUNTIME', 'cli')
    monkeypatch.setattr(module, 'HAS_AGY_CLI', True)
    monkeypatch.setattr(module, 'AGY_PATH', __file__)
    async def unsafe(self, *args, **kwargs):
        response = CLIResponse(json.dumps({'files': [
            {'path': 'app.py', 'content': 'new'}, {'path': '../escaped.py', 'content': 'bad'}]}), 100)
        response.conversation_id = 'proposal-session'
        response.reported_model = 'fixture-model'
        return response
    monkeypatch.setattr(AgentRunner, '_run_cli', unsafe)
    result = await AgentRunner().dispatch_agent_task('p', 'BackendDev', 'Fix app.py', str(tmp_path))
    assert result['status'] == 'FAILED' and result['error_code'] == 'HOST_PROPOSAL_INVALID'
    assert result['conversation_id'] == 'proposal-session'
    assert result['reported_model'] == 'fixture-model'
    assert result['tokens_used'] == 100 and result['usage_source'] == 'provider'
    assert (tmp_path / 'app.py').read_text() == 'original'


def test_context_omits_sensitive_paths_and_cannot_replace_unobserved_file(tmp_path):
    from app.services.host_file_writer import proposal_context
    (tmp_path / 'sales.py').write_text('source')
    (tmp_path / '.env').write_text('PRIVATE_VALUE=must-not-send')
    (tmp_path / 'credentials.json').write_text('must-not-send')
    (tmp_path / 'large.py').write_text('x' * 1000)
    baseline = snapshot_workspace(tmp_path)
    context, observed = proposal_context(tmp_path, baseline, 'sales.py', max_chars=300)
    assert 'must-not-send' not in context and observed == {'sales.py'}
    with pytest.raises(ValueError, match='omitted'):
        apply_file_proposals(json.dumps({'files': [{'path': 'large.py', 'content': 'replacement'}]}),
                             tmp_path, baseline, observed)


def test_host_writer_applies_files_and_preserves_existing_executable_mode(tmp_path):
    target = tmp_path / 'script.py'
    target.write_text('old')
    target.chmod(0o755)
    paths = apply_file_proposals(json.dumps({'files': [
        {'path': 'script.py', 'content': 'new'}, {'path': 'nested/new.py', 'content': 'created'}]}),
        tmp_path, snapshot_workspace(tmp_path))
    assert paths == ['script.py', 'nested/new.py']
    assert target.read_text() == 'new'
    if os.name != 'nt':
        assert target.stat().st_mode & 0o777 == 0o755
    assert (tmp_path / 'nested/new.py').read_text() == 'created'


def test_host_writer_rejects_internal_symlink_and_duplicate_targets(tmp_path):
    target = tmp_path / 'app.py'
    target.write_text('original')
    symlink_or_skip(tmp_path / 'alias.py', target)
    for paths in [('alias.py',), ('app.py', './app.py')]:
        with pytest.raises(ValueError):
            apply_file_proposals(json.dumps({'files': [{'path': path, 'content': 'new'} for path in paths]}),
                                 tmp_path, snapshot_workspace(tmp_path))
    assert target.read_text() == 'original'
