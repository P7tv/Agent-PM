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

    def enqueue(
        self, project_id: str, directive: str, priority: str = "NORMAL",
        acceptance_criteria: Optional[List[str]] = None,
        protected_paths: Optional[List[str]] = None,
        source_sprint_id: Optional[str] = None,
        resume_from: Optional[str] = None,
    ) -> QueueItem:
        item = self.store.enqueue_directive(
            project_id, directive, priority=priority,
            acceptance_criteria=acceptance_criteria, protected_paths=protected_paths,
            source_sprint_id=source_sprint_id, resume_from=resume_from,
        )
        self._ensure_worker(project_id)
        return item

    def list_queue(self, project_id: str) -> List[QueueItem]:
        return self.store.get_queue(project_id)

    def cancel_item(self, queue_id: str) -> bool:
        return self.store.cancel_queue_item(queue_id)

    async def stop_project(self, project_id: str) -> None:
        """Stop an active drain before its project rows are deleted."""
        self.orchestrator.abort_pipeline(project_id)
        worker = self._workers.pop(project_id, None)
        if worker and not worker.done():
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)

    def resume_pending(self) -> int:
        """Restart drain workers for directives that survived a server restart."""
        resumed = 0
        for project in self.store.list_projects():
            sprints = self.store.get_sprints(project.project_id)
            latest = max(sprints, key=lambda item: item.started_at) if sprints else None
            if latest and latest.status in {"PAUSED", "INTERRUPTED"}:
                continue  # Restart is not permission to resume a paused project.
            if self.store.get_queue(project.project_id):
                self._ensure_worker(project.project_id)
                resumed += 1
        return resumed

    def _ensure_worker(self, project_id: str):
        existing = self._workers.get(project_id)
        if existing is None or existing.done():
            self._workers[project_id] = asyncio.create_task(self._drain(project_id))

    async def _drain(self, project_id: str):
        paused_source = None
        try:
            while True:
                queue = self.store.get_queue(project_id)
                if not queue:
                    break
                item = queue[0]
                final_status = "FAILED"
                error = None
                if not self.store.claim_queue_item(item.queue_id):
                    break
                if self.broadcast_fn:
                    await self.broadcast_fn("QUEUE_ITEM_STARTED", {"project_id": project_id, "queue_id": item.queue_id, "directive": item.directive})
                try:
                    res = await self.orchestrator.execute_pm_directive(
                        project_id=project_id,
                        directive=item.directive,
                        event_callback=self.broadcast_fn,
                        acceptance_criteria=item.acceptance_criteria,
                        protected_paths=item.protected_paths,
                        source_sprint_id=item.source_sprint_id,
                        resume_from=item.resume_from,
                    )
                    final_status = res.get("status", "COMPLETED") if res else "COMPLETED"
                    if final_status in ["COMPLETED", "SUCCESS"]:
                        self.store.update_queue_item(item.queue_id, "COMPLETED")
                    elif final_status in ["PAUSED", "ABORTED", "REJECTED", "HALTED_QA_FAILURE"]:
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
                if final_status == "PAUSED":
                    paused_source = res.get('sprint_id') if res else None
                    break  # Do not start another directive while the user paused this project.
        finally:
            current = self._workers.get(project_id)
            if current is asyncio.current_task():
                self._workers.pop(project_id, None)
                # A user may explicitly enqueue Resume while the pause-finished
                # broadcast is in flight. Do not strand that request in the queue.
                pending = self.store.get_queue(project_id)
                if paused_source and pending and pending[0].source_sprint_id == paused_source:
                    self._ensure_worker(project_id)
