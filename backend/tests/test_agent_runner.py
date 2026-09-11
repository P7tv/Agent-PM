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

@pytest.mark.asyncio
async def test_agent_runner_returns_token_and_backend_metadata():
    runner = AgentRunner(use_mock=True)
    result = await runner.dispatch_agent_task(
        project_id="test-p1",
        role="Architect",
        prompt="Plan a todo app",
        workspace_path="/tmp"
    )
    assert "tokens_used" in result
    assert "backend_used" in result
    assert result["backend_used"] in ("mock", "cli", "sdk")
    assert isinstance(result["tokens_used"], int)

@pytest.mark.asyncio
async def test_dispatch_chat_task_returns_token_and_backend_metadata():
    runner = AgentRunner(use_mock=True)
    result = await runner.dispatch_chat_task(
        project_id="test-p1",
        role="TechLead",
        message="hello",
        workspace_path="/tmp"
    )
    assert "tokens_used" in result
    assert "backend_used" in result
    assert result["backend_used"] in ("mock", "cli", "sdk")
    assert isinstance(result["tokens_used"], int)

