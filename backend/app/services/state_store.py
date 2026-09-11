import sqlite3
import json
import time
from typing import List, Optional, Dict, Any
from app.models.schemas import Project, TaskItem, AgentState, TaskStatus, AgentStatus, ApprovalRequest, SprintRecord, QueueItem

from contextlib import contextmanager

class StateStore:
    def __init__(self, db_path: str = "state.db"):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT,
                    workspace_path TEXT,
                    auto_pilot INTEGER DEFAULT 0,
                    created_at REAL,
                    metadata_json TEXT DEFAULT '{}'
                )
            """)
            # Migration: add metadata_json if table already exists without it
            try:
                conn.execute("ALTER TABLE projects ADD COLUMN metadata_json TEXT DEFAULT '{}'")
            except sqlite3.OperationalError:
                pass

            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    project_id TEXT,
                    title TEXT,
                    description TEXT,
                    assigned_to TEXT,
                    status TEXT,
                    created_at REAL,
                    updated_at REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_states (
                    project_id TEXT,
                    role TEXT,
                    status TEXT,
                    current_task_id TEXT,
                    thought TEXT,
                    last_tool_call TEXT,
                    updated_at REAL,
                    PRIMARY KEY (project_id, role)
                )
            """)
            try:
                conn.execute("ALTER TABLE agent_states ADD COLUMN skill_name TEXT DEFAULT NULL")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE agent_states ADD COLUMN skill_tier TEXT DEFAULT 'stock'")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE agent_states ADD COLUMN skill_title TEXT DEFAULT NULL")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE agent_states ADD COLUMN equipped_skills_json TEXT DEFAULT '[]'")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE agent_states ADD COLUMN skill_mode TEXT DEFAULT 'AUTO'")
            except sqlite3.OperationalError:
                pass

            conn.execute("""
                CREATE TABLE IF NOT EXISTS approvals (
                    request_id TEXT PRIMARY KEY,
                    project_id TEXT,
                    gate_type TEXT,
                    summary TEXT,
                    status TEXT,
                    created_at REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sprints (
                    sprint_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    directive TEXT NOT NULL,
                    status TEXT NOT NULL,
                    total_tokens INTEGER DEFAULT 0,
                    backend_used TEXT DEFAULT 'mock',
                    started_at REAL NOT NULL,
                    completed_at REAL,
                    tasks_count INTEGER DEFAULT 0,
                    release_summary TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS directive_queue (
                    queue_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    directive TEXT NOT NULL,
                    status TEXT NOT NULL,
                    position INTEGER DEFAULT 0,
                    created_at REAL NOT NULL
                )
            """)
            conn.commit()

    def create_project(self, project_id: str, name: str, workspace_path: str, auto_pilot: bool = False, metadata: Optional[Dict[str, Any]] = None) -> Project:
        now = time.time()
        meta_str = json.dumps(metadata) if metadata else "{}"
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO projects VALUES (?, ?, ?, ?, ?, ?)",
                (project_id, name, workspace_path, 1 if auto_pilot else 0, now, meta_str)
            )
            conn.commit()
        return Project(project_id=project_id, name=name, workspace_path=workspace_path, auto_pilot=auto_pilot, created_at=now)

    def get_project_metadata(self, project_id: str) -> Dict[str, Any]:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT metadata_json FROM projects WHERE project_id = ?", (project_id,))
            row = cur.fetchone()
            if row and row[0]:
                try:
                    return json.loads(row[0])
                except Exception:
                    return {}
        return {}

    def update_project_metadata(self, project_id: str, metadata: Dict[str, Any]):
        with self._get_conn() as conn:
            conn.execute("UPDATE projects SET metadata_json = ? WHERE project_id = ?", (json.dumps(metadata), project_id))
            conn.commit()


    def get_project(self, project_id: str) -> Optional[Project]:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT project_id, name, workspace_path, auto_pilot, created_at FROM projects WHERE project_id = ?", (project_id,))
            row = cur.fetchone()
            if row:
                return Project(project_id=row[0], name=row[1], workspace_path=row[2], auto_pilot=bool(row[3]), created_at=row[4])
        return None

    def list_projects(self) -> List[Project]:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT project_id, name, workspace_path, auto_pilot, created_at FROM projects ORDER BY created_at ASC")
            return [Project(project_id=r[0], name=r[1], workspace_path=r[2], auto_pilot=bool(r[3]), created_at=r[4]) for r in cur.fetchall()]

    def create_task(self, project_id: str, title: str, assigned_to: str, description: str = "") -> TaskItem:
        task = TaskItem(project_id=project_id, title=title, description=description, assigned_to=assigned_to)
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (task.task_id, task.project_id, task.title, task.description, task.assigned_to, task.status.value, task.created_at, task.updated_at)
            )
            conn.commit()
        return task

    def update_task_status(self, task_id: str, status: str) -> TaskItem:
        now = time.time()
        with self._get_conn() as conn:
            conn.execute("UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?", (status, now, task_id))
            conn.commit()
            cur = conn.execute("SELECT task_id, project_id, title, description, assigned_to, status, created_at, updated_at FROM tasks WHERE task_id = ?", (task_id,))
            r = cur.fetchone()
            return TaskItem(task_id=r[0], project_id=r[1], title=r[2], description=r[3], assigned_to=r[4], status=TaskStatus(r[5]), created_at=r[6], updated_at=r[7])

    def get_tasks(self, project_id: str) -> List[TaskItem]:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT task_id, project_id, title, description, assigned_to, status, created_at, updated_at FROM tasks WHERE project_id = ? ORDER BY created_at ASC", (project_id,))
            return [TaskItem(task_id=r[0], project_id=r[1], title=r[2], description=r[3], assigned_to=r[4], status=TaskStatus(r[5]), created_at=r[6], updated_at=r[7]) for r in cur.fetchall()]

    def set_agent_status(
        self,
        project_id: str,
        role: str,
        status: str,
        thought: str = "",
        current_task_id: Optional[str] = None,
        last_tool_call: Optional[str] = None,
        skill_name: Optional[str] = None,
        skill_tier: Optional[str] = "stock",
        skill_title: Optional[str] = None,
        equipped_skills: Optional[List[str]] = None,
        skill_mode: Optional[str] = None
    ):
        now = time.time()
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO agent_states (project_id, role, status, current_task_id, thought, last_tool_call, skill_name, skill_tier, skill_title, equipped_skills_json, skill_mode, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, role) DO UPDATE SET
                    status=excluded.status,
                    current_task_id=coalesce(excluded.current_task_id, agent_states.current_task_id),
                    thought=excluded.thought,
                    last_tool_call=coalesce(excluded.last_tool_call, agent_states.last_tool_call),
                    skill_name=coalesce(excluded.skill_name, agent_states.skill_name),
                    skill_tier=coalesce(excluded.skill_tier, agent_states.skill_tier),
                    skill_title=coalesce(excluded.skill_title, agent_states.skill_title),
                    equipped_skills_json=coalesce(excluded.equipped_skills_json, agent_states.equipped_skills_json),
                    skill_mode=coalesce(excluded.skill_mode, agent_states.skill_mode),
                    updated_at=excluded.updated_at
            """, (project_id, role, status, current_task_id, thought, last_tool_call, skill_name, skill_tier, skill_title, json.dumps(equipped_skills) if equipped_skills is not None else None, skill_mode, now))
            conn.commit()

    def get_agent_status(self, project_id: str, role: str) -> AgentState:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT project_id, role, status, current_task_id, thought, last_tool_call, updated_at, skill_name, skill_tier, skill_title, equipped_skills_json, skill_mode FROM agent_states WHERE project_id = ? AND role = ?", (project_id, role))
            r = cur.fetchone()
            if r:
                return AgentState(
                    project_id=r[0],
                    role=r[1],
                    status=AgentStatus(r[2]),
                    current_task_id=r[3],
                    thought=r[4],
                    last_tool_call=r[5],
                    updated_at=r[6],
                    skill_name=r[7] if len(r) > 7 else None,
                    skill_tier=r[8] if len(r) > 8 else "stock",
                    skill_title=r[9] if len(r) > 9 else None,
                    equipped_skills=json.loads(r[10]) if len(r) > 10 and r[10] else [],
                    skill_mode=r[11] if len(r) > 11 and r[11] else "AUTO"
                )
        return AgentState(project_id=project_id, role=role)

    def assign_agent_skill(
        self,
        project_id: str,
        role: str,
        skill_name: str,
        skill_tier: str = "stock",
        skill_title: Optional[str] = None
    ) -> AgentState:
        now = time.time()
        with self._get_conn() as conn:
            conn.execute("""
                UPDATE agent_states
                SET skill_name = ?, skill_tier = ?, skill_title = ?, updated_at = ?
                WHERE project_id = ? AND role = ?
            """, (skill_name, skill_tier, skill_title, now, project_id, role))
            conn.commit()
        return self.get_agent_status(project_id, role)

    def get_all_agent_states(self, project_id: str) -> List[AgentState]:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT project_id, role, status, current_task_id, thought, last_tool_call, updated_at, skill_name, skill_tier, skill_title, equipped_skills_json, skill_mode FROM agent_states WHERE project_id = ? ORDER BY role ASC", (project_id,))
            return [
                AgentState(
                    project_id=r[0],
                    role=r[1],
                    status=AgentStatus(r[2]),
                    current_task_id=r[3],
                    thought=r[4],
                    last_tool_call=r[5],
                    updated_at=r[6],
                    skill_name=r[7] if len(r) > 7 else None,
                    skill_tier=r[8] if len(r) > 8 else "stock",
                    skill_title=r[9] if len(r) > 9 else None,
                    equipped_skills=json.loads(r[10]) if len(r) > 10 and r[10] else [],
                    skill_mode=r[11] if len(r) > 11 and r[11] else "AUTO"
                )
                for r in cur.fetchall()
            ]

    def list_agents(self, project_id: str) -> List[AgentState]:
        return self.get_all_agent_states(project_id)

    def create_approval_request(self, project_id: str, gate_type: str, summary: str) -> ApprovalRequest:
        req = ApprovalRequest(project_id=project_id, gate_type=gate_type, summary=summary)
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO approvals VALUES (?, ?, ?, ?, ?, ?)",
                (req.request_id, req.project_id, req.gate_type, req.summary, req.status, req.created_at)
            )
            conn.commit()
        return req

    def get_pending_approvals(self, project_id: str) -> List[ApprovalRequest]:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT request_id, project_id, gate_type, summary, status, created_at FROM approvals WHERE project_id = ? AND status = 'PENDING' ORDER BY created_at ASC", (project_id,))
            return [ApprovalRequest(request_id=r[0], project_id=r[1], gate_type=r[2], summary=r[3], status=r[4], created_at=r[5]) for r in cur.fetchall()]

    def resolve_approval(self, request_id: str, status: str):
        with self._get_conn() as conn:
            conn.execute("UPDATE approvals SET status = ? WHERE request_id = ?", (status, request_id))
            conn.commit()

    def delete_project(self, project_id: str):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM tasks WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM agent_states WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM approvals WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM sprints WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM directive_queue WHERE project_id = ?", (project_id,))
            conn.commit()

    def record_sprint(self, sprint: SprintRecord) -> SprintRecord:
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sprints
                (sprint_id, project_id, directive, status, total_tokens, backend_used, started_at, completed_at, tasks_count, release_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sprint.sprint_id, sprint.project_id, sprint.directive, sprint.status,
                    sprint.total_tokens, sprint.backend_used, sprint.started_at,
                    sprint.completed_at, sprint.tasks_count, sprint.release_summary
                )
            )
            conn.commit()
        return sprint

    def update_sprint(
        self,
        sprint_id: str,
        status: Optional[str] = None,
        completed_at: Optional[float] = None,
        total_tokens: Optional[int] = None,
        backend_used: Optional[str] = None,
        release_summary: Optional[str] = None,
        tasks_count: Optional[int] = None
    ):
        updates = []
        params = []
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if completed_at is not None:
            updates.append("completed_at = ?")
            params.append(completed_at)
        if total_tokens is not None:
            updates.append("total_tokens = ?")
            params.append(total_tokens)
        if backend_used is not None:
            updates.append("backend_used = ?")
            params.append(backend_used)
        if release_summary is not None:
            updates.append("release_summary = ?")
            params.append(release_summary)
        if tasks_count is not None:
            updates.append("tasks_count = ?")
            params.append(tasks_count)

        if not updates:
            return

        params.append(sprint_id)
        query = f"UPDATE sprints SET {', '.join(updates)} WHERE sprint_id = ?"
        with self._get_conn() as conn:
            conn.execute(query, tuple(params))
            conn.commit()

    def get_sprints(self, project_id: str) -> List[SprintRecord]:
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                SELECT sprint_id, project_id, directive, status, total_tokens, backend_used, started_at, completed_at, tasks_count, release_summary
                FROM sprints WHERE project_id = ? ORDER BY started_at DESC
                """,
                (project_id,)
            )
            return [
                SprintRecord(
                    sprint_id=r[0],
                    project_id=r[1],
                    directive=r[2],
                    status=r[3],
                    total_tokens=r[4] or 0,
                    backend_used=r[5] or "mock",
                    started_at=r[6],
                    completed_at=r[7],
                    tasks_count=r[8] or 0,
                    release_summary=r[9]
                )
                for r in cur.fetchall()
            ]

    def enqueue_directive(self, project_id: str, directive: str) -> QueueItem:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT MAX(position) FROM directive_queue WHERE project_id = ?", (project_id,))
            row = cur.fetchone()
            max_pos = row[0] if row and row[0] is not None else -1
            item = QueueItem(project_id=project_id, directive=directive, position=max_pos + 1)
            conn.execute(
                "INSERT INTO directive_queue (queue_id, project_id, directive, status, position, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (item.queue_id, item.project_id, item.directive, item.status, item.position, item.created_at)
            )
            conn.commit()
            return item

    def get_queue(self, project_id: str) -> List[QueueItem]:
        with self._get_conn() as conn:
            cur = conn.execute(
                "SELECT queue_id, project_id, directive, status, position, created_at FROM directive_queue WHERE project_id = ? AND status = 'QUEUED' ORDER BY position ASC",
                (project_id,)
            )
            return [
                QueueItem(queue_id=r[0], project_id=r[1], directive=r[2], status=r[3], position=r[4], created_at=r[5])
                for r in cur.fetchall()
            ]

    def update_queue_item(self, queue_id: str, status: str):
        with self._get_conn() as conn:
            conn.execute("UPDATE directive_queue SET status = ? WHERE queue_id = ?", (status, queue_id))
            conn.commit()

    def cancel_queue_item(self, queue_id: str) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute("UPDATE directive_queue SET status = 'CANCELLED' WHERE queue_id = ? AND status = 'QUEUED'", (queue_id,))
            conn.commit()
            return cur.rowcount > 0


