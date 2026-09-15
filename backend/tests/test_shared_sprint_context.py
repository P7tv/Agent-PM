import pytest
import os
import tempfile
import asyncio
from app.services.skill_manager import SkillManager
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager
from app.services.agent_runner import AgentRunner
from app.services.orchestrator import Orchestrator

def test_synthesize_agent_prompt_with_normalized_meta_and_blackboard():
    sm = SkillManager()
    
    project_context = {
        "purpose_summary": "High-speed 3D WebGL Vehicle Racing Simulator",
        "stack_type": "Node.js",
        "frameworks": ["Three.js", "React", "Cannon.js"],
        "directory_structure": ["src/game/", "src/physics/", "src/shaders/"],
        "test_command": "npm test",
        "has_docker": True,
        # Sprint blackboard
        "tech_lead_notes": "Ensure 60 FPS on mobile and low draw calls.",
        "architect_plan": "Breakdown: Physics loop in worker, Three.js canvas in HUD.",
        "backend_specs": "POST /api/telemetry, GET /api/leaderboard",
        "design_specs": "Cyberpunk dark theme with neon yellow accents.",
        "qa_criteria": "Verify 60 FPS and telemetry payload schema."
    }
    
    prompt = sm.synthesize_agent_prompt(
        role="FrontendDev",
        project_context=project_context
    )
    
    # Check normalized metadata rendered
    assert "High-speed 3D WebGL Vehicle Racing Simulator" in prompt
    assert "Node.js (Three.js, React, Cannon.js)" in prompt
    assert "src/game, src/physics, src/shaders" in prompt
    assert "npm test" in prompt
    assert "Docker: Detected" in prompt
    
    # Check blackboard sections rendered
    assert "TECH LEAD DIRECTIVE & CONSTRAINTS" in prompt
    assert "Ensure 60 FPS on mobile" in prompt
    assert "SPRINT ARCHITECTURAL BLUEPRINT & CONTRACTS" in prompt
    assert "Physics loop in worker" in prompt
    assert "COMPLETED BACKEND API SPECIFICATIONS" in prompt
    assert "POST /api/telemetry" in prompt
    assert "COMPLETED DESIGN TOKENS & UI SPECIFICATIONS" in prompt
    assert "Cyberpunk dark theme" in prompt
    assert "QA VERIFICATION & ACCEPTANCE CRITERIA" in prompt
    assert "telemetry payload schema" in prompt

@pytest.mark.asyncio
async def test_orchestrator_shared_blackboard_and_custom_specialists():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(os.path.join(tmpdir, "state.db"))
        pm = ProjectManager(store=store)
        p = pm.register_project("proj-race", "Race Game", tmpdir, auto_pilot=True)
        
        # Add a custom specialist to project roster
        store.add_agent(
            project_id="proj-race",
            role="ThreeJsSpecialist",
            title="3D WebGL Specialist",
            description="Expert in Three.js rendering pipelines, shaders, and GLTF assets",
            skill_name="ui-styling",
            skill_tier="stock"
        )
        
        # Track dispatched prompts for each role
        dispatched_prompts = {}
        dispatched_contexts = {}
        
        runner = AgentRunner(use_mock=True)
        orig_dispatch = runner.dispatch_agent_task
        
        async def tracking_dispatch(*args, **kwargs):
            role = kwargs.get("role") or (args[1] if len(args) > 1 else None)
            prompt = kwargs.get("prompt") or (args[2] if len(args) > 2 else "")
            pcontext = kwargs.get("project_context") or (args[4] if len(args) > 4 else {})
            dispatched_prompts[role] = prompt
            dispatched_contexts[role] = pcontext
            return await orig_dispatch(*args, **kwargs)
            
        runner.dispatch_agent_task = tracking_dispatch
        orch = Orchestrator(store=store, project_manager=pm, agent_runner=runner)
        
        result = await orch.execute_pm_directive("proj-race", "Build multiplayer vehicle lobby")
        
        assert result["status"] == "COMPLETED"
        
        # 1. Verify Architect received TechLead triage
        assert "Tech Lead Guidance & Constraints" in dispatched_prompts["Architect"]
        
        # 2. Verify Designer received Architect plan
        assert "Architectural Blueprint" in dispatched_prompts["Designer"]
        
        # 3. Verify BackendDev received Architect plan
        assert "Architectural Blueprint & API Contracts" in dispatched_prompts["BackendDev"]
        
        # 4. Verify Custom Specialist (ThreeJsSpecialist) was dispatched in sprint!
        assert "ThreeJsSpecialist" in dispatched_prompts
        assert "Architectural Blueprint" in dispatched_prompts["ThreeJsSpecialist"]
        assert "Specialist Persona" in dispatched_prompts["ThreeJsSpecialist"]
        
        # 5. Verify FrontendDev received Backend API contracts AND Designer tokens
        assert "Completed Backend API Contracts" in dispatched_prompts["FrontendDev"]
        assert "Completed Design Tokens & Layout" in dispatched_prompts["FrontendDev"]
        
        # 6. Verify QATester received acceptance criteria and changes
        assert "Architect Acceptance Criteria" in dispatched_prompts["QATester"]
        assert "Backend Changes" in dispatched_prompts["QATester"]
        assert "Frontend Changes" in dispatched_prompts["QATester"]
        
        # 7. Verify tasks recorded in store (4 standard + custom specialists)
        tasks = store.get_tasks("proj-race")
        assert len(tasks) >= 5
        custom_task = next((t for t in tasks if t.assigned_to == "ThreeJsSpecialist"), None)
        assert custom_task is not None
        assert custom_task.status == "DONE"
