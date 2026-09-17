from pathlib import Path
import pytest
from app.services.eval_fixtures import CASES, REFERENCE_SALES, prepare_fixture, grade_sales


@pytest.mark.parametrize('case_id', list(CASES))
def test_persisted_state_grader_rejects_seeded_bug_and_accepts_reference(tmp_path, case_id):
    candidate = Path(prepare_fixture(tmp_path / 'workspace'))
    original = candidate.read_text()
    broken = grade_sales(case_id, candidate, tmp_path / 'oracle-broken')
    assert broken['status'] == 'FAILED', broken
    assert candidate.read_text() == original
    candidate.write_text(REFERENCE_SALES)
    correct = grade_sales(case_id, candidate, tmp_path / 'oracle-reference')
    assert correct['status'] == 'PASSED', correct
    assert correct['evidence_kind'] == 'SQLITE_PERSISTED_STATE'
    assert correct['live_api_verified'] is False


@pytest.mark.asyncio
@pytest.mark.parametrize('arm', ['current_pipeline', 'single_coder_with_verification',
                                 'planner_coder_evaluator_with_optional_specialists'])
async def test_comparison_driver_uses_real_grader_with_fake_runtime(tmp_path, arm):
    from app.services.coding_eval import run_trial
    class FixtureRunner:
        async def dispatch_agent_task(self, **kwargs):
            role = kwargs['role']
            if role == 'BackendDev':
                (Path(kwargs['workspace_path']) / 'sales.py').write_text(REFERENCE_SALES)
                text = 'Changed sales.py'
            elif role == 'Architect':
                text = '<execution_plan>{"roles":["BackendDev"],"acceptance_criteria":["Atomic rollback"]}</execution_plan>'
            elif role == 'Reviewer':
                text = '<review_verdict>{"verdict":"APPROVED","findings":[],"owners":[]}</review_verdict>'
            else:
                text = 'Analysis'
            return {'role': role, 'status': 'SUCCESS', 'response': text, 'tokens_used': 0,
                    'usage_source': 'fixture', 'backend_used': 'fixture'}
    result = await run_trial('E05', arm, tmp_path / arm, FixtureRunner())
    assert result['status'] == 'PASSED', result
    assert result['grader']['status'] == 'PASSED'
    assert result['scope_passed'] is True
    assert result['live_api_verified'] is False and result['browser_verified'] is False
    assert result['calls'] <= 8


@pytest.mark.asyncio
async def test_comparison_driver_does_not_treat_runtime_success_as_feature_success(tmp_path):
    from app.services.coding_eval import run_trial
    class NoEditRunner:
        async def dispatch_agent_task(self, **kwargs):
            return {'status': 'SUCCESS', 'response': 'All done', 'tokens_used': 1, 'backend_used': 'fixture'}
    result = await run_trial('E05', 'single_coder_with_verification', tmp_path / 'trial', NoEditRunner(), max_calls=3)
    assert result['status'] == 'FAILED'
    assert result['grader']['status'] == 'FAILED'
    assert result['calls'] == 3
    assert result['successful_runtime_with_failed_acceptance'] is True
    assert result['false_completion'] is False  # Runtime SUCCESS is not a delivery claim.
