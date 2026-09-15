import asyncio
from typing import Optional, Callable, Dict, Any, List
from app.models.schemas import QueueItem
from app.services.state_store import StateStore
from app.services.orchestrator import Orchestrator

class SprintQueue:
    def __init__(self, store: StateStore, orchestrator: Orchestrator, broadcast_fn: Optional[Callable] = None):
        self.store = store
        self.orchestrator = orchestrator
        self.broadcast_fn = broadcast_fn
        # Track active drain workers per project: { project_id: asyncio.Task }
        self._workers: Dict[str, asyncio.Task] = {}

    def enqueue(self, project_id: str, directive: str, priority: str = "NORMAL") -> QueueItem:
        item = self.store.enqueue_directive(project_id, directive, priority=priority)
        self._ensure_worker(project_id)
        return item

    def list_queue(self, project_id: str) -> List[QueueItem]:
        return self.store.get_queue(project_id)

    def cancel_item(self, queue_id: str) -> bool:
        return self.store.cancel_queue_item(queue_id)

    def resume_pending(self) -> int:
        """Restart drain workers for directives that survived a server restart."""
        resumed = 0
        for project in self.store.list_projects():
            if self.store.get_queue(project.project_id):
                self._ensure_worker(project.project_id)
                resumed += 1
        return resumed

    def _ensure_worker(self, project_id: str):
        existing = self._workers.get(project_id)
        if existing is None or existing.done():
            self._workers[project_id] = asyncio.create_task(self._drain(project_id))

    async def _drain(self, project_id: str):
        while True:
            queue = self.store.get_queue(project_id)
            if not queue:
                break
            item = queue[0]
            final_status = "FAILED"
            error = None
            self.store.update_queue_item(item.queue_id, "RUNNING")
            if self.broadcast_fn:
                await self.broadcast_fn("QUEUE_ITEM_STARTED", {"project_id": project_id, "queue_id": item.queue_id, "directive": item.directive})
            try:
                res = await self.orchestrator.execute_pm_directive(
                    project_id=project_id,
                    directive=item.directive,
                    event_callback=self.broadcast_fn
                )
                final_status = res.get("status", "COMPLETED") if res else "COMPLETED"
                if final_status in ["COMPLETED", "SUCCESS"]:
                    self.store.update_queue_item(item.queue_id, "COMPLETED")
                elif final_status in ["ABORTED", "REJECTED", "HALTED_QA_FAILURE"]:
                    self.store.update_queue_item(item.queue_id, "CANCELLED")
                else:
                    self.store.update_queue_item(item.queue_id, "FAILED")
            except Exception as exc:
                final_status = "FAILED"
                error = str(exc)
                self.store.update_queue_item(item.queue_id, "FAILED")
            if self.broadcast_fn:
                await self.broadcast_fn("QUEUE_ITEM_FINISHED", {
                    "project_id": project_id,
                    "queue_id": item.queue_id,
                    "status": final_status,
                    "error": error,
                })
                await self.broadcast_fn("QUEUE_UPDATED", {"project_id": project_id})
