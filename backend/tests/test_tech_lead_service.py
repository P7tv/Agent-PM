import pytest
import os
import tempfile
from app.services.state_store import StateStore
from app.services.project_manager import ProjectManager
from app.services.tech_lead_service import TechLeadService

def test_tech_lead_standup_generation():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(db_path=os.path.join(tmpdir, "test.db"))
        pm = ProjectManager(store=store)
        ws_dir = os.path.join(tmpdir, "ws")
        os.makedirs(ws_dir)
        with open(os.path.join(ws_dir, "package.json"), "w", encoding="utf-8") as f:
            f.write('{"name": "demo-app"}')
            
        pm.register_project("demo", "Demo App", ws_dir)
        
        # Add sample tasks
        t1 = store.create_task("demo", "Design API", "Architect", "Spec schema")
        store.update_task_status(t1.task_id, "DONE")
        t2 = store.create_task("demo", "Write Endpoints", "BackendDev", "FastAPI routes")
        store.update_task_status(t2.task_id, "IN_PROGRESS")
        
        service = TechLeadService(store=store, pm=pm)
        standup = service.generate_standup("demo")
        
        assert standup["project_id"] == "demo"
        assert standup["health_status"] in ["ON_TRACK", "AT_RISK", "BLOCKED"]
        assert standup["progress_percent"] == 50
        assert len(standup["completed_items"]) == 1
        assert len(standup["active_items"]) == 1
        assert "Demo App" in standup["summary"]

def test_tech_lead_chat_response():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(db_path=os.path.join(tmpdir, "test.db"))
        pm = ProjectManager(store=store)
        ws_dir = os.path.join(tmpdir, "ws")
        os.makedirs(ws_dir)
        with open(os.path.join(ws_dir, "package.json"), "w", encoding="utf-8") as f:
            f.write('{"name": "demo-app"}')
            
        pm.register_project("demo", "Demo App", ws_dir)
        service = TechLeadService(store=store, pm=pm)
        
        reply = service.chat_with_lead("demo", "What is our current status?")
        assert "role" in reply
        assert reply["role"] == "TechLead"
        assert "message" in reply
        assert len(reply["message"]) > 0

def test_tech_lead_thai_chat_overview():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = StateStore(db_path=os.path.join(tmpdir, "test.db"))
        pm = ProjectManager(store=store)
        ws_dir = os.path.join(tmpdir, "ws")
        os.makedirs(ws_dir)
        with open(os.path.join(ws_dir, "package.json"), "w", encoding="utf-8") as f:
            f.write('{"name": "f1-racing", "dependencies": {"vite": "^5.0.0"}}')
            
        pm.register_project("f1", "f1", ws_dir)
        service = TechLeadService(store=store, pm=pm)
        
        reply = service.chat_with_lead("f1", "งานนี้เกี่ยวกับอะไร")
        assert reply["role"] == "TechLead"
        assert "โปรเจกต์ 'f1'" in reply["message"]
        assert "Node.js" in reply["message"]
        assert "สถานะทีม" in reply["message"]

