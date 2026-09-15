import asyncio
import pytest
from app.api.routes import runner, store
from app.services.skill_manager import SkillManager

@pytest.mark.anyio
async def test_multi_skill():
    print("Testing Multi-Skill System...")
    
    project_id = "test_proj_4"
    store.create_project(project_id, "Test Project", "/tmp/test", False)
    
    print("\n--- AUTO MODE ---")
    store.set_agent_status(project_id, "TechLead", status="IDLE", skill_mode="AUTO")
    result = await runner.dispatch_chat_task(project_id, "TechLead", "Hello", "/tmp/test")
    prompt = runner.skill_manager.synthesize_agent_prompt(
            role="TechLead", project_path="/tmp/test", 
            base_skill=runner.skill_manager.get_base_role_skill("TechLead"),
            active_skills=runner.skill_manager.get_domain_skills_for_role("TechLead"))
    print("Auto Skills Prompt Contains SKILL CAPABILITIES CATALOG:", "SKILL CAPABILITIES CATALOG" in prompt)
            
    print("\n--- MANUAL MODE ---")
    store.assign_agent_skill(project_id, "TechLead", "test-driven-development")
    store.assign_agent_skill(project_id, "TechLead", "writing-plans")
    state = store.get_agent_status(project_id, "TechLead")
    print(f"Mode after adding: {state.skill_mode}")
    print(f"Equipped skills: {state.equipped_skills}")
    
if __name__ == "__main__":
    asyncio.run(test_multi_skill())
