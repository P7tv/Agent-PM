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

export default function SprintHistoryPanel({ sprints = [], onRerun }) {
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
      </div>
      <div className="sprint-history-list">
        {sprints.map((sp) => {
          const badge = STATUS_BADGE[sp.status] || STATUS_BADGE.COMPLETED;
          const isExpanded = expandedSprintId === sp.sprint_id;
          const tasks = sprintTasks[sp.sprint_id] || [];
          const isLoading = loadingTasks[sp.sprint_id];

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
                </div>
              </div>

              <div className="sprint-directive-text">{sp.directive}</div>

              {sp.release_summary && (
                <div className="sprint-release-summary">
                  <span className="summary-label">Summary: </span>
                  {sp.release_summary}
                </div>
              )}

              {/* Granular Task Breakdown Accordion */}
              {isExpanded && (
                <div className="sprint-tasks-breakdown">
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
