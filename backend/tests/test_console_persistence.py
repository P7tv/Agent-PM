"""Tests for Console SQLite Persistence across reloads."""
import os
import pytest
from app.services.state_store import StateStore
from app.services.console_service import ConsoleService


@pytest.fixture
def temp_store(tmp_path):
    db_file = tmp_path / "test_state.db"
    return StateStore(db_path=str(db_file))


def test_console_persistence_across_service_instances(temp_store):
    # Instance 1: write messages
    svc1 = ConsoleService(store=temp_store)
    svc1.add_message("proj_alpha", "user", "Directive 1", msg_type="user_chat")
    svc1.add_message(
        "proj_alpha",
        "TechLead",
        "Acknowledged Directive 1",
        msg_type="agent_response",
        role="TechLead",
        code_proposals=[{"filepath": "main.py", "content": "print('ok')", "status": "pending"}],
        active_skills=["brainstorming"]
    )

    history1 = svc1.get_history("proj_alpha")
    assert len(history1) == 2
    assert history1[0]["content"] == "Directive 1"
    assert history1[1]["active_skills"] == ["brainstorming"]

    # Instance 2: new ConsoleService with same StateStore (simulating backend reboot)
    svc2 = ConsoleService(store=temp_store)
    history2 = svc2.get_history("proj_alpha")
    assert len(history2) == 2
    assert history2[0]["sender"] == "user"
    assert history2[0]["content"] == "Directive 1"
    assert history2[1]["sender"] == "TechLead"
    assert history2[1]["code_proposals"][0]["filepath"] == "main.py"
    assert history2[1]["active_skills"] == ["brainstorming"]


def test_console_persistence_clear(temp_store):
    svc = ConsoleService(store=temp_store)
    svc.add_message("proj_beta", "user", "Message to clear")
    assert len(svc.get_history("proj_beta")) == 1

    svc.clear_history("proj_beta")
    assert len(svc.get_history("proj_beta")) == 0

    # Verify cleared in new instance
    svc_reboot = ConsoleService(store=temp_store)
    assert len(svc_reboot.get_history("proj_beta")) == 0
