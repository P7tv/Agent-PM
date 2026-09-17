import React, { useState } from 'react';
import { ChevronDown, ChevronUp, CheckCircle2, AlertCircle, Clock, Check, RefreshCw } from 'lucide-react';

const STATUS_BADGE = {
  COMPLETED: { text: 'Done', cls: 'sprint-badge-done' },
  RUNNING: { text: 'Running', cls: 'sprint-badge-running' },
  REJECTED: { text: 'Rejected', cls: 'sprint-badge-rejected' },
  FAILED: { text: 'Failed', cls: 'sprint-badge-failed' },
};

const ROLE_ICONS = {
  TechLead: '👑',
  Architect: '🏛️',
  Designer: '🎨',
  FrontendDev: '⚛️',
  BackendDev: '⚙️',
  QATester: '🧪',
  Reviewer: '🔍',
  DocWriter: '📝'
};

export default function SprintHistoryPanel({ sprints = [], onRerun, onRetry }) {
  const [expandedSprintId, setExpandedSprintId] = useState(null);
  const [sprintTasks, setSprintTasks] = useState({});
  const [loadingTasks, setLoadingTasks] = useState({});

  if (!sprints.length) {
    return (
      <div className="sprint-history-empty">
        <div className="empty-icon">📋</div>
        <p className="empty-title">No sprint history recorded yet</p>
        <p className="empty-subtitle">Sprints will be recorded here automatically when PM directives execute</p>
      </div>
    );
  }

  const formatDuration = (start, end) => {
    if (!end) return 'Running...';
    const s = Math.round(end - start);
    return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
  };

  const formatDate = (ts) => {
    return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const toggleExpand = async (sprint) => {
    const isExpanding = expandedSprintId !== sprint.sprint_id;
    setExpandedSprintId(isExpanding ? sprint.sprint_id : null);

    if (isExpanding && !sprintTasks[sprint.sprint_id]) {
      setLoadingTasks(prev => ({ ...prev, [sprint.sprint_id]: true }));
      try {
        const res = await fetch(`/api/projects/${sprint.project_id}/sprints/${sprint.sprint_id}/tasks`);
        if (res.ok) {
          const tasks = await res.json();
          setSprintTasks(prev => ({ ...prev, [sprint.sprint_id]: tasks }));
        }
      } catch (err) {
        console.error("Error fetching sprint tasks:", err);
      } finally {
        setLoadingTasks(prev => ({ ...prev, [sprint.sprint_id]: false }));
      }
    }
  };

  return (
    <div className="sprint-history-panel">
      <div className="sprint-history-header">
        <span className="sprint-history-header-title">
          Sprint History ({sprints.length})
        </span>
        <div className="sprint-history-totals">
          <span>🪙 {sprints.reduce((sum, sprint) => sum + (sprint.total_tokens || 0), 0).toLocaleString()} tokens</span>
          <span>⏱ {Math.round(sprints.reduce((sum, sprint) => sum + (sprint.completed_at ? sprint.completed_at - sprint.started_at : 0), 0))}s</span>
          <span>≈ ${(sprints.reduce((sum, sprint) => sum + (sprint.total_tokens || 0), 0) * 0.000001).toFixed(3)}</span>
        </div>
      </div>
      <div className="sprint-history-list">
        {sprints.map((sp) => {
          const badge = STATUS_BADGE[sp.status] || STATUS_BADGE.COMPLETED;
          const isExpanded = expandedSprintId === sp.sprint_id;
          const tasks = sprintTasks[sp.sprint_id] || [];
          const isLoading = loadingTasks[sp.sprint_id];
          const changedFileCount = ['added', 'modified', 'deleted'].reduce(
            (total, kind) => total + (sp.change_evidence?.[kind]?.length || 0), 0,
          );
          // Older runs predate the explicit commit flag; completed staged runs
          // reached commit, while failed runs keep their checkpoint for retry.
          const filesApplied = sp.change_evidence?.applied_to_project
            ?? (sp.status === 'COMPLETED' && Boolean(sp.checkpoint_path));

          return (
            <div key={sp.sprint_id} className={`sprint-card ${isExpanded ? 'sprint-card-expanded' : ''}`}>
              <div className="sprint-card-top">
                <span className={`sprint-status-badge ${badge.cls}`}>{badge.text}</span>
                <span className="sprint-meta-item sprint-time">{formatDate(sp.started_at)}</span>
                <span className="sprint-meta-item sprint-duration">
                  ⏱ {formatDuration(sp.started_at, sp.completed_at)}
                </span>
                <span className="sprint-meta-item sprint-tokens">
                  🪙 {(sp.total_tokens || 0).toLocaleString()} tok
                </span>
                <span className="sprint-meta-item sprint-backend">{sp.backend_used || 'mock'}</span>
                
                <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <button
                    className="sprint-detail-toggle-btn"
                    onClick={() => toggleExpand(sp)}
                    title={isExpanded ? "Collapse task breakdown" : "Expand task breakdown"}
                  >
                    {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    <span>Tasks</span>
                  </button>

                  <a
                    href={`/api/projects/${sp.project_id}/sprints/${sp.sprint_id}/export`}
                    download={`sprint-${sp.sprint_id}-release-notes.md`}
                    className="sprint-export-btn"
                    title="Export sprint release notes (.md)"
                  >
                    📥 Export
                  </a>
                  {onRerun && (
                    <button
                      className="sprint-rerun-btn"
                      onClick={() => onRerun(sp.directive)}
                      title="Re-run this directive"
                    >
                      ↺ Re-run
                    </button>
                  )}
                  {onRetry && ['FAILED', 'REJECTED', 'PAUSED', 'INTERRUPTED'].includes(sp.status) && sp.checkpoint_path && sp.execution_plan?.checkpoint_manifest_hash && ['PLANNING', 'IMPLEMENTATION', 'QA', 'REVIEWER', 'FINAL'].includes(sp.execution_plan?.checkpoint_stage) && (
                    <button className="sprint-rerun-btn" onClick={() => onRetry(sp, 'QA')} title="ตรวจ QA และ Review ต่อจากไฟล์ที่เก็บไว้ แล้วนำเข้าโปรเจกต์เมื่อผ่านขั้นตรวจ">
                      ▶ ตรวจต่อและนำไฟล์ไปใช้
                    </button>
                  )}
                </div>
              </div>

              <div className="sprint-directive-text">{sp.directive}</div>

              {sp.checkpoint_path && (
                <div className="sprint-release-summary">
                  <strong>{filesApplied ? 'ไฟล์ถูกนำเข้าโปรเจกต์แล้ว' : 'ไฟล์ยังอยู่ในโฟลเดอร์พักงาน — ยังไม่นำเข้าโปรเจกต์'}</strong>
                  {changedFileCount > 0 && <div>ไฟล์ที่เพิ่ม แก้ไข หรือลบ: {changedFileCount} ไฟล์ (ดูรายการที่ Tasks)</div>}
                  <div style={{ overflowWrap: 'anywhere' }}>
                    ตำแหน่ง: <code>{filesApplied ? (sp.change_evidence?.project_workspace || 'โฟลเดอร์โปรเจกต์ที่ลงทะเบียน') : sp.checkpoint_path}</code>
                  </div>
                  {!filesApplied && <div>ระบบนำไฟล์เข้าโปรเจกต์หลังผ่าน QA, Review และการตรวจขั้นสุดท้าย หากหยุดหรือยกเลิก งานจะยังอยู่ในโฟลเดอร์พักงาน</div>}
                </div>
              )}

              {sp.release_summary && (
                <div className="sprint-release-summary">
                  <span className="summary-label">Summary: </span>
                  {sp.release_summary}
                </div>
              )}

              {/* Granular Task Breakdown Accordion */}
              {isExpanded && (
                <div className="sprint-tasks-breakdown">
                  {sp.execution_plan?.product_brief && <section>
                    <strong>สิ่งที่ต้องการให้ผู้ใช้ทำได้</strong>
                    <p>{sp.execution_plan.product_brief.outcome}</p>
                    {(sp.execution_plan.product_brief.constraints || []).map((item, i) => <div key={i}>ข้อกำหนด: {item}</div>)}
                    {(sp.execution_plan.product_brief.assumptions || []).map((item, i) => <div key={i}>ข้อสมมติ: {item}</div>)}
                    {(sp.execution_plan.product_brief.out_of_scope || []).map((item, i) => <div key={i}>นอกขอบเขต: {item}</div>)}
                  </section>}
                  {sp.execution_plan?.task_graph?.length > 0 && <details><summary>ลำดับงานและความสัมพันธ์</summary>
                    <ol>{sp.execution_plan.task_graph.map(item => <li key={item.id}>{item.title} · {item.role} · {item.write_policy === 'READ_ONLY' ? 'ตรวจผล' : 'ทำงานในไฟล์พักงาน'}</li>)}</ol>
                  </details>}
                  <div className="sprint-report-grid">
                    <section>
                      <strong>Acceptance criteria</strong>
                      {(sp.execution_plan?.acceptance_criteria || []).length ? <ul>{sp.execution_plan.acceptance_criteria.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p>No criteria recorded</p>}
                    </section>
                    <section>
                      <strong>Verification</strong>
                      <p>{sp.verification_report?.status || 'Not recorded'} {sp.verification_report?.stage ? `(${sp.verification_report.stage})` : ''}</p>
                      {sp.verification_report?.readiness && <p>ขอบเขต: {sp.verification_report.readiness === 'AUTOMATED_CHECKS_ONLY' ? 'ผ่าน automated checks; ยังไม่ใช่การตรวจรับครบทุก requirement' : 'ตรวจ source; ไม่ได้ยืนยันด้วย tests'}</p>}
                      {(sp.verification_report?.acceptance_coverage || []).map(item => <div key={item.id}>{item.id}: {item.status === 'VERIFIED_BY_CHECK' ? 'ผ่าน checks ที่ผูกกับ requirement' : item.status === 'NOT_INDEPENDENTLY_VERIFIED' ? 'ยังไม่ตรวจรับอย่างอิสระ' : item.status} — {item.description}</div>)}
                      {(sp.verification_report?.checks || []).map((check, index) => <div key={index}>{check.status === 'PASSED' ? '✅' : check.status === 'WARNING' ? '⚠️' : '❌'} {check.name}</div>)}
                    </section>
                    <section>
                      <strong>{filesApplied ? 'Applied file changes' : 'Staged file changes (ยังไม่นำเข้าโปรเจกต์)'}</strong>
                      {['added', 'modified', 'deleted'].flatMap(kind => (sp.change_evidence?.[kind] || []).map(path => <div key={`${kind}-${path}`}><code>{kind}</code> {path}</div>))}
                    </section>
                    <section>
                      <strong>Review verdict</strong>
                      <p>{sp.review_verdict?.verdict || 'Not recorded'}</p>
                      {(sp.review_verdict?.findings || []).map((item, index) => <div key={index}>• {item}</div>)}
                    </section>
                  </div>
                  {sp.change_evidence?.diff && <details className="sprint-diff"><summary>Review unified diff</summary><pre>{sp.change_evidence.diff}</pre></details>}
                  <div className="sprint-tasks-header">
                    <span>Task Execution Details ({tasks.length || sp.tasks_count || 0})</span>
                  </div>

                  {isLoading ? (
                    <div className="sprint-tasks-loading">
                      <RefreshCw size={14} className="animate-spin" /> Loading granular tasks...
                    </div>
                  ) : tasks.length === 0 ? (
                    <div className="sprint-tasks-empty">
                      No granular sub-tasks recorded for this run.
                    </div>
                  ) : (
                    <div className="sprint-tasks-list">
                      {tasks.map((t) => (
                        <div key={t.task_id} className="sprint-task-item">
                          <div className="sprint-task-main">
                            <span className="sprint-task-role" title={t.assigned_to}>
                              {ROLE_ICONS[t.assigned_to] || '🤖'} {t.assigned_to}
                            </span>
                            <span className="sprint-task-title">{t.title}</span>
                            <span className={`sprint-task-status status-${(t.status || 'TODO').toLowerCase()}`}>
                              {t.status}
                            </span>
                          </div>
                          {t.result_output && (
                            <div className="sprint-task-output">
                              <pre>{t.result_output}</pre>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
