"""Tests for directive queue priority setting and reordering."""
import pytest
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager


@pytest.fixture
def store(tmp_path):
    db_file = tmp_path / "test_queue_prio.db"
    store = StateStore(db_path=str(db_file))
    pm = ProjectManager(store=store)
    ws_dir = tmp_path / "ws"
    ws_dir.mkdir()
    pm.register_project("proj_q", "Queue Project", str(ws_dir))
    return store


def test_queue_priority_and_reorder(store):
    q1 = store.enqueue_directive("proj_q", "Task 1", priority="NORMAL")
    q2 = store.enqueue_directive("proj_q", "Task 2", priority="HIGH")
    q3 = store.enqueue_directive("proj_q", "Task 3", priority="URGENT")

    queue = store.get_queue("proj_q")
    assert len(queue) == 3
    assert queue[0].directive == "Task 3"
    assert queue[1].directive == "Task 2"
    assert queue[2].directive == "Task 1"
    assert queue[0].priority == "URGENT"

    # Change priority of Task 1 to URGENT
    res = store.set_queue_priority(q1.queue_id, "URGENT")
    assert res is True
    queue_after = store.get_queue("proj_q")
    assert queue_after[0].priority == "URGENT"

    # Reorder within the same priority group.
    res_move = store.reorder_queue_item(q3.queue_id, "up")
    assert res_move is True
    queue_reordered = store.get_queue("proj_q")
    assert queue_reordered[0].directive == "Task 3"
    assert queue_reordered[1].directive == "Task 1"
    assert queue_reordered[2].directive == "Task 2"
