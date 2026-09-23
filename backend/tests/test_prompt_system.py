import json
import sqlite3
import sys

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import AgentState
from app.services.agent_runner import AgentRunner
from app.services.prompt_builder import build_prompt, handoff_text
from app.services.skill_manager import SkillManager
from app.services.state_store import StateStore


@pytest.fixture
def manager(tmp_path):
    return SkillManager(agy_skills_dir=str(tmp_path / 'empty-agy'))


def skill_file(root, name, content):
    path = root / '.agents' / 'skills' / name / 'SKILL.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.mark.parametrize('role', ['SecurityAuditor', 'security-auditor', 'SystematicDebugger', 'systematic-debugger', 'Debugger'])
def test_audit_and_debug_roles_default_to_read_only(tmp_path, manager, role):
    from app.services.prompt_builder import READ_ONLY_MODES
    bundle = build_prompt(manager, role, str(tmp_path), intent='Inspect the reported failure')
    assert bundle.trace['execution_mode'] in READ_ONLY_MODES
    assert 'MODE LIMIT: Inspect and report only' in bundle.system
    assert 'For host-proposals, return one JSON object' in bundle.system
    expected_skill = 'security-auditor' if 'security' in role.lower() else 'systematic-debugger'
    assert f'CORE ROLE PLAYBOOK ({expected_skill.upper()})' in bundle.system


@pytest.mark.asyncio
async def test_persona_survives_progress_and_is_shared_by_chat_and_pipeline(tmp_path, manager, monkeypatch):
    import app.services.agent_runner as module
    store = StateStore(str(tmp_path / 'state.db'))
    store.add_agent('p', 'POSExpert', 'POS Specialist', 'Understand order and stock consistency', skill_tier='agy')
    store.set_agent_status('p', 'POSExpert', 'WORKING', thought='Previous sprint complete')
    runner = AgentRunner(store=store, skill_manager=manager)
    runner.has_api_key = False
    monkeypatch.setattr(module, 'HAS_AGY_CLI', True)
    monkeypatch.setattr(module, 'AGY_PATH', sys.executable)
    prompts = []
    async def fake_cli(prompt, *args, **kwargs):
        prompts.append(prompt)
        return 'Reviewed consistency'
    runner._run_cli = fake_cli
    async def progress(kind, data):
        if kind == 'AGENT_THOUGHT_DELTA':
            store.set_agent_status('p', 'POSExpert', 'THINKING', thought=data['thought'])
    task = await runner.dispatch_agent_task('p', 'POSExpert', 'Inspect order and stock', str(tmp_path), event_callback=progress)
    chat = await runner.dispatch_chat_task('p', 'POSExpert', 'Inspect order and stock', str(tmp_path))
    assert task['status'] == chat['status'] == 'SUCCESS'
    assert all('Stable specialist persona: Understand order and stock consistency' in prompt for prompt in prompts)
    assert 'Previous sprint complete' not in prompts[0]
    assert store.get_agent_status('p', 'POSExpert').persona == 'Understand order and stock consistency'
    assert store.get_agent_status('p', 'POSExpert').skill_tier == 'agy'
    traces = store.list_prompt_traces('p', 'POSExpert')
    assert len(traces) == 2
    assert 'system_prompt' not in json.dumps(traces)
    assert traces[0]['trace']['execution_mode'] == 'consultation'


def test_manual_empty_never_falls_back_to_auto_or_legacy_selection(tmp_path, manager):
    agent = AgentState(project_id='p', role='BackendDev', skill_mode='MANUAL',
                       equipped_skills=[], skill_name='security-auditor')
    bundle = build_prompt(manager, 'BackendDev', str(tmp_path), agent=agent, intent='Fix memory leak bug')
    assert bundle.active_skills == []
    assert bundle.trace['selected_skills'] == []
    assert 'Backend Engineer Playbook' in bundle.system
    greeting = build_prompt(manager, 'BackendDev', str(tmp_path), intent='สวัสดีครับ')
    assert greeting.active_skills == [] and greeting.trace['selected_skills'] == []


def test_manual_missing_and_invalid_skills_are_visible_without_auto_fallback(tmp_path, manager):
    skill_file(tmp_path, 'broken', '---\nname: broken\ntriggers: [17]\n---\nBody')
    agent = AgentState(project_id='p', role='BackendDev', skill_mode='MANUAL', equipped_skills=['missing', 'broken'])
    bundle = build_prompt(manager, 'BackendDev', str(tmp_path), agent=agent, intent='Fix bug')
    assert bundle.active_skills == []
    assert any('missing' in message for message in bundle.trace['warnings'])
    assert any('Invalid skill broken' in message for message in bundle.trace['warnings'])


def test_project_rules_always_apply_and_core_is_not_duplicated(tmp_path, manager):
    path = skill_file(tmp_path, 'backend-dev', '---\nname: backend-dev\ntier: stock\nallowed-tools: [read_file]\n---\nUse project-specific inventory transactions.')
    agent = AgentState(project_id='p', role='BackendDev', skill_mode='MANUAL', equipped_skills=['backend-dev'])
    bundle = build_prompt(manager, 'BackendDev', str(tmp_path), agent=agent)
    assert bundle.system.count('Use project-specific inventory transactions.') == 1
    assert bundle.system.count('# Backend Engineer Playbook') == 1
    assert bundle.active_skills == []
    parsed = manager.get_skill('backend-dev', str(tmp_path), required=True)
    assert parsed.tier == 'project'
    assert parsed.allowed_tools == ['read_file']
    assert str(path) in [source['path'] for source in bundle.trace['sources']]
    path.write_text(manager.get_base_role_skill('BackendDev').raw_content)
    copied = build_prompt(manager, 'BackendDev', str(tmp_path), agent=agent)
    assert copied.system.count('# Backend Engineer Playbook') == 1


@pytest.mark.parametrize('role,expected', [('Designer', 'designer'), ('DocWriter', 'doc-writer'), ('Reviewer', 'reviewer')])
def test_roles_have_their_own_core(manager, role, expected):
    assert manager.get_base_role_skill(role).name == expected


def test_read_only_prompt_uses_analysis_not_implementation(tmp_path, manager):
    bundle = build_prompt(manager, 'QATester', str(tmp_path))
    assert bundle.trace['execution_mode'] == 'verification-analysis'
    assert 'Do not edit files, invoke terminal/RunCommand' in bundle.system
    assert 'The orchestrator executes project checks' in bundle.system
    assert 'Write comprehensive unit' not in bundle.system


def test_project_markdown_and_references_resolve_to_their_actual_sources(tmp_path, manager):
    (tmp_path / 'AGENTS.md').write_text('Use inventory transactions for all order writes.')
    path = skill_file(tmp_path, 'inventory', '---\nname: inventory\n---\nSee [contract](references/contract.md) and [bad](../outside.md).')
    reference = path.parent / 'references' / 'contract.md'
    reference.parent.mkdir()
    reference.write_text('STOCK_CONTRACT: quantity must never be negative.')
    agent = AgentState(project_id='p', role='BackendDev', skill_mode='MANUAL', equipped_skills=['inventory'])
    bundle = build_prompt(manager, 'BackendDev', str(tmp_path), agent=agent)
    assert 'Use inventory transactions for all order writes.' in bundle.system
    assert 'STOCK_CONTRACT' in bundle.system
    assert any('out-of-scope' in warning for warning in bundle.trace['warnings'])
    assert str(reference) in [source['path'] for source in bundle.trace['sources']]


def test_context_excerpts_are_visible_but_contracts_and_criteria_remain_intact(tmp_path, manager):
    contract = json.dumps({'summary': 'Inventory', 'contracts': {'notes': 'x' * 3500, 'stock_field': 'stock_remaining'}})
    bundle = build_prompt(manager, 'FrontendDev', str(tmp_path), context={
        'tech_lead_notes': 'z' * 5000, 'backend_specs': contract,
        'acceptance_criteria': 'ACCEPTANCE_SENTINEL', 'specialist_specs': 'SPECIALIST_SENTINEL',
        'frontend_specs': 'FRONTEND_SENTINEL'})
    assert 'tech_lead_notes' in bundle.trace['truncated_sections']
    assert 'stock_remaining' in bundle.system
    assert 'backend_specs' not in bundle.trace['truncated_sections']
    assert all(marker in bundle.system for marker in ['ACCEPTANCE_SENTINEL', 'SPECIALIST_SENTINEL', 'FRONTEND_SENTINEL'])
    with pytest.raises(ValueError, match='exceeds'):
        build_prompt(manager, 'BackendDev', str(tmp_path), context={'acceptance_criteria': 'x' * 100000})


def test_handoff_contract_uses_verified_files_and_labels_self_reported_checks():
    payload = {'summary': 'Created order endpoint', 'changed_files': ['fake.py'],
               'contracts': {'POST /orders': {'response': {'stock_remaining': 'int'}}},
               'checks': [{'command': 'pytest', 'result': 'PASS'}], 'risks': []}
    result = {'response': 'Report\n<agent_handoff>' + json.dumps(payload) + '</agent_handoff>', 'changed_files': ['orders.py']}
    parsed = json.loads(handoff_text(result))
    assert parsed['verified_changed_files'] == ['orders.py']
    assert 'agent-reported' in parsed['checks_provenance']
    assert parsed['contracts']['POST /orders']['response']['stock_remaining'] == 'int'
    assert handoff_text({'response': '<agent_handoff>[]</agent_handoff>'}) == '<agent_handoff>[]</agent_handoff>'


def test_remove_last_skill_keeps_manual_and_clears_legacy_selection(tmp_path):
    store = StateStore(str(tmp_path / 'state.db'))
    store.set_agent_status('p', 'BackendDev', 'WORKING', skill_name='security-auditor',
                           skill_mode='MANUAL', equipped_skills=['security-auditor'], persona='Stable persona')
    state = store.remove_equipped_skill('p', 'BackendDev', 'security-auditor')
    assert state.skill_mode == 'MANUAL'
    assert state.equipped_skills == [] and state.skill_name is None
    assert state.persona == 'Stable persona' and state.status == 'WORKING'


def test_identity_migration_recovers_only_unchanged_descriptions(tmp_path):
    path = str(tmp_path / 'old.db')
    store = StateStore(path)
    store.add_agent('p', 'Custom', 'Stock Expert', 'Original inventory specialist')
    store.add_agent('p', 'Other', 'Other Expert', 'Previous description')
    store.set_agent_status('p', 'Other', 'DONE', thought='Pipeline complete')
    store.add_agent('p', 'Aborted', 'Aborted Expert', 'Initial expertise')
    store.set_agent_status('p', 'Aborted', 'IDLE', thought='Sprint aborted by PM.')
    with sqlite3.connect(path) as conn:
        for column in ('display_name', 'persona', 'persona_source'):
            conn.execute('ALTER TABLE agent_states DROP COLUMN ' + column)
    migrated = StateStore(path)
    assert migrated.get_agent_status('p', 'Custom').persona == 'Original inventory specialist'
    assert migrated.get_agent_status('p', 'Other').persona == 'Other Expert'
    assert migrated.get_agent_status('p', 'Other').persona_source == 'legacy_title'
    assert migrated.get_agent_status('p', 'Aborted').persona == 'Aborted Expert'
    assert migrated.get_agent_status('p', 'Aborted').persona_source == 'legacy_title'
    migrated.set_agent_status('p', 'Custom', 'WORKING', thought='New progress')
    assert StateStore(path).get_agent_status('p', 'Custom').persona == 'Original inventory specialist'


def test_skill_parser_failure_does_not_crash_discovery_and_thai_triggers_work(tmp_path, manager):
    skill_file(tmp_path, 'broken', '---\nname: broken\ntriggers: [17]\n---\nBody')
    skill_file(tmp_path, 'inventory', '---\nname: inventory\ntriggers: [สต็อก]\n---\nInventory rules')
    names = [skill.name for skill in manager.match_skills_for_task('BackendDev', 'แก้ปัญหาสต็อกติดลบ', str(tmp_path))]
    assert 'inventory' in names and 'broken' not in names
    assert manager.diagnostics
    with pytest.raises(ValueError):
        manager.save_custom_skill(str(tmp_path), '..', 'Body')
    with pytest.raises(ValueError, match='exceed'):
        manager.save_custom_skill(str(tmp_path), 'backend-dev', 'x' * 7000)


def test_auto_loads_library_methodology_for_thai_request_without_equipping(tmp_path, manager):
    skill_file(tmp_path, 'transaction-regression', '---\nname: transaction-regression\ndescription: transaction concurrency verification\ntriggers: [transaction, concurrency]\n---\nTRANSACTION_ROLLBACK_METHOD')
    bundle = build_prompt(manager, 'BackendDev', str(tmp_path), intent='แก้ stock ติดลบเวลาขายพร้อมกัน')
    assert 'transaction-regression' in bundle.trace['operational_skills']
    assert 'TRANSACTION_ROLLBACK_METHOD' in bundle.system
    assert 'backend-dev' not in bundle.trace['operational_skills']
    assert len(bundle.trace['operational_skills']) <= 4


def test_auto_pins_keep_automatic_retrieval_but_manual_remains_exclusive(tmp_path, manager):
    skill_file(tmp_path, 'inventory-check', '---\nname: inventory-check\ntriggers: [concurrency, transaction]\n---\nINVENTORY_CHECK_METHOD')
    auto = AgentState(project_id='p', role='BackendDev', skill_mode='AUTO', equipped_skills=['security-auditor'])
    bundle = build_prompt(manager, 'BackendDev', str(tmp_path), agent=auto, intent='แก้ stock ติดลบเวลาขายพร้อมกัน')
    assert {'security-auditor', 'inventory-check'} <= set(bundle.trace['operational_skills'])
    manual = auto.model_copy(update={'skill_mode': 'MANUAL'})
    bundle = build_prompt(manager, 'BackendDev', str(tmp_path), agent=manual, intent='แก้ stock ติดลบเวลาขายพร้อมกัน')
    assert bundle.trace['operational_skills'] == ['security-auditor']


def test_skill_catalog_includes_current_project_and_rejects_unknown_project(tmp_path, isolated_db):
    isolated_db.create_project('p', 'Project', str(tmp_path), True)
    skill_file(tmp_path, 'local-only', '---\nname: local-only\n---\nLocal methodology')
    client = TestClient(app)
    assert 'local-only' in {s['name'] for s in client.get('/api/skills?project_id=p').json()}
    assert 'local-only' not in {s['name'] for s in client.get('/api/skills').json()}
    assert client.get('/api/skills?project_id=missing').status_code == 404


def test_reregister_preserves_explicit_persona(tmp_path, isolated_db):
    from app.services.project_manager import ProjectManager
    pm = ProjectManager(isolated_db)
    pm.register_project('p', 'Project', str(tmp_path))
    isolated_db.set_agent_status('p', 'TechLead', 'IDLE', persona='User-defined triage methodology', display_name='My Lead', persona_source='explicit')
    pm.register_project('p', 'Project', str(tmp_path))
    state = isolated_db.get_agent_status('p', 'TechLead')
    assert state.persona == 'User-defined triage methodology' and state.display_name == 'My Lead'


def test_trace_retention_does_not_pollute_activity_metrics_and_project_delete_cleans_up(tmp_path):
    store = StateStore(str(tmp_path / 'state.db'))
    for index in range(55):
        store.save_prompt_trace('p', 'Expert', {'sha256': str(index), 'execution_mode': 'planning'})
    traces = store.list_prompt_traces('p', 'Expert', limit=100)
    assert len(traces) == 50 and traces[0]['trace']['sha256'] == '54'
    assert store.list_agent_activities('p') == []
    store.delete_project('p')
    assert store.list_prompt_traces('p', 'Expert') == []


def test_preview_and_identity_api_use_saved_persona_and_validate_skill_metadata(tmp_path, isolated_db):
    import app.api.routes as routes
    # Match production wiring: prompt composition reads the registered agent.
    routes.runner.store = isolated_db
    isolated_db.create_project('p', 'Project', str(tmp_path))
    isolated_db.add_agent('p', 'Expert', 'Expert', 'Original expertise')
    client = TestClient(app)
    response = client.put('/api/projects/p/agents/Expert/identity', json={'display_name': 'Inventory Expert', 'persona': 'Keep stock consistent'})
    assert response.status_code == 200
    preview = client.post('/api/projects/p/agents/Expert/prompt-preview', json={'message': 'Analyze stock', 'mode': 'consultation'})
    assert preview.status_code == 200
    assert 'Stable specialist persona: Keep stock consistent' in preview.json()['system_prompt']
    assert isolated_db.list_prompt_traces('p', 'Expert') == []
    assert client.post('/api/projects/p/agents/Missing/prompt-preview', json={}).status_code == 404
    assert client.put('/api/projects/p/skills/Expert', json={'content': '---\ntriggers: [17]\n---\nBody'}).status_code == 400
    assert client.post('/api/projects/p/agents/Expert/skills/add', json={'skill_name': 'missing'}).status_code == 400
