"""Tests for Project Memory persistence and retrieval."""
import pytest
from app.services.state_store import StateStore


@pytest.fixture
def store(tmp_path):
    db_file = tmp_path / "test_memory.db"
    return StateStore(db_path=str(db_file))


def test_project_memory_crud(store):
    # Add memory
    mem1 = store.add_project_memory(
        project_id="proj_x",
        title="CSS Framework",
        content="Use TailwindCSS v4 with Vanilla CSS variables",
        category="architecture"
    )
    assert mem1.memory_id is not None
    assert mem1.category == "architecture"

    mem2 = store.add_project_memory(
        project_id="proj_x",
        title="API Convention",
        content="All endpoints must return JSON with status code 200/400",
        category="rule"
    )

    # Get memories
    memories = store.get_project_memories("proj_x")
    assert len(memories) == 2

    # Delete memory
    del_res = store.delete_project_memory(mem1.memory_id)
    assert del_res is True

    memories_after = store.get_project_memories("proj_x")
    assert len(memories_after) == 1
    assert memories_after[0].title == "API Convention"
