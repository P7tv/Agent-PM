import pytest
from app.services.agent_runner import AgentRunner
from app.services.skill_manager import SkillManager

@pytest.mark.asyncio
async def test_agent_runner_uses_skill_manager():
    runner = AgentRunner(use_mock=True)
    assert hasattr(runner, "skill_manager")
    assert isinstance(runner.skill_manager, SkillManager)

    # Test dispatching with standard and custom roles
    events = []
    async def callback(event_type, data):
        events.append((event_type, data))

    res = await runner.dispatch_agent_task(
        project_id="proj-123",
        role="BackendDev",
        prompt="Build a new user registration route",
        workspace_path="/test/path",
        project_context={"stack": "FastAPI", "test_command": "pytest"},
        event_callback=callback
    )

    assert res["status"] == "SUCCESS"
    assert res["role"] == "BackendDev"
    assert len(events) > 0

@pytest.mark.asyncio
async def test_agent_runner_synthesizes_custom_role_prompt():
    runner = AgentRunner(use_mock=True)
    
    # Verify prompt synthesis for non-preset custom role
    prompt = runner.skill_manager.synthesize_agent_prompt(
        role="SmartContractAuditor",
        project_context={"stack": "Solidity/Hardhat", "project_purpose": "DeFi Lending"}
    )
    assert "SmartContractAuditor" in prompt or "Smart Contract Auditor" in prompt
    assert "DeFi Lending" in prompt
