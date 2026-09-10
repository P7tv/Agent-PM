import sqlite3
import json
import time
from typing import List, Optional
from app.models.schemas import Project, TaskItem, AgentState, TaskStatus, AgentStatus, ApprovalRequest

class StateStore:
    def __init__(self, db_path: str = "state.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT,
                    workspace_path TEXT,
                    auto_pilot INTEGER DEFAULT 0,
                    created_at REAL
                )
            """)
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
            conn.commit()

    def create_project(self, project_id: str, name: str, workspace_path: str, auto_pilot: bool = False) -> Project:
        now = time.time()
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO projects VALUES (?, ?, ?, ?, ?)",
                (project_id, name, workspace_path, 1 if auto_pilot else 0, now)
            )
            conn.commit()
        return Project(project_id=project_id, name=name, workspace_path=workspace_path, auto_pilot=auto_pilot, created_at=now)

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

    def set_agent_status(self, project_id: str, role: str, status: str, thought: str = "", current_task_id: Optional[str] = None, last_tool_call: Optional[str] = None):
        now = time.time()
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO agent_states (project_id, role, status, current_task_id, thought, last_tool_call, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, role) DO UPDATE SET
                    status=excluded.status,
                    current_task_id=coalesce(excluded.current_task_id, agent_states.current_task_id),
                    thought=excluded.thought,
                    last_tool_call=coalesce(excluded.last_tool_call, agent_states.last_tool_call),
                    updated_at=excluded.updated_at
            """, (project_id, role, status, current_task_id, thought, last_tool_call, now))
            conn.commit()

    def get_agent_status(self, project_id: str, role: str) -> AgentState:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT project_id, role, status, current_task_id, thought, last_tool_call, updated_at FROM agent_states WHERE project_id = ? AND role = ?", (project_id, role))
            r = cur.fetchone()
            if r:
                return AgentState(project_id=r[0], role=r[1], status=AgentStatus(r[2]), current_task_id=r[3], thought=r[4], last_tool_call=r[5], updated_at=r[6])
        return AgentState(project_id=project_id, role=role)

    def get_all_agent_states(self, project_id: str) -> List[AgentState]:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT project_id, role, status, current_task_id, thought, last_tool_call, updated_at FROM agent_states WHERE project_id = ? ORDER BY role ASC", (project_id,))
            return [AgentState(project_id=r[0], role=r[1], status=AgentStatus(r[2]), current_task_id=r[3], thought=r[4], last_tool_call=r[5], updated_at=r[6]) for r in cur.fetchall()]

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
            conn.commit()
