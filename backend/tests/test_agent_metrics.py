"""Tests for Agent Activity Logging and Metrics Aggregation."""
import pytest
from app.services.state_store import StateStore


@pytest.fixture
def store(tmp_path):
    db_file = tmp_path / "test_metrics.db"
    return StateStore(db_path=str(db_file))


def test_agent_activity_and_metrics(store):
    # Record multiple agent activities
    store.record_agent_activity(
        project_id="proj_m",
        role="FrontendDev",
        action_type="sprint_task",
        sprint_id="sprint-1",
        tokens_used=1500,
        duration_seconds=12.5,
        status="SUCCESS",
        summary="Built login component"
    )
    store.record_agent_activity(
        project_id="proj_m",
        role="FrontendDev",
        action_type="sprint_task",
        sprint_id="sprint-2",
        tokens_used=2500,
        duration_seconds=17.5,
        status="SUCCESS",
        summary="Refactored dashboard header"
    )
    store.record_agent_activity(
        project_id="proj_m",
        role="BackendDev",
        action_type="sprint_task",
        sprint_id="sprint-1",
        tokens_used=3000,
        duration_seconds=20.0,
        status="SUCCESS",
        summary="Created auth endpoints"
    )

    activities = store.list_agent_activities("proj_m")
    assert len(activities) == 3

    fe_activities = store.list_agent_activities("proj_m", role="FrontendDev")
    assert len(fe_activities) == 2

    # Get aggregated metrics
    metrics = store.get_agent_metrics("proj_m")
    assert "FrontendDev" in metrics
    assert "BackendDev" in metrics
    assert metrics["FrontendDev"]["total_actions"] == 2
    assert metrics["FrontendDev"]["total_tokens"] == 4000
    assert metrics["FrontendDev"]["avg_duration_seconds"] == 15.0
    assert metrics["FrontendDev"]["success_rate"] == 100.0
    assert metrics["BackendDev"]["total_tokens"] == 3000
