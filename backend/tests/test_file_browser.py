import pytest
import os
import tempfile
from fastapi.testclient import TestClient
from app.main import app

def test_file_browser_endpoints():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create dummy file inside tmpdir
        sample_file = os.path.join(tmpdir, "hello.py")
        with open(sample_file, "w", encoding="utf-8") as f:
            f.write("print('hello world')")
            
        client = TestClient(app)
        
        # Register project
        res = client.post("/api/projects", json={
            "project_id": "test-fb",
            "name": "File Browser Test",
            "workspace_path": tmpdir,
            "auto_pilot": True
        })
        assert res.status_code == 200
        
        # List files
        res = client.get("/api/projects/test-fb/files")
        assert res.status_code == 200
        data = res.json()
        assert "files" in data
        assert any(f["name"] == "hello.py" for f in data["files"])
        
        # Read file content
        res = client.get("/api/projects/test-fb/files/content?path=hello.py")
        assert res.status_code == 200
        data = res.json()
        assert "print('hello world')" in data["content"]
        
        # Path traversal guard
        res = client.get("/api/projects/test-fb/files/content?path=../../etc/passwd")
        assert res.status_code in (400, 403, 404)
        
        # Cleanup
        client.delete("/api/projects/test-fb")
