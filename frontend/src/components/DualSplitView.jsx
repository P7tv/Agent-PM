import React, { useState } from 'react';
import { Layers, Activity, CheckCircle2, Clock, Trash2, FolderPlus, Send } from 'lucide-react';

export default function DualSplitView({ 
  projects, 
  tasksByProject, 
  liveStreamsByProject, 
  onDeleteProject,
  onRequestDelete,
  onOpenAddProject,
  onDispatchDirective,
  onOpenStandup
}) {
  return (
    <div className="dual-split-view">
      {projects.map((project) => {
        const tasks = tasksByProject[project.project_id] || [];
        const stream = liveStreamsByProject[project.project_id] || [];

        const todoTasks = tasks.filter((t) => t.status === 'TODO');
        const inProgressTasks = tasks.filter((t) => ['IN_PROGRESS', 'TESTING', 'REVIEW'].includes(t.status));
        const doneTasks = tasks.filter((t) => t.status === 'DONE');

        return (
          <div key={project.project_id} className="project-column">
            <div className="room-header">
              <div>
                <h3 className="room-title">{project.name}</h3>
                <p className="room-workspace">{project.workspace_path}</p>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button
                  className="view-btn"
                  onClick={() => onOpenStandup(project.project_id, project.name)}
                  style={{ color: '#d97706', borderColor: 'rgba(245, 158, 11, 0.4)', padding: '4px 8px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}
                  title="Daily Standup Briefing"
                >
                  <span>👑 Standup</span>
                </button>
                <span className="room-tag">
                  {project.auto_pilot ? 'Auto-Pilot' : 'Gate Mode'}
                </span>
                <button
                  className="view-btn"
                  onClick={() => {
                    if (onRequestDelete) {
                      onRequestDelete(project);
                    } else {
                      onDeleteProject(project.project_id);
                    }
                  }}
                  title="Remove project"
                  style={{ color: 'var(--accent-coral)', borderColor: 'rgba(239, 68, 68, 0.25)', padding: '4px 6px' }}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </div>


            {/* Kanban Overview */}
            <div className="kanban-section">
              <div className="kanban-col">
                <div className="kanban-header">
                  <span>To Do</span>
                  <span>{todoTasks.length}</span>
                </div>
                {todoTasks.map((t) => (
                  <div key={t.task_id} className="kanban-card">
                    <div>{t.title}</div>
                    <div className="kanban-assignee">@{t.assigned_to}</div>
                  </div>
                ))}
              </div>

              <div className="kanban-col">
                <div className="kanban-header">
                  <span>In Progress</span>
                  <span>{inProgressTasks.length}</span>
                </div>
                {inProgressTasks.map((t) => (
                  <div key={t.task_id} className="kanban-card">
                    <div>{t.title}</div>
                    <div className="kanban-assignee">@{t.assigned_to}</div>
                  </div>
                ))}
              </div>

              <div className="kanban-col">
                <div className="kanban-header">
                  <span>Done</span>
                  <span>{doneTasks.length}</span>
                </div>
                {doneTasks.map((t) => (
                  <div key={t.task_id} className="kanban-card">
                    <div>{t.title}</div>
                    <div className="kanban-assignee">@{t.assigned_to}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Live Terminal Stream */}
            <div style={{ marginTop: '10px' }}>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: '500' }}>
                <Activity size={13} color="var(--primary)" />
                <span>ACTIVITY FEED</span>
              </div>
              <div className="live-stream-box">
                {stream.length === 0 ? (
                  <div style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Standing by for PM directives...</div>
                ) : (
                  stream.slice(-30).map((log, i) => (
                    <div key={i} className="stream-entry">
                      <span className="stream-role">[{log.role || 'SYS'}]</span>
                      {log.thought && <span className="stream-thought">{log.thought}</span>}
                      {log.tool && <span className="stream-tool">[tool: {log.tool}]</span>}
                      {log.message && <span className="stream-thought">{log.message}</span>}
                    </div>
                  ))
                )}
              </div>
            </div>
            {/* Per-Column Directive Input */}
            <ColumnDirectiveBar
              projectId={project.project_id}
              onDispatchDirective={onDispatchDirective}
            />
          </div>
        );
      })}

      {/* Add Project column slot */}
      <div 
        className="project-column" 
        style={{ 
          border: '2px dashed var(--border-medium)', 
          display: 'flex', 
          flexDirection: 'column', 
          alignItems: 'center', 
          justifyContent: 'center', 
          minHeight: '340px',
          textAlign: 'center',
          cursor: 'pointer',
          background: 'var(--bg-canvas)',
          opacity: 0.9,
          transition: 'all 0.2s ease'
        }}
        onClick={onOpenAddProject}
      >
        <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: 'var(--primary-subtle)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '12px' }}>
          <FolderPlus size={24} />
        </div>
        <h4 style={{ fontSize: '15px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '4px' }}>
          Connect Project {String(projects.length + 1).padStart(2, '0')}
        </h4>
        <p style={{ fontSize: '12px', color: 'var(--text-muted)', maxWidth: '240px', marginBottom: '14px' }}>
          Split screen will display your projects side-by-side.
        </p>
        <button className="dispatch-btn" style={{ fontSize: '12px', padding: '6px 14px' }}>
          + Add Project
        </button>
      </div>
    </div>
  );
}

function ColumnDirectiveBar({ projectId, onDispatchDirective }) {
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!text.trim() || !onDispatchDirective) return;
    setSending(true);
    await onDispatchDirective(projectId, text);
    setText('');
    setSending(false);
  };

  return (
    <form onSubmit={handleSubmit} style={{
      display: 'flex', gap: '8px', marginTop: '10px',
      padding: '8px 10px', background: 'var(--bg-canvas)',
      borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)'
    }}>
      <input
        type="text"
        className="pm-input"
        style={{ fontSize: '12px', flex: 1 }}
        placeholder="Quick directive for this project..."
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={sending}
      />
      <button
        type="submit"
        className="dispatch-btn"
        style={{ fontSize: '11px', padding: '5px 10px' }}
        disabled={sending || !text.trim()}
      >
        <Send size={12} />
      </button>
    </form>
  );
}
