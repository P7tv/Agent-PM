import json
import sys

import pytest

from app.services.agent_runner import AgentRunner, CLIExecutionError, parse_cli_response


def cli_result(payload, code=0, stderr=''):
    return {'exit_code': code, 'stdout': json.dumps(payload), 'stderr': stderr}


def test_json_result_exposes_response_and_actual_usage():
    text = parse_cli_response(cli_result({
        'status': 'SUCCESS', 'response': 'Plan ready', 'usage': {'total_tokens': 15535},
    }))
    assert text == 'Plan ready'
    assert text.tokens_used == 15535


@pytest.mark.parametrize('payload,expected', [
    ({'status': 'ERROR', 'error': 'Tool confirmation permission denied'}, 'PERMISSION_REQUIRED'),
    ({'status': 'ERROR', 'error': 'You are not logged into Antigravity'}, 'AUTH_REQUIRED'),
    ({'status': 'ERROR', 'error': 'quota resource_exhausted'}, 'RATE_LIMITED'),
    ({'status': 'SUCCESS', 'response': ''}, 'EMPTY_RESPONSE'),
    ({'status': 'SUCCESS', 'response': '   \n'}, 'EMPTY_RESPONSE'),
    ({'status': 'ERROR', 'response': 'Provider failure'}, 'CLI_ERROR'),
])
def test_zero_exit_code_does_not_hide_json_failures(payload, expected):
    with pytest.raises(CLIExecutionError) as error:
        parse_cli_response(cli_result(payload))
    assert error.value.code == expected


def test_nonzero_exit_exposes_provider_stderr():
    with pytest.raises(CLIExecutionError, match='upstream unavailable'):
        parse_cli_response({'exit_code': 7, 'stdout': '', 'stderr': 'upstream unavailable'})


@pytest.mark.asyncio
async def test_planning_retry_is_bounded_and_disables_slash_expansion(monkeypatch, tmp_path):
    import app.services.agent_runner as module
    monkeypatch.setattr(module, 'AGY_PATH', sys.executable)
    calls = []
    events = []
    async def fake_process(args, workspace, timeout, progress, stdout_line=None):
        calls.append(args)
        return cli_result({'status': 'SUCCESS', 'response': '' if len(calls) == 1 else 'Ready'})
    async def emit(kind, data):
        events.append(data.get('message', ''))
    monkeypatch.setattr(module, 'run_process', fake_process)
    assert await AgentRunner()._run_cli('/plan is literal context', str(tmp_path), emit, chat=True) == 'Ready'
    assert len(calls) == 2
    assert all('--disable-slash-commands' in args and '--output-format' in args for args in calls)
    assert all('--dangerously-skip-permissions' not in args for args in calls)
    assert 'Do not call any tools' in calls[1][calls[1].index('-p') + 1]
    assert any('(1/1)' in message for message in events)


@pytest.mark.asyncio
async def test_implementation_empty_result_is_never_replayed(monkeypatch, tmp_path):
    import app.services.agent_runner as module
    monkeypatch.setattr(module, 'AGY_PATH', sys.executable)
    calls = []
    async def fake_process(*args):
        calls.append(args)
        (tmp_path / 'already-edited.txt').write_text('edited')
        return cli_result({'status': 'SUCCESS', 'response': ''})
    monkeypatch.setattr(module, 'run_process', fake_process)
    with pytest.raises(CLIExecutionError):
        await AgentRunner()._run_cli('Implement', str(tmp_path), chat=False)
    assert len(calls) == 1
