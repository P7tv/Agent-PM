import pytest
from app.services.agent_runner import AgentRunner

@pytest.mark.asyncio
async def test_context_aware_system_instructions():
    runner = AgentRunner(use_mock=True)
    events = []
    async def callback(event_type, data):
        events.append((event_type, data))
        
    context = {
        "suggested_name": "Payment Gateway",
        "purpose_summary": "Handles credit card processing and billing webhooks.",
        "stack_type": "Python / FastAPI",
        "frameworks": ["fastapi", "stripe"],
        "test_runner": "pytest",
        "test_command": "pytest tests/ -v"
    }
    
    res = await runner.dispatch_agent_task(
        project_id="p1",
        role="BackendDev",
        prompt="Implement stripe webhook verification",
        workspace_path="/mock/path",
        project_context=context,
        event_callback=callback
    )
    assert res["status"] == "SUCCESS"
    assert "stripe webhook verification" in res["response"]
