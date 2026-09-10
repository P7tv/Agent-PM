import pytest
import asyncio
from app.services.agent_runner import AgentRunner

@pytest.mark.asyncio
async def test_agent_runner_streaming_events():
    runner = AgentRunner(use_mock=True)  # supports mock for fast deterministic test
    events = []
    
    async def on_event(event_type: str, data: dict):
        events.append((event_type, data))
        
    result = await runner.dispatch_agent_task(
        project_id="test-p1",
        role="Architect",
        prompt="Plan a todo app",
        workspace_path="/tmp",
        event_callback=on_event
    )
    
    event_types = [e[0] for e in events]
    assert "AGENT_THOUGHT_DELTA" in event_types
    assert "AGENT_STATUS_CHANGE" in event_types
    assert result["status"] == "SUCCESS"
    assert len(result["response"]) > 0
