"""Tests for Backlog Management and Sprint Promotion."""
import pytest
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager
from app.services.orchestrator import Orchestrator
from app.services.sprint_queue import SprintQueue


@pytest.fixture
def store_and_queue(tmp_path):
    db_file = tmp_path / "test_backlog.db"
    store = StateStore(db_path=str(db_file))
    pm = ProjectManager(store=store)
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    pm.register_project("proj_backlog", "Backlog Project", str(ws_dir))
    queue = SprintQueue(store=store, orchestrator=None)
    return store, queue


def test_backlog_crud(store_and_queue):
    store, _ = store_and_queue
    item = store.create_backlog_item(
        project_id="proj_backlog",
        title="Add Google OAuth",
        description="Support user sign in with Google",
        category="feature",
        priority="HIGH"
    )
    assert item.item_id is not None
    assert item.title == "Add Google OAuth"
    assert item.priority == "HIGH"
    assert item.status == "BACKLOG"

    items = store.get_backlog_items("proj_backlog")
    assert len(items) == 1
    assert items[0].title == "Add Google OAuth"

    updated = store.update_backlog_item(item.item_id, priority="URGENT", status="QUEUED")
    assert updated.priority == "URGENT"
    assert updated.status == "QUEUED"

    deleted = store.delete_backlog_item(item.item_id)
    assert deleted is True
    assert len(store.get_backlog_items("proj_backlog")) == 0
