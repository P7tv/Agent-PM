"""Opt-in model coding benchmark over calibrated SQLite fixtures.

No AI is called without --live. Candidate workspaces and databases are disposable;
no registered user project is used. Each arm gets the same call/time ceilings.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import time

from app.services.eval_fixtures import CASES, prepare_fixture
from app.services.process_runner import run_process
from app.services.workspace_session import snapshot_workspace, changed_paths, flatten_changes
from app.services.pipeline_contracts import parse_reviewer_verdict


ARMS = ('current_pipeline', 'single_coder_with_verification',
        'planner_coder_evaluator_with_optional_specialists')


async def run_trial(case_id, arm, directory, runner, max_calls=8, timeout=120, token_budget=120000):
    from app.services import eval_fixtures
    from app.services.state_store import StateStore
    from app.services.project_manager import ProjectManager
    from app.services.orchestrator import Orchestrator
    root = Path(directory)
    workspace = root / 'candidate'
    candidate = prepare_fixture(workspace)
    oracle = root / 'oracle'
    command = [sys.executable, '-B', str(Path(eval_fixtures.__file__).resolve()), '--case', case_id,
               '--candidate', 'sales.py', '--oracle-dir', str(oracle)]
    config = {'verification': {'checks': [{'name': case_id, 'kind': 'test', 'command': command,
                                         'timeout_seconds': 30}]},
              'protected_paths': ['README.md', '.agent-pm.yml']}
    # JSON is valid YAML. The host owns this command and snapshots it before work.
    (workspace / '.agent-pm.yml').write_text(json.dumps(config))
    before = snapshot_workspace(workspace)
    started = time.monotonic()
    attempts = []
    grade = {'status': 'NOT_RUN'}
    runtime_status = 'NOT_RUN'
    error = None

    async def bounded_dispatch(**kwargs):
        if len(attempts) >= max_calls or sum(item.get('tokens_used') or 0 for item in attempts) >= token_budget:
            raise RuntimeError('Call or token budget exhausted')
        attempt = {'role': kwargs['role'], 'status': 'RUNNING'}
        attempts.append(attempt)
        previous_callback = kwargs.get('event_callback')
        async def observe(event, data):
            if event == 'RUNTIME_STEP':
                events = attempt.setdefault('runtime_steps', [])
                if len(events) < 200:
                    events.append({key: data.get(key) for key in
                                   ('step_index', 'state', 'step_type', 'tool', 'conversation_id')})
            if previous_callback:
                await previous_callback(event, data)
        kwargs['event_callback'] = observe
        try:
            result = await asyncio.wait_for(runner.dispatch_agent_task(**kwargs), timeout)
        except BaseException:
            attempt['status'] = 'INTERRUPTED'
            raise
        attempt.update({key: result.get(key) for key in
                        ('status', 'tokens_used', 'usage_source', 'backend_used', 'reported_model', 'conversation_id', 'error_code')})
        if result.get('status') != 'SUCCESS':
            raise RuntimeError(result.get('error') or result.get('response') or 'Runtime failed')
        return result

    async def invoke(role, prompt):
        return await bounded_dispatch(project_id='fixture', role=role, prompt=prompt, workspace_path=str(workspace))

    class LimitedRunner:
        use_mock = False
        async def dispatch_agent_task(self, **kwargs):
            return await bounded_dispatch(**kwargs)

    async def inspect_grade():
        source_before = snapshot_workspace(workspace)
        result = await run_process(command, str(workspace), 30)
        try:
            measured = json.loads(result['stdout'].strip())
        except ValueError:
            measured = {'status': 'ERROR', 'error': result['stderr'][-1000:]}
        if result['exit_code'] != 0 and measured.get('status') == 'PASSED':
            measured['status'] = 'ERROR'
        if snapshot_workspace(workspace) != source_before:
            measured = {'status': 'ERROR', 'error': 'Candidate changed source during grading'}
        return measured

    try:
        if arm == 'current_pipeline':
            store = StateStore(str(root / 'state.db'))
            store.create_project('fixture', 'Disposable coding fixture', str(workspace), True)
            result = await Orchestrator(store, ProjectManager(store), LimitedRunner()).execute_pm_directive(
                'fixture', CASES[case_id], acceptance_criteria=[CASES[case_id]],
                protected_paths=config['protected_paths'])
            runtime_status = result['status']
            error = result.get('error')
        else:
            plan = ''
            if arm == ARMS[2]:
                planned = await invoke('Architect', 'Plan the minimal implementation and observable acceptance for: '
                                       + CASES[case_id] + '. Do not edit files. Only sales.py may change.')
                plan = planned.get('response', '')[:2500]
            reserve = 1 if arm == ARMS[2] else 0
            while len(attempts) < max_calls - reserve:
                await invoke('BackendDev', CASES[case_id] + '\nOnly edit sales.py. Preserve the documented signature/schema. '
                             'Inspect existing files. Use standard library only.\nPlan excerpt: ' + plan +
                             '\nActual previous grader outcome: ' + json.dumps(grade, ensure_ascii=False)[:2500])
                grade = await inspect_grade()
                if grade.get('status') == 'PASSED':
                    break
            runtime_status = 'SUCCESS'
            if arm == ARMS[2] and grade.get('status') == 'PASSED':
                evaluated = await invoke('Reviewer', 'Inspect sales.py read-only for: ' + CASES[case_id] +
                    '\nMeasured SQLite grader: ' + json.dumps(grade, ensure_ascii=False)[:2500] +
                    '\nReturn <review_verdict>{"verdict":"APPROVED or BLOCKED","findings":[],"owners":[]}</review_verdict>. '
                    'Do not claim live APIs or browser verification.')
                if parse_reviewer_verdict(evaluated.get('response', ''))['verdict'] != 'APPROVED':
                    runtime_status = 'REJECTED'
    except Exception as exception:
        runtime_status = 'FAILED'
        error = f'{type(exception).__name__}: {exception}'
    # Inspect persisted candidate state even after a provider failure. A partial
    # repair is evidence about files, never a successful runtime/delivery claim.
    try:
        grade = await inspect_grade()
    except Exception as exception:
        grade = {'status': 'ERROR', 'error': f'{type(exception).__name__}: {exception}'}
    changes = flatten_changes(changed_paths(before, snapshot_workspace(workspace)))
    scope_passed = all(path == 'sales.py' for path in changes)
    passed = runtime_status in {'SUCCESS', 'COMPLETED'} and grade.get('status') == 'PASSED' and scope_passed
    return {'case_id': case_id, 'arm': arm, 'status': 'PASSED' if passed else 'FAILED',
            'runtime_status': runtime_status, 'grader': grade, 'scope_passed': scope_passed,
            'changed_files': changes, 'attempts': attempts, 'calls': len(attempts),
            'seconds': time.monotonic() - started, 'error': error,
            'false_completion': runtime_status == 'COMPLETED' and not passed,
            'successful_runtime_with_failed_acceptance': runtime_status in {'SUCCESS', 'COMPLETED'} and not passed,
            'tokens_reported_or_estimated': sum(attempt.get('tokens_used') or 0 for attempt in attempts),
            'live_api_verified': False, 'browser_verified': False}


async def run_live(options):
    from app.services.agent_runner import AgentRunner, AGY_PATH
    from app.services.runtime_adapter import AntigravityAdapter
    os.environ['AGENT_RUNTIME'] = 'cli'
    os.environ['AGENT_MODEL'] = options.model
    os.environ['AGENT_CLI_FILE_MODE'] = options.file_mode
    os.environ['AGENT_TIMEOUT_SECONDS'] = str(options.timeout)
    os.environ['SPRINT_MAX_AGENT_CALLS'] = str(options.max_calls)
    os.environ['SPRINT_TOKEN_BUDGET'] = str(options.token_budget)
    report = {'kind': 'LIVE_CODING_FIXTURE_BENCHMARK', 'requested_model': options.model,
              'file_mode': options.file_mode,
              'call_count_kind': 'RUNTIME_TASK_INVOCATIONS_NOT_RAW_PROVIDER_REQUESTS',
              'calls_per_trial_ceiling': options.max_calls, 'timeout_per_call': options.timeout,
              'reported_token_stop_threshold_per_trial': options.token_budget, 'trials': [],
              'note': 'Three calibrated coding fixtures; does not cover all 26 roadmap cases or novice usability.'}
    destination = Path(options.output).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    def persist():
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    with tempfile.TemporaryDirectory(prefix='agentpm-coding-benchmark-') as temporary:
        report['runtime_probe'] = await AntigravityAdapter(AGY_PATH).get_capabilities(temporary)
        persist()
        for repeat in range(options.trials):
            for case_id in options.cases:
                for arm in options.arms:
                    result = await run_trial(case_id, arm, Path(temporary) / f'{repeat}-{case_id}-{arm}',
                                             AgentRunner(use_mock=False), options.max_calls, options.timeout, options.token_budget)
                    result['repeat'] = repeat
                    report['trials'].append(result)
                    persist()  # Retain failures even if a later trial is interrupted.
                    print(case_id, arm, result['status'], flush=True)
    print('Report:', destination)
    return 0 if all(trial['status'] == 'PASSED' for trial in report['trials']) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Explicitly enable external AI calls using your CLI credentials/credits')
    parser.add_argument('--model')
    parser.add_argument('--file-mode', choices=['direct', 'host-proposals'], default='direct')
    parser.add_argument('--cases', nargs='+', choices=list(CASES), default=list(CASES))
    parser.add_argument('--arms', nargs='+', choices=ARMS, default=list(ARMS))
    parser.add_argument('--trials', type=int, default=1)
    parser.add_argument('--max-calls', type=int, default=8)
    parser.add_argument('--token-budget', type=int, default=120000)
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('--output', default='/tmp/agentpm-live-coding-eval.json')
    options = parser.parse_args()
    if not options.live:
        print('NOT_RUN. Add --live --model MODEL_ID to explicitly enable external AI calls. No AI request was sent.')
        return 0
    if not options.model or options.trials < 1 or options.max_calls < 3 or options.timeout <= 0 or options.token_budget <= 0:
        parser.error('Live evaluation requires a model, positive trials/timeout/token budget, and at least 3 calls per trial')
    return asyncio.run(run_live(options))


if __name__ == '__main__':
    raise SystemExit(main())
