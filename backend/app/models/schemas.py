from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
import uuid
import time

class AgentRole(str, Enum):
    TECH_LEAD = "TechLead"
    ARCHITECT = "Architect"
    DESIGNER = "Designer"
    FRONTEND_DEV = "FrontendDev"
    BACKEND_DEV = "BackendDev"
    QA_TESTER = "QATester"
    REVIEWER = "Reviewer"
    DOC_WRITER = "DocWriter"
    DEVOPS = "DevOps"
    SECURITY = "Security"
    ML_ENGINEER = "MLEngineer"
    DATA_ENGINEER = "DataEngineer"
    DEBUGGER = "SystematicDebugger"

class AgentStatus(str, Enum):
    IDLE = "IDLE"
    THINKING = "THINKING"
    WORKING = "WORKING"
    TESTING = "TESTING"
    REVIEWING = "REVIEWING"
    BLOCKED = "BLOCKED"
    DONE = "DONE"

class TaskStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    TESTING = "TESTING"
    REVIEW = "REVIEW"
    DONE = "DONE"
    FAILED = "FAILED"

class TaskItem(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    project_id: str
    title: str
    description: str = ""
    assigned_to: str
    status: TaskStatus = TaskStatus.TODO
    sprint_id: Optional[str] = None
    result_output: Optional[str] = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

class AgentState(BaseModel):
    project_id: str
    role: str
    status: AgentStatus = AgentStatus.IDLE
    current_task_id: Optional[str] = None
    thought: str = ""
    last_tool_call: Optional[str] = None
    skill_name: Optional[str] = None
    skill_tier: Optional[str] = "stock"
    skill_title: Optional[str] = None
    equipped_skills: List[str] = Field(default_factory=list)
    skill_mode: str = "AUTO"
    updated_at: float = Field(default_factory=time.time)

class SkillMetadata(BaseModel):
    name: str
    title: str
    description: str = ""
    tier: str = "stock"
    allowed_tools: List[str] = Field(default_factory=list)
    triggers: List[str] = Field(default_factory=list)

class SkillDetail(SkillMetadata):
    instructions: str = ""
    raw_content: str = ""
    file_path: Optional[str] = None

class Project(BaseModel):
    project_id: str
    name: str
    workspace_path: str
    auto_pilot: bool = False
    created_at: float = Field(default_factory=time.time)

class ApprovalRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    project_id: str
    gate_type: str
    summary: str
    status: str = "PENDING"  # PENDING, APPROVED, REJECTED
    created_at: float = Field(default_factory=time.time)

class SprintRecord(BaseModel):
    sprint_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    project_id: str
    directive: str
    status: str = "RUNNING"  # RUNNING | COMPLETED | REJECTED | FAILED
    total_tokens: int = 0
    backend_used: str = "mock"
    started_at: float = Field(default_factory=time.time)
    completed_at: Optional[float] = None
    tasks_count: int = 0
    release_summary: Optional[str] = None
    execution_plan: Dict[str, Any] = Field(default_factory=dict)
    verification_report: Dict[str, Any] = Field(default_factory=dict)
    change_evidence: Dict[str, Any] = Field(default_factory=dict)
    review_verdict: Dict[str, Any] = Field(default_factory=dict)
    checkpoint_path: Optional[str] = None
    source_sprint_id: Optional[str] = None
    resume_from: Optional[str] = None

class QueueItem(BaseModel):
    queue_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    project_id: str
    directive: str
    status: str = "QUEUED"  # QUEUED | RUNNING | COMPLETED | CANCELLED
    position: int = 0
    priority: str = "NORMAL"  # URGENT | HIGH | NORMAL | LOW
    created_at: float = Field(default_factory=time.time)
    acceptance_criteria: List[str] = Field(default_factory=list)
    protected_paths: List[str] = Field(default_factory=list)
    source_sprint_id: Optional[str] = None
    resume_from: Optional[str] = None

class BacklogItem(BaseModel):
    item_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    project_id: str
    title: str
    description: str = ""
    category: str = "feature"  # feature | bug | refactor | doc
    priority: str = "NORMAL"  # URGENT | HIGH | NORMAL | LOW
    status: str = "BACKLOG"  # BACKLOG | QUEUED | COMPLETED
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

class ProjectMemory(BaseModel):
    memory_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    project_id: str
    category: str = "architecture"  # architecture | rule | convention | decision
    title: str
    content: str
    created_at: float = Field(default_factory=time.time)

class AgentActivityLog(BaseModel):
    log_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    project_id: str
    sprint_id: Optional[str] = None
    role: str
    action_type: str = "task_execution"  # task_execution | chat_response | whisper
    tokens_used: int = 0
    duration_seconds: float = 0.0
    status: str = "SUCCESS"  # SUCCESS | FAILED | TIMEOUT
    summary: Optional[str] = None
    created_at: float = Field(default_factory=time.time)




class DownloadSkillRequest(BaseModel):
    url: str
    skill_name: Optional[str] = None
    target: str = "project"  # "project", "stock", "agy"
    project_id: Optional[str] = None

class AssignSkillRequest(BaseModel):
    skill_name: str

class SkillAddRequest(BaseModel):
    skill_name: str

class SkillRemoveRequest(BaseModel):
    skill_name: str

class SetSkillModeRequest(BaseModel):
    mode: str  # "AUTO" or "MANUAL"

class CustomAgentCreateRequest(BaseModel):
    role: str = Field(..., min_length=2, max_length=50)
    title: str = Field(..., min_length=2, max_length=80)
    description: str = Field(..., min_length=5, max_length=300)
    skill_name: Optional[str] = None
    skill_tier: Optional[str] = "stock"

class AutoGenerateRosterRequest(BaseModel):
    replace_existing: bool = True
