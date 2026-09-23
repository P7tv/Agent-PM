import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import SprintRecord
from app.services.verification import detect_verification_commands
from app.services.workspace_session import WorkspaceSession


def test_queue_round_trips_acceptance_and_protected_paths(isolated_db):
    item = isolated_db.enqueue_directive(
        "project", "Build it", acceptance_criteria=["Health endpoint returns 200"],
        protected_paths=[".env", "infra/production"], source_sprint_id="old", resume_from="QA",
    )
    loaded = isolated_db.get_queue_item(item.queue_id)
    assert loaded.acceptance_criteria == ["Health endpoint returns 200"]
    assert loaded.protected_paths == [".env", "infra/production"]
    assert loaded.source_sprint_id == "old"
    assert loaded.resume_from == "QA"


def test_structured_sprint_report_round_trip(isolated_db):
    sprint = SprintRecord(
        sprint_id="structured", project_id="project", directive="Ship",
        execution_plan={"acceptance_criteria": ["Works"]},
        verification_report={"status": "PASSED", "checks": []},
        change_evidence={"modified": ["app.py"], "diff": "--- a/app.py"},
        review_verdict={"verdict": "APPROVED"}, checkpoint_path="/tmp/checkpoint",
    )
    isolated_db.record_sprint(sprint)
    loaded = isolated_db.get_sprint("structured")
    assert loaded.execution_plan["acceptance_criteria"] == ["Works"]
    assert loaded.change_evidence["modified"] == ["app.py"]
    assert loaded.review_verdict["verdict"] == "APPROVED"


def test_reviewer_large_evidence_is_explicitly_bounded():
    from app.services.orchestrator import reviewer_excerpt
    evidence = 'large diff\n' * 10000
    excerpt = reviewer_excerpt(evidence, 6000)
    assert len(excerpt) < 6100
    assert excerpt.startswith(evidence[:6000])
    assert 'Inspect the actual checkpoint files' in excerpt
    assert reviewer_excerpt('small evidence') == 'small evidence'


def test_durable_workspace_checkpoint_can_resume_and_commit(tmp_path):
    original = tmp_path / "original"
    original.mkdir()
    (original / "app.txt").write_text("one\n")
    runs = tmp_path / "runs"
    first = WorkspaceSession(str(original), str(runs), "sprint-one")
    (first.workspace / "app.txt").write_text("two\n")
    checkpoint = str(first.workspace)
    first.close(delete=False)

    resumed = WorkspaceSession(str(original), str(runs), "sprint-two", checkpoint)
    assert resumed.changes()["modified"] == ["app.txt"]
    resumed.commit()
    resumed.close(delete=True)
    assert (original / "app.txt").read_text() == "two\n"
    assert not Path(checkpoint).exists()


def test_project_config_overrides_auto_detection(tmp_path):
    (tmp_path / ".agent-pm.yml").write_text(
        "verification:\n  checks:\n    - name: focused\n      command: [python, -m, compileall, .]\n      kind: build\n      required: true\n"
    )
    checks = detect_verification_commands(str(tmp_path))
    assert len(checks) == 1
    assert checks[0]["name"] == "focused"
    assert checks[0]["required"] is True


def test_preview_process_can_start_and_stop(tmp_path, isolated_db):
    client = TestClient(app)
    workspace = tmp_path / "preview"
    workspace.mkdir()
    (workspace / ".agent-pm.yml").write_text(
        "preview:\n  command: [python, -c, 'import time; time.sleep(10)']\n  url: http://127.0.0.1:9999\n"
    )
    assert client.post("/api/projects", json={
        "project_id": "preview", "name": "Preview", "workspace_path": str(workspace), "auto_pilot": True,
    }).status_code == 200
    started = client.post("/api/projects/preview/preview")
    assert started.status_code == 200
    assert started.json()["running"] is True
    assert client.get("/api/projects/preview/preview").json()["running"] is True
    stopped = client.delete("/api/projects/preview/preview")
    assert stopped.status_code == 200
    assert stopped.json()["running"] is False


def test_report_endpoint_enforces_project_ownership(tmp_path, isolated_db):
    client = TestClient(app)
    for project_id in ("one", "two"):
        workspace = tmp_path / project_id
        workspace.mkdir()
        assert client.post("/api/projects", json={
            "project_id": project_id, "name": project_id, "workspace_path": str(workspace), "auto_pilot": True,
        }).status_code == 200
    isolated_db.record_sprint(SprintRecord(sprint_id="s1", project_id="one", directive="Build"))
    assert client.get("/api/projects/one/sprints/s1/report").status_code == 200
    assert client.get("/api/projects/two/sprints/s1/report").status_code == 404
    assert client.get("/api/projects/two/sprints/s1/agent-logs").status_code == 404
    assert client.get("/api/projects/two/sprints/s1/export").status_code == 404


def test_workspace_sibling_prefix_is_not_treated_as_inside(tmp_path, isolated_db):
    client = TestClient(app)
    workspace = tmp_path / "app"
    sibling = tmp_path / "app-secret"
    workspace.mkdir()
    sibling.mkdir()
    (sibling / "secret.txt").write_text("secret")
    assert client.post("/api/projects", json={
        "project_id": "paths", "name": "Paths", "workspace_path": str(workspace), "auto_pilot": True,
    }).status_code == 200
    assert client.get("/api/projects/paths/files/content", params={"path": "../app-secret/secret.txt"}).status_code == 400
    assert client.post("/api/projects/paths/apply-change", json={
        "filepath": "../app-secret/changed.txt", "content": "no",
    }).status_code == 403
    assert not (sibling / "changed.txt").exists()


def test_apply_change_verifies_stages_and_blocks_protected_paths(tmp_path, isolated_db):
    workspace = tmp_path / "safe-apply"
    workspace.mkdir()
    (workspace / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    test_file = workspace / "test_project.py"
    test_file.write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    client = TestClient(app)
    assert client.post("/api/projects", json={
        "project_id": "safe-apply", "name": "Safe apply",
        "workspace_path": str(workspace), "auto_pilot": True,
    }).status_code == 200

    protected = client.post("/api/projects/safe-apply/apply-change", json={
        "filepath": ".env", "content": "SECRET=no\n",
    })
    assert protected.status_code == 403
    assert not (workspace / ".env").exists()

    applied = client.post("/api/projects/safe-apply/apply-change", json={
        "filepath": "feature.py", "content": "READY = True\n",
    })
    assert applied.status_code == 200, applied.text
    assert applied.json()["verification"]["status"] == "PASSED"
    assert (workspace / "feature.py").read_text(encoding="utf-8") == "READY = True\n"

    test_file.write_text("def test_failure():\n    assert False\n", encoding="utf-8")
    rejected = client.post("/api/projects/safe-apply/apply-change", json={
        "filepath": "rejected.py", "content": "SHOULD_NOT_APPLY = True\n",
    })
    assert rejected.status_code == 409
    assert not (workspace / "rejected.py").exists()


def test_openapi_operation_ids_are_unique(isolated_db):
    schema = TestClient(app).get("/openapi.json").json()
    operation_ids = [
        operation["operationId"]
        for path in schema["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]
    assert len(operation_ids) == len(set(operation_ids))


def test_triage_failure_cannot_resume_as_completed_implementation(tmp_path, isolated_db):
    workspace = tmp_path / 'checkpoint'
    workspace.mkdir()
    isolated_db.record_sprint(SprintRecord(
        sprint_id='triage-failed', project_id='project', directive='Build',
        status='FAILED', checkpoint_path=str(workspace),
    ))
    response = TestClient(app).post('/api/projects/project/sprints/triage-failed/retry', json={'stage': 'QA'})
    assert response.status_code == 409
    assert 'Re-run' in response.json()['detail']


def test_resume_deduplicates_pending_checkpoint(tmp_path, isolated_db):
    checkpoint = tmp_path / 'checkpoint'
    checkpoint.mkdir()
    isolated_db.record_sprint(SprintRecord(
        sprint_id='stopped', project_id='project', directive='Build', status='FAILED',
        checkpoint_path=str(checkpoint), execution_plan={'checkpoint_stage': 'REVIEWER'},
    ))
    pending = isolated_db.enqueue_directive('project', 'Build', source_sprint_id='stopped', resume_from='QA')
    client = TestClient(app)
    for _ in range(2):
        response = client.post('/api/projects/project/sprints/stopped/retry', json={'stage': 'QA'})
        assert response.status_code == 200
        assert response.json()['queue_id'] == pending.queue_id
    assert len(isolated_db.get_queue('project')) == 1


def test_resume_rejects_active_project_and_applied_checkpoint(tmp_path, isolated_db):
    checkpoint = tmp_path / 'checkpoint'
    checkpoint.mkdir()
    isolated_db.record_sprint(SprintRecord(
        sprint_id='stopped', project_id='project', directive='Build', status='FAILED',
        checkpoint_path=str(checkpoint), execution_plan={'checkpoint_stage': 'REVIEWER'},
    ))
    isolated_db.record_sprint(SprintRecord(sprint_id='active', project_id='project', directive='Build', status='RUNNING'))
    client = TestClient(app)
    response = client.post('/api/projects/project/sprints/stopped/retry', json={'stage': 'QA'})
    assert response.status_code == 409
    assert 'active sprint' in response.json()['detail']
    isolated_db.update_sprint('active', status='COMPLETED')
    isolated_db.update_sprint('stopped', change_evidence={'applied_to_project': True})
    response = client.post('/api/projects/project/sprints/stopped/retry', json={'stage': 'QA'})
    assert response.status_code == 409
    assert 'already been applied' in response.json()['detail']
    assert isolated_db.get_queue('project') == []


@pytest.mark.asyncio
async def test_change_request_gate_preserves_feedback(isolated_db, tmp_path):
    from app.services.agent_runner import AgentRunner
    from app.services.orchestrator import Orchestrator
    from app.services.project_manager import ProjectManager

    orchestrator = Orchestrator(isolated_db, ProjectManager(isolated_db), AgentRunner(use_mock=True))
    approval = isolated_db.create_approval_request("project", "PLAN_APPROVAL", "Plan")
    waiter = asyncio.create_task(orchestrator._wait_for_approval(approval.request_id, timeout=1))
    await asyncio.sleep(0)
    orchestrator.resolve_gate(approval.request_id, "CHANGES_REQUESTED", "Keep the API compatible")
    assert await waiter == "CHANGES_REQUESTED"
    assert orchestrator._gate_feedback[approval.request_id] == "Keep the API compatible"
