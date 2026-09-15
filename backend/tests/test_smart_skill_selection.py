import pytest
import os
import tempfile
from app.services.skill_manager import SkillManager
from app.services.agent_runner import AgentRunner
from app.services.state_store import StateStore
from app.models.schemas import AgentState, AgentStatus

@pytest.fixture
def skill_manager():
    return SkillManager()

def test_match_skills_by_trigger_keywords(skill_manager):
    # Prompt with debugging words should match systematic-debugger
    matched = skill_manager.match_skills_for_task(
        role="BackendDev",
        task_prompt="We have a memory leak and unhandled exception crash in the auth loop, please fix this bug"
    )
    assert len(matched) > 0
    names = [s.name for s in matched]
    assert "systematic-debugger" in names

def test_match_skills_by_security_keywords(skill_manager):
    # Prompt with security words should match security-auditor
    matched = skill_manager.match_skills_for_task(
        role="BackendDev",
        task_prompt="Audit the API endpoints for OWASP SQL injection vulnerabilities and secrets"
    )
    assert len(matched) > 0
    names = [s.name for s in matched]
    assert "security-auditor" in names

def test_match_skills_frontend_role_affinity(skill_manager):
    # Frontend prompt should match frontend specialist
    matched = skill_manager.match_skills_for_task(
        role="FrontendDev",
        task_prompt="Build responsive navigation bar and CSS buttons"
    )
    assert len(matched) > 0
    names = [s.name for s in matched]
    assert "frontend-dev" in names

def test_match_skills_project_local_override(skill_manager):
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a custom project-local skill with custom triggers
        custom_skill_dir = os.path.join(tmpdir, ".agents", "skills", "graphql-expert")
        os.makedirs(custom_skill_dir, exist_ok=True)
        with open(os.path.join(custom_skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write("""---
name: graphql-expert
title: GraphQL Schema Expert
description: Specialist in Apollo GraphQL mutations and resolvers
triggers: [graphql, mutation, resolver, schema]
tier: project
---
# GraphQL Playbook
Always write typed mutations and optimize subqueries.
""")
        
        # Test matching with project_path
        matched = skill_manager.match_skills_for_task(
            role="BackendDev",
            task_prompt="Implement the new GraphQL mutation and resolvers for user checkout",
            project_path=tmpdir
        )
        assert len(matched) > 0
        names = [s.name for s in matched]
        assert "graphql-expert" in names
        assert matched[0].tier == "project"

def test_match_skills_fallback_on_generic_prompt(skill_manager):
    # Generic prompt with no triggers should fallback to role domain skill
    matched = skill_manager.match_skills_for_task(
        role="BackendDev",
        task_prompt="Hello, do your standard work today"
    )
    assert len(matched) > 0
    names = [s.name for s in matched]
    assert "backend-dev" in names

@pytest.mark.asyncio
async def test_agent_runner_dynamic_skill_activation():
    manager = SkillManager()
    runner = AgentRunner(use_mock=True, skill_manager=manager)
    
    events = []
    async def callback(ev, data):
        events.append((ev, data))
        
    res = await runner.dispatch_agent_task(
        project_id="test-proj",
        role="BackendDev",
        prompt="Fix the crash and memory leak in the billing queue",
        workspace_path="/tmp",
        event_callback=callback
    )
    assert res["status"] == "SUCCESS"
    assert "active_skills" in res
    assert "systematic-debugger" in res["active_skills"]
    
    # Verify thought delta mentioned the skill
    thought_texts = [d.get("thought", "") for ev, d in events if ev == "AGENT_THOUGHT_DELTA"]
    assert any("Activated Skill Playbook" in t or "Systematic Debugging" in t for t in thought_texts)

@pytest.mark.asyncio
async def test_agent_runner_manual_mode_override():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        store = StateStore(db_path)
        manager = SkillManager()
        runner = AgentRunner(use_mock=True, skill_manager=manager, store=store)
        
        # Equip specific skill in MANUAL mode
        store.set_agent_status(
            project_id="test-proj",
            role="BackendDev",
            status="IDLE",
            skill_mode="MANUAL",
            equipped_skills=["security-auditor"]
        )
        
        # Even if prompt mentions debugging, MANUAL mode should strictly use equipped security-auditor
        res = await runner.dispatch_agent_task(
            project_id="test-proj",
            role="BackendDev",
            prompt="Fix memory leak bug crash",
            workspace_path=tmpdir
        )
        assert res["status"] == "SUCCESS"
        assert res["active_skills"] == ["security-auditor"]
