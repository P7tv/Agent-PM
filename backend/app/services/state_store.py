import sqlite3
import json
import time
import uuid
from typing import List, Optional, Dict, Any
from app.models.schemas import (
    Project, TaskItem, AgentState, TaskStatus, AgentStatus, ApprovalRequest, SprintRecord, QueueItem,
    BacklogItem, ProjectMemory, AgentActivityLog
)

from contextlib import contextmanager

class StateStore:
    def __init__(self, db_path: str = "state.db"):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA busy_timeout = 30000")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
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
            try:
                conn.execute("ALTER TABLE tasks ADD COLUMN sprint_id TEXT DEFAULT NULL")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE tasks ADD COLUMN result_output TEXT DEFAULT NULL")
            except sqlite3.OperationalError:
                pass

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
            for column, definition in (
                ("execution_plan_json", "TEXT DEFAULT '{}'"),
                ("verification_report_json", "TEXT DEFAULT '{}'"),
                ("change_evidence_json", "TEXT DEFAULT '{}'"),
                ("review_verdict_json", "TEXT DEFAULT '{}'"),
                ("checkpoint_path", "TEXT DEFAULT NULL"),
                ("source_sprint_id", "TEXT DEFAULT NULL"),
                ("resume_from", "TEXT DEFAULT NULL"),
            ):
                try:
                    conn.execute(f"ALTER TABLE sprints ADD COLUMN {column} {definition}")
                except sqlite3.OperationalError:
                    pass
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
            try:
                conn.execute("ALTER TABLE directive_queue ADD COLUMN priority TEXT DEFAULT 'NORMAL'")
            except sqlite3.OperationalError:
                pass
            for column, definition in (
                ("acceptance_criteria_json", "TEXT DEFAULT '[]'"),
                ("protected_paths_json", "TEXT DEFAULT '[]'"),
                ("source_sprint_id", "TEXT DEFAULT NULL"),
                ("resume_from", "TEXT DEFAULT NULL"),
            ):
                try:
                    conn.execute(f"ALTER TABLE directive_queue ADD COLUMN {column} {definition}")
                except sqlite3.OperationalError:
                    pass

            conn.execute("""
                CREATE TABLE IF NOT EXISTS console_messages (
                    message_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    content TEXT NOT NULL,
                    msg_type TEXT DEFAULT 'user_chat',
                    role TEXT,
                    code_proposals_json TEXT DEFAULT '[]',
                    qa_results_json TEXT DEFAULT NULL,
                    attachments_json TEXT DEFAULT '[]',
                    active_skills_json TEXT DEFAULT '[]',
                    timestamp REAL NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS backlog_items (
                    item_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    category TEXT DEFAULT 'feature',
                    priority TEXT DEFAULT 'NORMAL',
                    status TEXT DEFAULT 'BACKLOG',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS project_memories (
                    memory_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    category TEXT DEFAULT 'architecture',
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_activity_logs (
                    log_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    sprint_id TEXT,
                    role TEXT NOT NULL,
                    action_type TEXT DEFAULT 'task_execution',
                    tokens_used INTEGER DEFAULT 0,
                    duration_seconds REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'SUCCESS',
                    summary TEXT,
                    created_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_sprint_logs (
                    log_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    sprint_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    step_label TEXT NOT NULL,
                    response_text TEXT DEFAULT '',
                    tokens_used INTEGER DEFAULT 0,
                    created_at REAL NOT NULL
                )
            """)
            # Cleanup orphaned running tasks or agent states from abrupt server shutdowns
            now = time.time()
            conn.execute("UPDATE directive_queue SET status = 'CANCELLED' WHERE status = 'RUNNING'")
            conn.execute("UPDATE agent_states SET status = 'IDLE' WHERE status IN ('WORKING', 'THINKING', 'TESTING', 'REVIEWING')")
            conn.execute(
                """UPDATE sprints SET status = 'FAILED', completed_at = ?,
                   release_summary = 'Backend restarted before this sprint completed.'
                   WHERE status = 'RUNNING'""",
                (now,),
            )
            conn.execute("UPDATE tasks SET status = 'FAILED', updated_at = ? WHERE status IN ('IN_PROGRESS', 'TESTING', 'REVIEW')", (now,))
            conn.execute("UPDATE approvals SET status = 'REJECTED' WHERE status = 'PENDING'")
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

    def create_task(self, project_id: str, title: str, assigned_to: str, description: str = "", sprint_id: Optional[str] = None) -> TaskItem:
        task = TaskItem(project_id=project_id, title=title, description=description, assigned_to=assigned_to, sprint_id=sprint_id)
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO tasks (task_id, project_id, title, description, assigned_to, status, created_at, updated_at, sprint_id, result_output) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (task.task_id, task.project_id, task.title, task.description, task.assigned_to, task.status.value, task.created_at, task.updated_at, task.sprint_id, task.result_output)
            )
            conn.commit()
        return task

    def update_task_status(self, task_id: str, status: str) -> TaskItem:
        now = time.time()
        with self._get_conn() as conn:
            conn.execute("UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?", (status, now, task_id))
            conn.commit()
            cur = conn.execute("SELECT task_id, project_id, title, description, assigned_to, status, created_at, updated_at, sprint_id, result_output FROM tasks WHERE task_id = ?", (task_id,))
            r = cur.fetchone()
            return TaskItem(
                task_id=r[0], project_id=r[1], title=r[2], description=r[3], assigned_to=r[4],
                status=TaskStatus(r[5]), created_at=r[6], updated_at=r[7], sprint_id=r[8], result_output=r[9]
            )

    def update_task_result(self, task_id: str, result_output: str, status: Optional[str] = None) -> Optional[TaskItem]:
        now = time.time()
        with self._get_conn() as conn:
            if status:
                conn.execute("UPDATE tasks SET result_output = ?, status = ?, updated_at = ? WHERE task_id = ?", (result_output, status, now, task_id))
            else:
                conn.execute("UPDATE tasks SET result_output = ?, updated_at = ? WHERE task_id = ?", (result_output, now, task_id))
            conn.commit()
            cur = conn.execute("SELECT task_id, project_id, title, description, assigned_to, status, created_at, updated_at, sprint_id, result_output FROM tasks WHERE task_id = ?", (task_id,))
            r = cur.fetchone()
            if r:
                return TaskItem(
                    task_id=r[0], project_id=r[1], title=r[2], description=r[3], assigned_to=r[4],
                    status=TaskStatus(r[5]), created_at=r[6], updated_at=r[7], sprint_id=r[8], result_output=r[9]
                )
        return None

    def get_tasks(self, project_id: str) -> List[TaskItem]:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT task_id, project_id, title, description, assigned_to, status, created_at, updated_at, sprint_id, result_output FROM tasks WHERE project_id = ? ORDER BY created_at ASC", (project_id,))
            return [
                TaskItem(
                    task_id=r[0], project_id=r[1], title=r[2], description=r[3], assigned_to=r[4],
                    status=TaskStatus(r[5]), created_at=r[6], updated_at=r[7], sprint_id=r[8], result_output=r[9]
                )
                for r in cur.fetchall()
            ]

    def get_sprint_tasks(self, sprint_id: str) -> List[TaskItem]:
        with self._get_conn() as conn:
            cur = conn.execute(
                "SELECT task_id, project_id, title, description, assigned_to, status, created_at, updated_at, sprint_id, result_output FROM tasks WHERE sprint_id = ? ORDER BY created_at ASC",
                (sprint_id,)
            )
            return [
                TaskItem(
                    task_id=r[0], project_id=r[1], title=r[2], description=r[3], assigned_to=r[4],
                    status=TaskStatus(r[5]), created_at=r[6], updated_at=r[7], sprint_id=r[8], result_output=r[9]
                )
                for r in cur.fetchall()
            ]

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

    def add_agent(
        self,
        project_id: str,
        role: str,
        title: str,
        description: str,
        skill_name: Optional[str] = None,
        skill_tier: Optional[str] = "stock"
    ) -> AgentState:
        self.set_agent_status(
            project_id=project_id,
            role=role,
            status="IDLE",
            thought=description,
            skill_name=skill_name,
            skill_tier=skill_tier or "stock",
            skill_title=title
        )
        return self.get_agent_status(project_id, role)

    def delete_agent(self, project_id: str, role: str) -> bool:
        if role == "TechLead":
            return False
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM agent_states WHERE project_id = ? AND role = ?", (project_id, role))
            conn.commit()
            return cur.rowcount > 0

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
            conn.execute("DELETE FROM console_messages WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM backlog_items WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM project_memories WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM agent_activity_logs WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM agent_sprint_logs WHERE project_id = ?", (project_id,))
            conn.commit()

    def record_sprint(self, sprint: SprintRecord) -> SprintRecord:
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sprints
                (sprint_id, project_id, directive, status, total_tokens, backend_used, started_at, completed_at, tasks_count, release_summary,
                 execution_plan_json, verification_report_json, change_evidence_json, review_verdict_json,
                 checkpoint_path, source_sprint_id, resume_from)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sprint.sprint_id, sprint.project_id, sprint.directive, sprint.status,
                    sprint.total_tokens, sprint.backend_used, sprint.started_at,
                    sprint.completed_at, sprint.tasks_count, sprint.release_summary,
                    json.dumps(sprint.execution_plan), json.dumps(sprint.verification_report),
                    json.dumps(sprint.change_evidence), json.dumps(sprint.review_verdict),
                    sprint.checkpoint_path, sprint.source_sprint_id, sprint.resume_from,
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
        tasks_count: Optional[int] = None,
        execution_plan: Optional[Dict[str, Any]] = None,
        verification_report: Optional[Dict[str, Any]] = None,
        change_evidence: Optional[Dict[str, Any]] = None,
        review_verdict: Optional[Dict[str, Any]] = None,
        checkpoint_path: Optional[str] = None,
        source_sprint_id: Optional[str] = None,
        resume_from: Optional[str] = None,
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
        for column, value in (
            ("execution_plan_json", execution_plan),
            ("verification_report_json", verification_report),
            ("change_evidence_json", change_evidence),
            ("review_verdict_json", review_verdict),
        ):
            if value is not None:
                updates.append(f"{column} = ?")
                params.append(json.dumps(value))
        for column, value in (
            ("checkpoint_path", checkpoint_path),
            ("source_sprint_id", source_sprint_id),
            ("resume_from", resume_from),
        ):
            if value is not None:
                updates.append(f"{column} = ?")
                params.append(value)

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
                SELECT sprint_id, project_id, directive, status, total_tokens, backend_used, started_at, completed_at, tasks_count, release_summary,
                       execution_plan_json, verification_report_json, change_evidence_json, review_verdict_json,
                       checkpoint_path, source_sprint_id, resume_from
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
                    release_summary=r[9], execution_plan=json.loads(r[10] or "{}"),
                    verification_report=json.loads(r[11] or "{}"), change_evidence=json.loads(r[12] or "{}"),
                    review_verdict=json.loads(r[13] or "{}"), checkpoint_path=r[14],
                    source_sprint_id=r[15], resume_from=r[16],
                )
                for r in cur.fetchall()
            ]

    def get_sprint(self, sprint_id: str) -> Optional[SprintRecord]:
        with self._get_conn() as conn:
            cur = conn.execute(
                """
                SELECT sprint_id, project_id, directive, status, total_tokens, backend_used, started_at, completed_at, tasks_count, release_summary,
                       execution_plan_json, verification_report_json, change_evidence_json, review_verdict_json,
                       checkpoint_path, source_sprint_id, resume_from
                FROM sprints WHERE sprint_id = ?
                """,
                (sprint_id,)
            )
            r = cur.fetchone()
            if r:
                return SprintRecord(
                    sprint_id=r[0],
                    project_id=r[1],
                    directive=r[2],
                    status=r[3],
                    total_tokens=r[4] or 0,
                    backend_used=r[5] or "mock",
                    started_at=r[6],
                    completed_at=r[7],
                    tasks_count=r[8] or 0,
                    release_summary=r[9], execution_plan=json.loads(r[10] or "{}"),
                    verification_report=json.loads(r[11] or "{}"), change_evidence=json.loads(r[12] or "{}"),
                    review_verdict=json.loads(r[13] or "{}"), checkpoint_path=r[14],
                    source_sprint_id=r[15], resume_from=r[16],
                )
        return None

    def enqueue_directive(
        self,
        project_id: str,
        directive: str,
        priority: str = "NORMAL",
        acceptance_criteria: Optional[List[str]] = None,
        protected_paths: Optional[List[str]] = None,
        source_sprint_id: Optional[str] = None,
        resume_from: Optional[str] = None,
    ) -> QueueItem:
        with self._get_conn() as conn:
            cur = conn.execute("SELECT MAX(position) FROM directive_queue WHERE project_id = ?", (project_id,))
            row = cur.fetchone()
            max_pos = row[0] if row and row[0] is not None else -1
            item = QueueItem(
                project_id=project_id, directive=directive, position=max_pos + 1, priority=priority,
                acceptance_criteria=acceptance_criteria or [], protected_paths=protected_paths or [],
                source_sprint_id=source_sprint_id, resume_from=resume_from,
            )
            conn.execute(
                """INSERT INTO directive_queue
                   (queue_id, project_id, directive, status, position, priority, created_at,
                    acceptance_criteria_json, protected_paths_json, source_sprint_id, resume_from)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item.queue_id, item.project_id, item.directive, item.status, item.position,
                 item.priority, item.created_at, json.dumps(item.acceptance_criteria),
                 json.dumps(item.protected_paths), item.source_sprint_id, item.resume_from)
            )
            conn.commit()
            return item

    def get_queue(self, project_id: str) -> List[QueueItem]:
        with self._get_conn() as conn:
            cur = conn.execute(
                """SELECT queue_id, project_id, directive, status, position, created_at, priority,
                          acceptance_criteria_json, protected_paths_json, source_sprint_id, resume_from
                   FROM directive_queue WHERE project_id = ? AND status = 'QUEUED'
                   ORDER BY CASE priority WHEN 'URGENT' THEN 0 WHEN 'HIGH' THEN 1 WHEN 'NORMAL' THEN 2 ELSE 3 END,
                            position ASC, created_at ASC""",
                (project_id,)
            )
            return [
                QueueItem(queue_id=r[0], project_id=r[1], directive=r[2], status=r[3], position=r[4],
                          created_at=r[5], priority=r[6] or "NORMAL",
                          acceptance_criteria=json.loads(r[7] or "[]"), protected_paths=json.loads(r[8] or "[]"),
                          source_sprint_id=r[9], resume_from=r[10])
                for r in cur.fetchall()
            ]

    def update_queue_item(self, queue_id: str, status: str):
        with self._get_conn() as conn:
            conn.execute("UPDATE directive_queue SET status = ? WHERE queue_id = ?", (status, queue_id))
            conn.commit()

    def claim_queue_item(self, queue_id: str) -> bool:
        """Atomically move one queued directive to RUNNING."""
        with self._get_conn() as conn:
            cur = conn.execute(
                """UPDATE directive_queue SET status = 'RUNNING'
                   WHERE queue_id = ? AND status = 'QUEUED'
                     AND NOT EXISTS (
                         SELECT 1 FROM directive_queue active
                         WHERE active.project_id = directive_queue.project_id
                           AND active.status = 'RUNNING'
                     )""",
                (queue_id,),
            )
            conn.commit()
            return cur.rowcount == 1

    def get_queue_item(self, queue_id: str) -> Optional[QueueItem]:
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT queue_id, project_id, directive, status, position, created_at, priority,
                          acceptance_criteria_json, protected_paths_json, source_sprint_id, resume_from
                   FROM directive_queue WHERE queue_id = ?""",
                (queue_id,),
            ).fetchone()
            if not row:
                return None
            return QueueItem(
                queue_id=row[0], project_id=row[1], directive=row[2], status=row[3],
                position=row[4], created_at=row[5], priority=row[6] or "NORMAL",
                acceptance_criteria=json.loads(row[7] or "[]"), protected_paths=json.loads(row[8] or "[]"),
                source_sprint_id=row[9], resume_from=row[10],
            )

    def cancel_queue_item(self, queue_id: str) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute("UPDATE directive_queue SET status = 'CANCELLED' WHERE queue_id = ? AND status = 'QUEUED'", (queue_id,))
            conn.commit()
            return cur.rowcount > 0

    def get_all_queue_items(self) -> List[QueueItem]:
        with self._get_conn() as conn:
            cur = conn.execute(
                """SELECT queue_id, project_id, directive, status, position, created_at, priority,
                          acceptance_criteria_json, protected_paths_json, source_sprint_id, resume_from
                   FROM directive_queue WHERE status IN ('QUEUED', 'RUNNING')
                   ORDER BY CASE status WHEN 'RUNNING' THEN 0 ELSE 1 END,
                            CASE priority WHEN 'URGENT' THEN 0 WHEN 'HIGH' THEN 1 WHEN 'NORMAL' THEN 2 ELSE 3 END,
                            created_at ASC"""
            )
            return [
                QueueItem(queue_id=r[0], project_id=r[1], directive=r[2], status=r[3], position=r[4],
                          created_at=r[5], priority=r[6] or "NORMAL",
                          acceptance_criteria=json.loads(r[7] or "[]"), protected_paths=json.loads(r[8] or "[]"),
                          source_sprint_id=r[9], resume_from=r[10])
                for r in cur.fetchall()
            ]

    def set_queue_priority(self, queue_id: str, priority: str) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute("UPDATE directive_queue SET priority = ? WHERE queue_id = ?", (priority, queue_id))
            conn.commit()
            return cur.rowcount > 0

    def reorder_queue_item(self, queue_id: str, direction: str) -> bool:
        """Move item 'up' or 'down' relative to its peers."""
        with self._get_conn() as conn:
            cur = conn.execute("SELECT queue_id, project_id, position, priority, status FROM directive_queue WHERE queue_id = ?", (queue_id,))
            target = cur.fetchone()
            if not target or target[4] != "QUEUED" or direction not in {"up", "down"}:
                return False
            _, project_id, current_pos, priority, _status = target
            if direction == "up":
                cur = conn.execute(
                    "SELECT queue_id, position FROM directive_queue WHERE project_id = ? AND status = 'QUEUED' AND priority = ? AND position < ? ORDER BY position DESC LIMIT 1",
                    (project_id, priority, current_pos)
                )
            else:
                cur = conn.execute(
                    "SELECT queue_id, position FROM directive_queue WHERE project_id = ? AND status = 'QUEUED' AND priority = ? AND position > ? ORDER BY position ASC LIMIT 1",
                    (project_id, priority, current_pos)
                )
            other = cur.fetchone()
            if not other:
                return False
            other_id, other_pos = other
            conn.execute("UPDATE directive_queue SET position = ? WHERE queue_id = ?", (other_pos, queue_id))
            conn.execute("UPDATE directive_queue SET position = ? WHERE queue_id = ?", (current_pos, other_id))
            conn.commit()
            return True

    # ── Console Messages Persistence ────────────────────────────
    def add_console_message(
        self,
        project_id: str,
        sender: str,
        content: str,
        msg_type: str = "user_chat",
        role: Optional[str] = None,
        code_proposals: Optional[List[Dict[str, str]]] = None,
        qa_results: Optional[Dict[str, Any]] = None,
        attachments: Optional[List[Dict[str, str]]] = None,
        active_skills: Optional[List[str]] = None,
        message_id: Optional[str] = None,
        timestamp: Optional[float] = None
    ) -> Dict[str, Any]:
        msg_id = message_id or str(uuid.uuid4())[:8]
        ts = timestamp or time.time()
        c_prop = json.dumps(code_proposals) if code_proposals else "[]"
        qa_res = json.dumps(qa_results) if qa_results else None
        att = json.dumps(attachments) if attachments else "[]"
        skills = json.dumps(active_skills) if active_skills else "[]"
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO console_messages 
                   (message_id, project_id, sender, content, msg_type, role, code_proposals_json, qa_results_json, attachments_json, active_skills_json, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (msg_id, project_id, sender, content, msg_type, role or sender, c_prop, qa_res, att, skills, ts)
            )
            conn.commit()
        return {
            "message_id": msg_id,
            "project_id": project_id,
            "sender": sender,
            "content": content,
            "msg_type": msg_type,
            "role": role or sender,
            "code_proposals": code_proposals or [],
            "qa_results": qa_results,
            "attachments": attachments or [],
            "active_skills": active_skills or [],
            "timestamp": ts
        }

    def get_console_messages(self, project_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cur = conn.execute(
                """SELECT message_id, project_id, sender, content, msg_type, role, code_proposals_json, qa_results_json, attachments_json, active_skills_json, timestamp
                   FROM console_messages WHERE project_id = ? ORDER BY timestamp DESC, rowid DESC LIMIT ?""",
                (project_id, max(0, limit))
            )
            rows = cur.fetchall()
            results = []
            for r in reversed(rows):
                results.append({
                    "message_id": r[0],
                    "project_id": r[1],
                    "sender": r[2],
                    "content": r[3],
                    "msg_type": r[4],
                    "role": r[5],
                    "code_proposals": json.loads(r[6]) if r[6] else [],
                    "qa_results": json.loads(r[7]) if r[7] else None,
                    "attachments": json.loads(r[8]) if r[8] else [],
                    "active_skills": json.loads(r[9]) if r[9] else [],
                    "timestamp": r[10]
                })
            return results

    def clear_console_messages(self, project_id: str):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM console_messages WHERE project_id = ?", (project_id,))
            conn.commit()

    # ── Backlog Management ─────────────────────────────────────
    def create_backlog_item(
        self,
        project_id: str,
        title: str,
        description: str = "",
        category: str = "feature",
        priority: str = "NORMAL"
    ) -> BacklogItem:
        item = BacklogItem(
            project_id=project_id,
            title=title,
            description=description,
            category=category,
            priority=priority
        )
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO backlog_items 
                   (item_id, project_id, title, description, category, priority, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item.item_id, item.project_id, item.title, item.description, item.category, item.priority, item.status, item.created_at, item.updated_at)
            )
            conn.commit()
        return item

    def get_backlog_items(self, project_id: str) -> List[BacklogItem]:
        with self._get_conn() as conn:
            cur = conn.execute(
                """SELECT item_id, project_id, title, description, category, priority, status, created_at, updated_at
                   FROM backlog_items WHERE project_id = ? ORDER BY created_at DESC""",
                (project_id,)
            )
            return [
                BacklogItem(
                    item_id=r[0], project_id=r[1], title=r[2], description=r[3],
                    category=r[4], priority=r[5], status=r[6], created_at=r[7], updated_at=r[8]
                )
                for r in cur.fetchall()
            ]

    def update_backlog_item(
        self,
        item_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        status: Optional[str] = None
    ) -> Optional[BacklogItem]:
        now = time.time()
        with self._get_conn() as conn:
            cur = conn.execute("SELECT item_id, project_id, title, description, category, priority, status, created_at, updated_at FROM backlog_items WHERE item_id = ?", (item_id,))
            row = cur.fetchone()
            if not row:
                return None
            new_title = title if title is not None else row[2]
            new_desc = description if description is not None else row[3]
            new_cat = category if category is not None else row[4]
            new_pri = priority if priority is not None else row[5]
            new_stat = status if status is not None else row[6]
            conn.execute(
                "UPDATE backlog_items SET title = ?, description = ?, category = ?, priority = ?, status = ?, updated_at = ? WHERE item_id = ?",
                (new_title, new_desc, new_cat, new_pri, new_stat, now, item_id)
            )
            conn.commit()
            return BacklogItem(
                item_id=row[0], project_id=row[1], title=new_title, description=new_desc,
                category=new_cat, priority=new_pri, status=new_stat, created_at=row[7], updated_at=now
            )

    def delete_backlog_item(self, item_id: str) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM backlog_items WHERE item_id = ?", (item_id,))
            conn.commit()
            return cur.rowcount > 0

    # ── Project Memories (Architectural Rules & Context) ────────
    def add_project_memory(self, project_id: str, title: str, content: str, category: str = "architecture") -> ProjectMemory:
        memory = ProjectMemory(project_id=project_id, title=title, content=content, category=category)
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO project_memories (memory_id, project_id, category, title, content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (memory.memory_id, memory.project_id, memory.category, memory.title, memory.content, memory.created_at)
            )
            conn.commit()
        return memory

    def get_project_memories(self, project_id: str) -> List[ProjectMemory]:
        with self._get_conn() as conn:
            cur = conn.execute(
                "SELECT memory_id, project_id, category, title, content, created_at FROM project_memories WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,)
            )
            return [
                ProjectMemory(memory_id=r[0], project_id=r[1], category=r[2], title=r[3], content=r[4], created_at=r[5])
                for r in cur.fetchall()
            ]

    def delete_project_memory(self, memory_id: str) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM project_memories WHERE memory_id = ?", (memory_id,))
            conn.commit()
            return cur.rowcount > 0

    # ── Agent Activity Logs & Performance Analytics ────────────
    def record_agent_activity(
        self,
        project_id: str,
        role: str,
        action_type: str = "task_execution",
        sprint_id: Optional[str] = None,
        tokens_used: int = 0,
        duration_seconds: float = 0.0,
        status: str = "SUCCESS",
        summary: Optional[str] = None
    ) -> AgentActivityLog:
        log = AgentActivityLog(
            project_id=project_id,
            role=role,
            action_type=action_type,
            sprint_id=sprint_id,
            tokens_used=tokens_used,
            duration_seconds=duration_seconds,
            status=status,
            summary=summary
        )
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO agent_activity_logs 
                   (log_id, project_id, sprint_id, role, action_type, tokens_used, duration_seconds, status, summary, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (log.log_id, log.project_id, log.sprint_id, log.role, log.action_type, log.tokens_used, log.duration_seconds, log.status, log.summary, log.created_at)
            )
            conn.commit()
        return log

    def list_agent_activities(self, project_id: str, role: Optional[str] = None, limit: int = 50) -> List[AgentActivityLog]:
        with self._get_conn() as conn:
            if role:
                cur = conn.execute(
                    """SELECT log_id, project_id, sprint_id, role, action_type, tokens_used, duration_seconds, status, summary, created_at
                       FROM agent_activity_logs WHERE project_id = ? AND role = ? ORDER BY created_at DESC LIMIT ?""",
                    (project_id, role, limit)
                )
            else:
                cur = conn.execute(
                    """SELECT log_id, project_id, sprint_id, role, action_type, tokens_used, duration_seconds, status, summary, created_at
                       FROM agent_activity_logs WHERE project_id = ? ORDER BY created_at DESC LIMIT ?""",
                    (project_id, limit)
                )
            return [
                AgentActivityLog(
                    log_id=r[0], project_id=r[1], sprint_id=r[2], role=r[3], action_type=r[4],
                    tokens_used=r[5] or 0, duration_seconds=r[6] or 0.0, status=r[7], summary=r[8], created_at=r[9]
                )
                for r in cur.fetchall()
            ]

    def get_agent_metrics(self, project_id: str) -> Dict[str, Any]:
        """Calculates aggregated performance metrics per role for a project."""
        with self._get_conn() as conn:
            cur = conn.execute(
                """SELECT role, COUNT(*), SUM(tokens_used), AVG(duration_seconds),
                          SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END)
                   FROM agent_activity_logs WHERE project_id = ? GROUP BY role""",
                (project_id,)
            )
            metrics = {}
            for row in cur.fetchall():
                role, total_tasks, total_tokens, avg_duration, success_count = row
                metrics[role] = {
                    "total_actions": total_tasks,
                    "total_tokens": total_tokens or 0,
                    "avg_duration_seconds": round(avg_duration or 0.0, 2),
                    "success_rate": round((success_count / total_tasks * 100) if total_tasks else 100.0, 1)
                }
            return metrics

    # ─── Agent Sprint Logs ───────────────────────────────────────
    def save_agent_sprint_log(
        self,
        project_id: str,
        sprint_id: str,
        role: str,
        step_label: str,
        response_text: str,
        tokens_used: int = 0
    ) -> str:
        """Persist the full response text of an agent step for a sprint."""
        log_id = str(uuid.uuid4())
        now = time.time()
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO agent_sprint_logs
                   (log_id, project_id, sprint_id, role, step_label, response_text, tokens_used, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (log_id, project_id, sprint_id, role, step_label, response_text, tokens_used, now)
            )
            conn.commit()
        return log_id

    def get_agent_sprint_logs(self, sprint_id: str) -> List[Dict[str, Any]]:
        """Retrieve all agent step logs for a specific sprint."""
        with self._get_conn() as conn:
            cur = conn.execute(
                """SELECT log_id, project_id, sprint_id, role, step_label, response_text, tokens_used, created_at
                   FROM agent_sprint_logs WHERE sprint_id = ? ORDER BY created_at ASC""",
                (sprint_id,)
            )
            return [
                {
                    "log_id": r[0],
                    "project_id": r[1],
                    "sprint_id": r[2],
                    "role": r[3],
                    "step_label": r[4],
                    "response_text": r[5],
                    "tokens_used": r[6] or 0,
                    "created_at": r[7]
                }
                for r in cur.fetchall()
            ]
