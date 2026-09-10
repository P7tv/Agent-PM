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

class DownloadSkillRequest(BaseModel):
    url: str
    skill_name: Optional[str] = None
    target: str = "project"  # "project", "stock", "agy"
    project_id: Optional[str] = None

class AssignSkillRequest(BaseModel):
    skill_name: str

