"""Executable local regression evaluation; never invokes paid AI runtimes.

Run: PYTHONPATH=backend python -m app.services.workflow_eval --output /tmp/eval.json
This measures harness conformance, not model intelligence or novice usability.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='/tmp/agent-pm-workflow-eval.json')
    parser.add_argument('--require-roadmap-coverage', action='store_true')
    options = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    design = json.loads((root / 'docs/research/agent-workflow-eval-cases.json').read_text())
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='agentpm-eval-') as temporary:
        junit = Path(temporary) / 'results.xml'
        env = {**os.environ, 'PYTHONPATH': str(root / 'backend'), 'PYTHONDONTWRITEBYTECODE': '1',
               'PM_STATE_DB': str(Path(temporary) / 'isolated.db')}
        result = subprocess.run([sys.executable, '-m', 'pytest',
            'backend/tests/test_workflow_safety.py', 'backend/tests/test_durable_workflow.py',
            'backend/tests/test_execution_reliability.py', 'backend/tests/test_cli_print_result.py',
            'backend/tests/test_prompt_system.py', 'backend/tests/test_pipeline_features.py',
            'backend/tests/test_behavioral_eval_fixtures.py',
            'backend/tests/test_host_file_writer.py',
            '-q', f'--junitxml={junit}'], cwd=root, env=env, timeout=300,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        tests = []
        if junit.exists():
            for item in ET.parse(junit).iter('testcase'):
                status = 'FAILED' if item.find('failure') is not None or item.find('error') is not None else 'SKIPPED' if item.find('skipped') is not None else 'PASSED'
                tests.append({'name': item.get('name'), 'status': status, 'seconds': float(item.get('time', 0))})
    # Only narrower deterministic harness assertions are linked here. They do
    # not turn the original natural-language/model benchmark into a PASS.
    links = {'E05': 'test_persisted_state_grader_rejects_seeded_bug_and_accepts_reference[E05]',
             'E06': 'test_persisted_state_grader_rejects_seeded_bug_and_accepts_reference[E06]',
             'E08': 'test_persisted_state_grader_rejects_seeded_bug_and_accepts_reference[E08]',
             'E23': 'test_feature_tasks_execute_dependencies_and_gate_outside_edits',
             'E09': 'test_delivery_gate_and_verification_scope',
             'E12': 'test_acceptance_cannot_pass_with_stale_or_failing_evidence',
             'E13': 'test_pause_during_implementation_resumes_files_and_skips_completed_writer',
             'E14': 'test_resume_preserves_human_edits_and_reports_conflict',
             'E15': 'test_resume_keeps_new_human_file_and_original_baseline',
             'E16': 'test_resume_deduplicates_pending_checkpoint',
             'E17': 'test_restart_closes_orphaned_runtime_state',
             'E18': 'test_mid_task_instruction_applied_in_staging_and_done_tasks_survive_stop',
             'E19': 'test_context_excerpts_are_visible_but_contracts_and_criteria_remain_intact',
             'E20': 'test_missing_runtime_never_claims_success',
             'E21': 'test_planning_retry_is_bounded_and_disables_slash_expansion',
             'E26': 'test_journal_survives_reopen_orders_replay_and_scopes_projects'}
    cases = []
    for case in design['cases']:
        evidence = [test for test in tests if case['id'] in links and test['name'].startswith(links[case['id']])]
        cases.append({'id': case['id'], 'priority': case['priority'], 'benchmark_status': 'NOT_RUN',
                      'harness_regression_status': ('PASSED' if all(test['status'] == 'PASSED' for test in evidence) else 'FAILED') if evidence else 'NOT_RUN',
                      'evidence': evidence})
    report = {'schema_version': 1, 'kind': 'LOCAL_HARNESS_REGRESSION',
              'model_benchmark_status': 'NOT_RUN', 'live_provider_calls': 0,
              'source_note': 'Local deterministic fixtures. No comparison-arm or model intelligence claim.',
              'seconds': time.monotonic() - started, 'pytest_exit_code': result.returncode,
              'tests': tests, 'cases': cases, 'log_tail': result.stdout[-5000:]}
    destination = Path(options.output).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"{sum(test['status'] == 'PASSED' for test in tests)}/{len(tests)} local regressions passed; report: {destination}")
    if result.returncode:
        return 1
    if options.require_roadmap_coverage and any(case['benchmark_status'] != 'PASSED' for case in cases):
        print('Roadmap benchmark coverage remains incomplete; release gate is blocked.')
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
