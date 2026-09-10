import os
import tempfile
import pytest
from app.services.workspace_inspector import WorkspaceInspector

def test_deep_inspection_readme_and_topology():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create mock project structure with README
        readme_path = os.path.join(tmpdir, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write("# E-Commerce Storefront\nA modern online shopping platform with Stripe checkout.")
            
        os.makedirs(os.path.join(tmpdir, "src", "components"))
        os.makedirs(os.path.join(tmpdir, "src", "api"))
        os.makedirs(os.path.join(tmpdir, "tests"))
        
        with open(os.path.join(tmpdir, "package.json"), "w", encoding="utf-8") as f:
            f.write('{"name": "ecommerce-app", "scripts": {"test": "vitest run"}, "dependencies": {"react": "^18.0.0"}}')
            
        inspector = WorkspaceInspector()
        valid, msg, meta = inspector.validate_guardrails(tmpdir)
        
        assert valid is True
        assert "purpose_summary" in meta
        assert "E-Commerce Storefront" in meta["purpose_summary"]
        assert meta["test_command"] == "vitest run"
        assert any("src/components" in d for d in meta["directory_structure"])
        assert meta["test_runner"] == "vitest"
