import pytest
from app.services.workspace_inspector import WorkspaceInspector

def test_dynamic_roster_ml_project():
    inspector = WorkspaceInspector()
    meta = {
        "stack_type": "Python",
        "frameworks": ["torch", "pandas", "pytest"],
        "purpose_summary": "Deep learning model training pipeline",
        "test_runner": "pytest"
    }

    roster = inspector.generate_tailored_roster(meta)
    assert len(roster) >= 3 and len(roster) <= 6
    roles = [a["role"] for a in roster]
    skills = [a.get("skill_name") for a in roster]

    assert "TechLead" in roles
    # Should have ML Engineer or ML specialist
    assert any("ml" in r.lower() or "data" in r.lower() for r in roles)
    assert "ml-data-engineer" in skills
    # Should NOT have a Designer role for an ML script project!
    assert "Designer" not in roles

def test_dynamic_roster_frontend_web_project():
    inspector = WorkspaceInspector()
    meta = {
        "stack_type": "Node.js / React",
        "frameworks": ["react", "vite", "tailwind"],
        "purpose_summary": "E-commerce customer checkout portal",
        "test_runner": "vitest"
    }

    roster = inspector.generate_tailored_roster(meta)
    roles = [a["role"] for a in roster]
    skills = [a.get("skill_name") for a in roster]

    assert "TechLead" in roles
    assert "FrontendDev" in roles
    assert "frontend-dev" in skills
    assert "QATester" in roles

def test_dynamic_roster_backend_api_only():
    inspector = WorkspaceInspector()
    meta = {
        "stack_type": "Python",
        "frameworks": ["fastapi", "pytest"],
        "purpose_summary": "High-throughput financial pricing service",
        "test_runner": "pytest",
        "has_docker": True
    }

    roster = inspector.generate_tailored_roster(meta)
    roles = [a["role"] for a in roster]
    skills = [a.get("skill_name") for a in roster]

    assert "TechLead" in roles
    assert "BackendDev" in roles
    assert "backend-dev" in skills
    # No Designer in an API-only microservice
    assert "Designer" not in roles
    # Should have DevOps or Security
    assert "DevOps" in roles or "Security" in roles
